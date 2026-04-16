"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const amqplib_1 = __importDefault(require("amqplib"));
const express_1 = __importDefault(require("express"));
const node_events_1 = require("node:events");
const node_path_1 = __importDefault(require("node:path"));
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
const app = (0, express_1.default)();
app.use(express_1.default.json({ limit: "1mb" }));
const publicDir = node_path_1.default.resolve(process.cwd(), "public");
app.use(express_1.default.static(publicDir));
let connection = null;
let channel = null;
let totalReceived = 0;
let totalPublished = 0;
const latestByMachine = new Map();
const recentMessages = [];
const toSensorPayload = (value) => {
    if (!value || typeof value !== "object") {
        return null;
    }
    const raw = value;
    const machineId = typeof raw.machine_id === "string" ? raw.machine_id.trim() : "";
    const temperature = Number(raw.temperature);
    const vibration = Number(raw.vibration);
    if (!machineId || Number.isNaN(temperature) || Number.isNaN(vibration)) {
        return null;
    }
    const parsedTimestamp = typeof raw.timestamp === "string" && !Number.isNaN(Date.parse(raw.timestamp))
        ? raw.timestamp
        : new Date().toISOString();
    return {
        timestamp: parsedTimestamp,
        machine_id: machineId,
        temperature,
        vibration
    };
};
const rememberPayload = (payload) => {
    latestByMachine.set(payload.machine_id, payload);
    recentMessages.unshift(payload);
    if (recentMessages.length > maxRecentMessages) {
        recentMessages.length = maxRecentMessages;
    }
};
const connectRabbitMq = async () => {
    connection = await amqplib_1.default.connect(rabbitMqUrl);
    channel = await connection.createChannel();
    await channel.assertQueue(queueName, { durable: true });
    console.log(`Connected to RabbitMQ at ${rabbitMqUrl}`);
    console.log(`Queue ready: ${queueName}`);
};
const publishToQueue = async (payload) => {
    if (!channel) {
        throw new Error("RabbitMQ channel is not available");
    }
    const ok = channel.sendToQueue(queueName, Buffer.from(JSON.stringify(payload)), {
        persistent: true,
        contentType: "application/json"
    });
    if (!ok) {
        await (0, node_events_1.once)(channel, "drain");
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
    }
    catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        res.status(503).json({ error: `Failed to publish message: ${message}` });
        return;
    }
    res.status(202).json({ status: "published", queue: queueName, payload });
});
app.get("/api/dashboard", (_req, res) => {
    const machines = Array.from(latestByMachine.values()).sort((a, b) => a.machine_id.localeCompare(b.machine_id));
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
const start = async () => {
    await connectRabbitMq();
    app.listen(port, () => {
        console.log(`Sensor API server listening on http://localhost:${port}`);
        console.log(`Dashboard UI available on http://localhost:${port}`);
    });
};
const shutdown = async (signal) => {
    console.log(`Received ${signal}. Closing API server resources...`);
    try {
        await channel?.close();
    }
    catch {
        // Ignore close errors during shutdown.
    }
    try {
        await connection?.close();
    }
    catch {
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
