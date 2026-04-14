import amqp, { Channel, ChannelModel } from "amqplib";

type SensorPayload = {
  timestamp: string;
  machine_id: string;
  temperature: number;
  vibration: number;
};

const rabbitMqUrl = process.env.RABBITMQ_URL ?? "amqp://guest:guest@localhost:5672";
const queueName = process.env.RABBITMQ_QUEUE ?? "sensor_data_queue";
const intervalMs = Number(process.env.PUBLISH_INTERVAL_MS ?? "1000");
const machineIds = (process.env.MACHINE_IDS ?? "M-001,M-002,M-003")
  .split(",")
  .map((v) => v.trim())
  .filter(Boolean);

if (Number.isNaN(intervalMs) || intervalMs <= 0) {
  throw new Error("PUBLISH_INTERVAL_MS must be a positive number");
}

if (machineIds.length === 0) {
  throw new Error("MACHINE_IDS must contain at least one machine id");
}

const randomBetween = (min: number, max: number): number =>
  Math.round((Math.random() * (max - min) + min) * 100) / 100;

const pickMachineId = (): string => machineIds[Math.floor(Math.random() * machineIds.length)];

const createPayload = (): SensorPayload => ({
  timestamp: new Date().toISOString(),
  machine_id: pickMachineId(),
  temperature: randomBetween(70, 95),
  vibration: randomBetween(0.2, 2.5)
});

const delay = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms));

const logConfig = (): void => {
  console.log("Sensor generator configuration");
  console.log(`- RabbitMQ URL: ${rabbitMqUrl}`);
  console.log(`- Queue name: ${queueName}`);
  console.log(`- Publish interval (ms): ${intervalMs}`);
  console.log(`- Machine IDs: ${machineIds.join(", ")}`);
};

const setupGracefulShutdown = (
  connectionRef: { current: ChannelModel | null },
  channelRef: { current: Channel | null }
): void => {
  const shutdown = async (signal: string): Promise<void> => {
    console.log(`Received ${signal}. Closing RabbitMQ connection...`);
    try {
      await channelRef.current?.close();
      await connectionRef.current?.close();
    } finally {
      process.exit(0);
    }
  };

  process.on("SIGINT", () => {
    void shutdown("SIGINT");
  });

  process.on("SIGTERM", () => {
    void shutdown("SIGTERM");
  });
};

const publishLoop = async (): Promise<void> => {
  const connectionRef: { current: ChannelModel | null } = { current: null };
  const channelRef: { current: Channel | null } = { current: null };
  setupGracefulShutdown(connectionRef, channelRef);

  while (true) {
    try {
      logConfig();
      connectionRef.current = await amqp.connect(rabbitMqUrl);
      channelRef.current = await connectionRef.current.createChannel();
      await channelRef.current.assertQueue(queueName, { durable: true });
      console.log(`Connected to RabbitMQ and ready to publish to ${queueName}`);

      while (true) {
        const payload = createPayload();
        const json = JSON.stringify(payload);
        const channel = channelRef.current;
        if (!channel) {
          throw new Error("RabbitMQ channel is not available");
        }

        const published = channel.sendToQueue(queueName, Buffer.from(json), {
          persistent: true,
          contentType: "application/json"
        });

        if (!published) {
          await new Promise<void>((resolve) => {
            channel.once("drain", () => resolve());
          });
        }

        console.log(`Published: ${json}`);
        await delay(intervalMs);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      console.error(`Publish loop error: ${message}`);
      console.error("Retrying connection in 3 seconds...");
      await delay(3000);
    } finally {
      try {
        await channelRef.current?.close();
      } catch {
        // Ignore close errors while retrying.
      }
      try {
        await connectionRef.current?.close();
      } catch {
        // Ignore close errors while retrying.
      }
      channelRef.current = null;
      connectionRef.current = null;
    }
  }
};

void publishLoop();