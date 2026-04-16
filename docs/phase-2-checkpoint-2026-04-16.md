# Phase 2 Checkpoint (2026-04-16)

## 1) Executive Summary
สถานะโปรเจกต์พร้อมเริ่ม Phase 3 ในแกน Data Platform แล้ว โดย pipeline หลักทำงานได้จริงตั้งแต่ API -> RabbitMQ -> S3 -> Snowflake (โหลดเข้า RAW table สำเร็จ)

สิ่งที่ยืนยันแล้ว:
- มี API สำหรับรับข้อมูลเซ็นเซอร์และส่งเข้า RabbitMQ
- มี Dashboard endpoint สำหรับดูภาพรวมข้อมูลล่าสุด
- มี Python consumer batch ขึ้น S3 พร้อม partition ตามวัน
- มี Snowflake table และโหลดข้อมูลจาก S3 เข้าได้สำเร็จ
- มีผล k6 ล่าสุดสำหรับ baseline performance

## 2) Current System Status

### Infrastructure
- Docker services ที่ใช้งาน: RabbitMQ, PostgreSQL
- สถานะล่าสุด: Up ทั้งคู่
- RabbitMQ: host port 5672, management UI 15672
- PostgreSQL: host port 5433

### TypeScript Services
- Sensor Generator: ส่งข้อความเข้า RabbitMQ แบบต่อเนื่อง
- API Server: รับ HTTP แล้ว publish เข้า RabbitMQ
- Dashboard: เสิร์ฟ static UI และ endpoint สรุปข้อมูล

### Python Ingestion
- Consumer อ่านจาก queue, batch ตามจำนวนหรือเวลา
- Flush condition:
  - BATCH_SIZE = 10000
  - FLUSH_INTERVAL_SECONDS = 300
- เขียนไฟล์ json/csv ชั่วคราว แล้ว upload ไป S3

### Snowflake
- Warehouse/Database/Schema ถูกตั้งค่าและใช้งานได้
- RAW table: SMARTFACTORY_DB.RAW_DATA.SENSOR_DATA_RAW
- COPY INTO จาก S3 stage ทำงานได้ (หลังแก้ mapping/typing ของ JSON)

## 3) API Inventory (Current)

### Health Check
- Method: GET
- Path: /health
- Purpose: ตรวจสถานะ API และ RabbitMQ connection
- ตัวอย่างข้อมูลที่คืน (ล่าสุดหลังรัน k6):
  - status: ok
  - rabbitmq_connected: true
  - total_received: 37303
  - total_published: 37303

### Ingestion Endpoint
- Method: POST
- Path: /api/sensor-data
- Purpose: รับ sensor payload แล้ว publish เข้า queue
- Success status: 202
- Validation: machine_id ต้องเป็น string, temperature/vibration ต้องเป็น number, timestamp เป็น optional

### Dashboard Data Endpoint
- Method: GET
- Path: /api/dashboard
- Purpose: ดู latest per machine + recent messages + counters

### Static Dashboard UI
- Path: /
- Source: public/index.html

## 4) k6 Test Result (Latest Baseline)

### Test Profile
- Script: k6/sensor-load-test.js
- Scenario: constant-vus
- Load: 1000 VUs
- Duration: 1 minute
- Endpoint under test: POST /api/sensor-data
- Command: k6 run k6/sensor-load-test.js

### Threshold Config
- http_req_failed: rate < 0.02
- http_req_duration: p(95) < 1000ms
- checks: rate > 0.98

### Actual Result
- iterations/http_reqs: 38,831
- checks passed: 96.06% (37,303/38,831)
- http_req_failed: 3.93% (1,528 requests)
- http_req_duration:
  - avg: 557.67ms
  - p(90): 854.49ms
  - p(95): 1.06s
  - max: 6.58s
- Command exit code: 1 (threshold crossed)

### Interpretation
- ระบบรับโหลดได้ระดับหนึ่ง แต่ยังไม่ผ่าน target SLO ตาม threshold ที่ตั้งไว้
- มีช่วงที่เกิด connection refused ต่อ localhost:3000 ระหว่างทดสอบ ทำให้ error rate สูงขึ้น
- ควรทำ performance hardening ของ API/RabbitMQ path ก่อนใช้ profile 1000 VUs เป็นเกณฑ์ผ่าน

## 5) What Is Already Achieved (Phase 2)
- เข้าใจ Snowflake core architecture และใช้งาน worksheet ได้
- ตั้งค่า compute/db/schema/table สำเร็จ
- โหลดข้อมูลจาก S3 -> Snowflake RAW table สำเร็จ
- ตรวจสอบข้อมูลใน table ได้จริง
- ได้ baseline k6 สำหรับใช้เปรียบเทียบหลัง optimization

## 6) Gaps Before/At Start of Phase 3
- Security hardening Snowflake stage:
  - ยังใช้ key-based credential
  - ควรย้ายไป Storage Integration (IAM role)
- Reliability under high load:
  - ต้องลด request failure ให้ต่ำกว่า 2%
  - ต้องกด p95 ให้ต่ำกว่า 1s อย่างสม่ำเสมอ
- Observability:
  - เพิ่มการเก็บ log/metrics แบบแยกสาเหตุ latency และ publish failures

## 7) Recommended Entry Plan for Phase 3
1. ทำ Snowflake security baseline ให้เรียบร้อย (Storage Integration)
2. ตั้ง auto-ingest (Snowpipe) สำหรับ near real-time pipeline
3. ทำ API performance tuning และ re-run k6 (รอบ baseline/round 2)
4. เพิ่ม monitoring queries และ operational runbook
5. สรุปผลก่อนเริ่มงาน transformation/serving layer

## 8) Evidence References (Code)
- API server: src/api-server.ts
- Sensor generator: src/sensor-generator.ts
- Load test script: k6/sensor-load-test.js
- S3 consumer: python/s3_consumer.py
- Docker services: docker-compose.yml
- Existing project overview: README.md

---
Document owner: Project checkpoint generated before Phase 3 kickoff
Date: 2026-04-16
