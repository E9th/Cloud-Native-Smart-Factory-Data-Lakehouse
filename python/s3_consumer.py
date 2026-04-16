import csv
import json
import os
import signal
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
import pika


@dataclass
class ConsumerConfig:
    rabbitmq_url: str
    queue_name: str
    batch_size: int
    flush_interval_seconds: int
    s3_bucket: str
    s3_prefix: str
    output_format: str


def load_config() -> ConsumerConfig:
    rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672")
    queue_name = os.getenv("RABBITMQ_QUEUE", "sensor_data_queue")
    batch_size = int(os.getenv("BATCH_SIZE", "10000"))
    flush_interval_seconds = int(os.getenv("FLUSH_INTERVAL_SECONDS", "300"))
    s3_bucket = os.getenv("S3_BUCKET", "").strip()
    s3_prefix = os.getenv("S3_PREFIX", "sensor-data").strip().strip("/")
    output_format = os.getenv("OUTPUT_FORMAT", "json").strip().lower()

    if batch_size <= 0:
        raise ValueError("BATCH_SIZE must be greater than 0")

    if flush_interval_seconds <= 0:
        raise ValueError("FLUSH_INTERVAL_SECONDS must be greater than 0")

    if not s3_bucket:
        raise ValueError("S3_BUCKET is required")

    if output_format not in {"json", "csv"}:
        raise ValueError("OUTPUT_FORMAT must be either 'json' or 'csv'")

    return ConsumerConfig(
        rabbitmq_url=rabbitmq_url,
        queue_name=queue_name,
        batch_size=batch_size,
        flush_interval_seconds=flush_interval_seconds,
        s3_bucket=s3_bucket,
        s3_prefix=s3_prefix,
        output_format=output_format,
    )


def parse_message(body: bytes) -> dict[str, Any]:
    text = body.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {
            "raw_message": text,
            "parse_error": "invalid_json",
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }

    if isinstance(parsed, dict):
        return parsed

    return {
        "raw_message": text,
        "parse_error": "non_object_json",
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }


def timestamped_filename(output_format: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"sensor_data_{stamp}.{output_format}"


def to_s3_key(prefix: str, filename: str) -> str:
    now = datetime.now(timezone.utc)
    date_prefix = f"year={now:%Y}/month={now:%m}/day={now:%d}"
    if prefix:
        return f"{prefix}/{date_prefix}/{filename}"
    return f"{date_prefix}/{filename}"


def write_json(records: list[dict[str, Any]], file_path: Path) -> None:
    with file_path.open("w", encoding="utf-8") as file:
        json.dump(records, file, ensure_ascii=False)


def write_csv(records: list[dict[str, Any]], file_path: Path) -> None:
    all_keys: set[str] = set()
    for record in records:
        all_keys.update(record.keys())

    fieldnames = sorted(all_keys)
    with file_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def create_batch_file(records: list[dict[str, Any]], output_format: str) -> Path:
    filename = timestamped_filename(output_format)
    temp_path = Path(tempfile.gettempdir()) / filename

    if output_format == "csv":
        write_csv(records, temp_path)
    else:
        write_json(records, temp_path)

    return temp_path


class S3BatchConsumer:
    def __init__(self, config: ConsumerConfig) -> None:
        self.config = config
        self.s3_client = boto3.client("s3")
        self.connection = pika.BlockingConnection(
            pika.URLParameters(config.rabbitmq_url)
        )
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=config.queue_name, durable=True)
        self.channel.basic_qos(prefetch_count=config.batch_size)
        self.records: list[dict[str, Any]] = []
        self.last_delivery_tag: int | None = None
        self.last_flush_time = time.time()
        self.stopping = False

    def stop(self) -> None:
        self.stopping = True

    def should_flush(self) -> bool:
        if not self.records:
            return False

        if len(self.records) >= self.config.batch_size:
            return True

        elapsed = time.time() - self.last_flush_time
        return elapsed >= self.config.flush_interval_seconds

    def flush(self) -> bool:
        if not self.records or self.last_delivery_tag is None:
            return True

        batch_size = len(self.records)
        local_file = create_batch_file(self.records, self.config.output_format)
        s3_key = to_s3_key(self.config.s3_prefix, local_file.name)

        try:
            self.s3_client.upload_file(str(local_file), self.config.s3_bucket, s3_key)
            self.channel.basic_ack(delivery_tag=self.last_delivery_tag, multiple=True)
            print(
                f"Uploaded batch to s3://{self.config.s3_bucket}/{s3_key} with {batch_size} records"
            )
            self.records.clear()
            self.last_delivery_tag = None
            self.last_flush_time = time.time()
            return True
        except Exception as error:
            print(f"Batch upload failed, will retry: {error}")
            return False
        finally:
            try:
                local_file.unlink(missing_ok=True)
            except OSError:
                pass

    def run(self) -> None:
        print(
            "Starting consumer with "
            f"batch_size={self.config.batch_size}, "
            f"flush_interval_seconds={self.config.flush_interval_seconds}, "
            f"queue={self.config.queue_name}, "
            f"output_format={self.config.output_format}"
        )

        for method, _properties, body in self.channel.consume(
            self.config.queue_name,
            inactivity_timeout=1,
            auto_ack=False,
        ):
            if self.stopping:
                break

            if method is not None:
                self.records.append(parse_message(body))
                self.last_delivery_tag = method.delivery_tag

            if self.should_flush():
                flushed = self.flush()
                if not flushed:
                    time.sleep(3)

        if self.records:
            flushed = self.flush()
            if not flushed:
                print(
                    "Final flush failed. Messages remain unacked and will be re-queued by RabbitMQ when connection closes."
                )

        try:
            self.channel.cancel()
        except Exception:
            pass

        self.connection.close()
        print("Consumer stopped")


def main() -> None:
    config = load_config()
    consumer = S3BatchConsumer(config)

    def handle_signal(signum: int, _frame: Any) -> None:
        print(f"Received signal {signum}, stopping consumer...")
        consumer.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    consumer.run()


if __name__ == "__main__":
    main()