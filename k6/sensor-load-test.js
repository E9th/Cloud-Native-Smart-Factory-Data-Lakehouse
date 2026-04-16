import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  scenarios: {
    machine_load: {
      executor: "constant-vus",
      vus: 1000,
      duration: "1m"
    }
  },
  thresholds: {
    http_req_failed: ["rate<0.02"],
    http_req_duration: ["p(95)<1000"],
    checks: ["rate>0.98"]
  }
};

const baseUrl = __ENV.BASE_URL || "http://localhost:3000";
const endpoint = `${baseUrl}/api/sensor-data`;

function randomBetween(min, max) {
  return Math.round((Math.random() * (max - min) + min) * 100) / 100;
}

export default function () {
  const machineNumber = String(__VU).padStart(4, "0");
  const payload = {
    timestamp: new Date().toISOString(),
    machine_id: `M-${machineNumber}`,
    temperature: randomBetween(70, 95),
    vibration: randomBetween(0.2, 2.5)
  };

  const res = http.post(endpoint, JSON.stringify(payload), {
    headers: {
      "Content-Type": "application/json"
    }
  });

  check(res, {
    "status is 202": (r) => r.status === 202
  });

  // Simulate each machine sending every second during the test window.
  sleep(1);
}