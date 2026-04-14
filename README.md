# Cloud-Native-Smart-Factory-Data-Lakehouse

## Sensor Data Generator

This project includes a TypeScript sensor data generator that continuously publishes machine telemetry to RabbitMQ.

### Payload format

The generator publishes JSON payloads like:

{
	"timestamp": "2026-04-14T07:30:00Z",
	"machine_id": "M-001",
	"temperature": 85.5,
	"vibration": 1.2
}

### Setup

1. Start RabbitMQ and Postgres with Docker Compose.
2. Install dependencies.
3. Run the generator.

Commands:

docker compose up -d
npm install
npm run dev

### Config via environment variables

- RABBITMQ_URL (default: amqp://guest:guest@localhost:5672)
- RABBITMQ_QUEUE (default: sensor_data_queue)
- PUBLISH_INTERVAL_MS (default: 1000)
- MACHINE_IDS (default: M-001,M-002,M-003)
