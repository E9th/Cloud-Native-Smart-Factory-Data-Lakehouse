import amqp, { Channel, ChannelModel } from "amqplib";
import express from "express";
import { once } from "node:events";
import path from "node:path";

type SensorPayload = {
  timestamp: string;
  machine_id: string;
  temperature: number;
  vibration: number;
};

const rabbitMqUrl = process.env.RABBITMQ_URL ?? "amqp://guest:guest@localhost:5672";
const queueName = process.env.RABBITMQ_QUEUE ?? "sensor_data_queue";
const port = Number(process.env.API_PORT ?? "3000");
const maxRecentMessages = Number(process.env.MAX_RECENT_MESSAGES ?? "100");

if (Number.isNaN(port) || port <= 0) {
  throw new Error("API_PORT must be a positive number");
}

if (Number.isNaN(maxRecentMessages) || maxRecentMessages <= 0) {
  throw new Error("MAX_RECENT_MESSAGES must be a positive number");
}

const app = express();
app.use(express.json({ limit: "1mb" }));

const publicDir = path.resolve(process.cwd(), "public");
app.use(express.static(publicDir));

let connection: ChannelModel | null = null;
let channel: Channel | null = null;
let totalReceived = 0;
let totalPublished = 0;

const latestByMachine = new Map<string, SensorPayload>();
const recentMessages: SensorPayload[] = [];

const toSensorPayload = (value: unknown): SensorPayload | null => {
  if (!value || typeof value !== "object") {
    return null;
  }

  const raw = value as Record<string, unknown>;
  const machineId = typeof raw.machine_id === "string" ? raw.machine_id.trim() : "";
  const temperature = Number(raw.temperature);
  const vibration = Number(raw.vibration);

  if (!machineId || Number.isNaN(temperature) || Number.isNaN(vibration)) {
    return null;
  }

  const parsedTimestamp =
    typeof raw.timestamp === "string" && !Number.isNaN(Date.parse(raw.timestamp))
      ? raw.timestamp
      : new Date().toISOString();

  return {
    timestamp: parsedTimestamp,
    machine_id: machineId,
    temperature,
    vibration
  };
};

const rememberPayload = (payload: SensorPayload): void => {
  latestByMachine.set(payload.machine_id, payload);
  recentMessages.unshift(payload);
  if (recentMessages.length > maxRecentMessages) {
    recentMessages.length = maxRecentMessages;
  }
};

const connectRabbitMq = async (): Promise<void> => {
  connection = await amqp.connect(rabbitMqUrl);
  channel = await connection.createChannel();
  await channel.assertQueue(queueName, { durable: true });
  console.log(`Connected to RabbitMQ at ${rabbitMqUrl}`);
  console.log(`Queue ready: ${queueName}`);
};

const publishToQueue = async (payload: SensorPayload): Promise<void> => {
  if (!channel) {
    throw new Error("RabbitMQ channel is not available");
  }

  const ok = channel.sendToQueue(queueName, Buffer.from(JSON.stringify(payload)), {
    persistent: true,
    contentType: "application/json"
  });

  if (!ok) {
    await once(channel, "drain");
  }

  totalPublished += 1;
};

app.get("/health", (_req, res) => {
  res.json({
    status: "ok",
    rabbitmq_connected: Boolean(channel),
    queue: queueName,
    total_received: totalReceived,
    total_published: totalPublished
  });
});

app.post("/api/sensor-data", async (req, res) => {
  const payload = toSensorPayload(req.body);
  if (!payload) {
    res.status(400).json({
      error: "Invalid payload. Required fields: machine_id (string), temperature (number), vibration (number), timestamp (optional ISO string)."
    });
    return;
  }

  totalReceived += 1;
  rememberPayload(payload);

  try {
    await publishToQueue(payload);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    res.status(503).json({ error: `Failed to publish message: ${message}` });
    return;
  }

  res.status(202).json({ status: "published", queue: queueName, payload });
});

app.get("/api/dashboard", (_req, res) => {
  const machines = Array.from(latestByMachine.values()).sort((a, b) =>
    a.machine_id.localeCompare(b.machine_id)
  );

  res.json({
    queue: queueName,
    total_received: totalReceived,
    total_published: totalPublished,
    machine_count: machines.length,
    machines,
    recent_messages: recentMessages,
    server_time: new Date().toISOString()
  });
});

const start = async (): Promise<void> => {
  await connectRabbitMq();

  app.listen(port, () => {
    console.log(`Sensor API server listening on http://localhost:${port}`);
    console.log(`Dashboard UI available on http://localhost:${port}`);
  });
};

const shutdown = async (signal: string): Promise<void> => {
  console.log(`Received ${signal}. Closing API server resources...`);
  try {
    await channel?.close();
  } catch {
    // Ignore close errors during shutdown.
  }

  try {
    await connection?.close();
  } catch {
    // Ignore close errors during shutdown.
  }

  process.exit(0);
};

process.on("SIGINT", () => {
  void shutdown("SIGINT");
});

process.on("SIGTERM", () => {
  void shutdown("SIGTERM");
});

start().catch((error) => {
  const message = error instanceof Error ? error.message : String(error);
  console.error(`Failed to start API server: ${message}`);
  process.exit(1);
});