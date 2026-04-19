# รายงานปิดโครงการ

วันที่: 2026-04-19
โครงการ: Cloud-Native Smart Factory Data Lakehouse
สถานะ: เสร็จสมบูรณ์

## 1) สรุปผู้บริหาร

โครงการนี้พัฒนาระบบข้อมูลโรงงานแบบ Cloud-Native แบบครบวงจร ตั้งแต่การรับข้อมูลเซ็นเซอร์ การจัดเก็บใน Data Lake การโหลดเข้า Data Warehouse การแปลงข้อมูลเชิงธุรกิจ จนถึงการวิเคราะห์และแสดงผลบน Dashboard

ผลงานที่ส่งมอบสำเร็จ:
- ระบบรับข้อมูลจาก IoT ผ่าน API และ Queue
- ระบบ Batch Upload จาก RabbitMQ ไป S3 แบบแบ่งพาร์ทิชัน
- โครงสร้าง Snowflake RAW และกระบวนการโหลดข้อมูล
- โมเดล dbt (staging/marts) พร้อม data quality tests
- Python analytics สำหรับ baseline, breach detection, risk scoring
- Power BI Dashboard สำหรับ KPI ด้านปฏิบัติการ

## 2) End-to-End Workflow

### 2.1 Ingestion Layer

1. สร้างหรือรับข้อมูลเซ็นเซอร์จาก 2 ทาง:
- TypeScript Sensor Generator
- HTTP API: POST /api/sensor-data

2. ตรวจสอบรูปแบบข้อมูล แล้ว publish เข้า RabbitMQ queue `sensor_data_queue`

3. API มี endpoint สำหรับปฏิบัติการ:
- GET /health
- GET /api/dashboard

โครงสร้างข้อมูลหลัก:
- timestamp
- machine_id
- temperature
- vibration

### 2.2 Landing Layer (Queue -> S3)

1. Python consumer อ่านข้อมูลจาก RabbitMQ
2. รวมข้อมูลแบบ batch ตามเงื่อนไข:
- ครบจำนวน `BATCH_SIZE`
- ครบเวลา `FLUSH_INTERVAL_SECONDS`

3. เขียนไฟล์ชั่วคราว (JSON/CSV) และอัปโหลดเข้า S3
4. รูปแบบ path บน S3:
- `sensor-data/year=YYYY/month=MM/day=DD/...`

### 2.3 RAW Layer (Snowflake)

1. โหลดข้อมูลจาก S3 เข้า Snowflake RAW tables ด้วย COPY INTO
2. ข้อมูล MES วิ่งจาก PostgreSQL -> S3 -> Snowflake
3. การ orchestration:
- เส้นทางหลัก: Airflow DAG
- เส้นทางสำรอง: PowerShell fallback script

### 2.4 Transformation Layer (dbt)

1. ประกาศ source จาก RAW_DATA
2. staging models ทำความสะอาดและมาตรฐานข้อมูล:
- trim/nullif
- normalize keys
- deduplicate rows

3. marts models หลัก:
- fct_machine_health_hourly
- fct_work_orders_status
- fct_machine_risk_hourly

4. dbt tests หลัก:
- not_null
- unique
- accepted_values
- custom test: risk score อยู่ในช่วง 0-100

### 2.5 Analytics Layer (Python EDA)

1. ดึงข้อมูลจาก Snowflake
2. สร้างฟีเจอร์รายชั่วโมง (rolling mean/std, rate of change, anomaly rate)
3. คำนวณ baseline รายเครื่อง (p95)
4. ตรวจจับ sustained breach
5. คำนวณ risk score และจัดอันดับเครื่องจักร
6. ส่งออก artifact สำหรับพรีเซนต์

### 2.6 BI Layer (Power BI)

1. เชื่อม Snowflake marts
2. สร้าง KPI cards, trend charts, risk ranking
3. ตั้งค่า slicer และ interaction ให้ filter ไหลครบทุก visual
4. ใช้ Dim_HOUR เป็น time dimension กลาง เพื่อควบคุมการกรองข้ามหลาย fact tables

## 3) สรุปการทำงานตามเฟส

### Phase 2: Foundation

ส่งมอบ:
- API/Generator -> RabbitMQ
- Queue consumer -> S3
- Snowflake RAW load สำเร็จ
- k6 baseline test

ผลลัพธ์:
- ระบบทำงานได้จริงแบบ end-to-end ระดับ baseline
- ระบุ performance gap และ reliability gap ได้ชัดเจน

### Phase 3: Secure Bridge + Orchestration

ส่งมอบ:
- Snowflake storage integration + secure stage
- MES bridge: PostgreSQL -> S3 -> Snowflake
- Airflow DAG assets
- fallback script ใช้งานจริงเมื่อ Airflow runtime ติดข้อจำกัด

ผลลัพธ์:
- งานขนข้อมูลไป RAW สำเร็จ แม้มีข้อจำกัดด้าน runtime

### Phase 4: Analytics + Dashboard

ส่งมอบ:
- dbt staging/marts พร้อม tests
- risk model รายชั่วโมง
- EDA outputs และ ranking files
- Dashboard KPI พร้อมใช้งาน

ผลลัพธ์:
- ได้ analytics layer ที่พร้อมนำเสนอผลงาน

## 4) Tech Stack และเหตุผลการใช้งาน

| ส่วนงาน | Tech Stack | ใช้เพื่ออะไร |
|---|---|---|
| Producer/API | TypeScript, Node.js, Express | สร้างบริการรับ/ส่งข้อมูลที่เร็วและปลอดภัยเชิงโครงสร้างข้อมูล |
| Message Broker | RabbitMQ | แยก producer/consumer ลดการกระชากโหลด |
| Batch Worker | Python, pika, boto3 | อ่าน queue และอัปโหลดไฟล์เข้า S3 แบบควบคุมได้ |
| Data Lake | AWS S3 | เก็บข้อมูลดิบแบบพาร์ทิชัน |
| Data Warehouse | Snowflake | วิเคราะห์ข้อมูลด้วย SQL และแยก RAW/Analytics ชัดเจน |
| Transformation | dbt | จัดการโมเดล SQL, lineage และ tests แบบ versioned |
| Orchestration | Airflow | กำหนดลำดับงาน ETL เชิงตารางเวลา |
| BI | Power BI | แสดง KPI และ dashboard เชิงธุรกิจ |
| EDA | pandas, matplotlib, seaborn | วิเคราะห์เชิงสำรวจและสร้างภาพประกอบ |
| Performance Test | k6 | วัดโหลด API และ baseline SLO |

## 5) ปัญหาที่พบและวิธีแก้

### 5.1 Platform/Ingestion

ปัญหา: API ไม่ผ่าน threshold ที่ 1000 VUs อย่างสม่ำเสมอ
- อาการ: error rate และ p95 latency สูงเกินเป้า
- วิธีแก้: จัด baseline ให้ชัด แยกงาน tuning ออกจาก milestone เชิง functional

ปัญหา: Snowflake AssumeRole/AccessDenied
- อาการ: stage list/read ไม่ผ่าน
- วิธีแก้: แก้ IAM trust policy และสิทธิ์ตามค่าใน DESC STORAGE INTEGRATION

ปัญหา: รัน SQL คนละ engine
- อาการ: PostgreSQL SQL ไปรันใน Snowflake แล้ว error
- วิธีแก้: แยก runbook ตาม execution engine ชัดเจน

ปัญหา: ดึงภาพ Airflow ไม่ผ่าน (EOF/network)
- อาการ: เปิด local Airflow ไม่สำเร็จ
- วิธีแก้: ใช้ fallback script เพื่อส่งงานต่อและ validate ใน Snowflake

### 5.2 dbt

ปัญหา: source not found (dbt1005)
- วิธีแก้: แก้ชื่อ source, identifier และ YAML indentation

ปัญหา: test not_null/unique ล้มเหลว
- วิธีแก้: เพิ่ม normalization และ dedup logic ใน staging

ปัญหา: dbt parser/deprecation
- อาการ: accepted_values รูปแบบเก่า
- วิธีแก้: ปรับเป็น `accepted_values.arguments.values`

### 5.3 BI/Analytics

ปัญหา: ตารางใน Power BI ไม่ขึ้นตามที่คาด
- วิธีแก้: โหลดจาก schema เป้าหมายจริงของ dbt run

ปัญหา: slicer กระทบ KPI ไม่ครบ
- วิธีแก้: ใช้ Dim_HOUR กลางและตั้ง interaction/filter ให้ถูกต้อง

ปัญหา: KPI เป็น Blank/0
- วิธีแก้: แยกความหมาย Blank กับ 0, ปรับ measure ด้วย COALESCE และตรวจช่วงข้อมูล mock

## 6) รายการส่งมอบสุดท้าย

- Ingestion services: src/api-server.ts, src/sensor-generator.ts
- Queue consumer: python/s3_consumer.py
- dbt models/tests: models/, tests/
- EDA script: python/phase4_eda_template.py
- Orchestration/fallback: airflow/, scripts/phase3_manual_fallback.ps1
- Project docs: docs/phase-*.md
- เอกสารปิดโครงการภาษาอังกฤษ: docs/project-completion-report.md
- เอกสารปิดโครงการภาษาไทย: docs/project-completion-report.th.md

## 7) เกณฑ์ปิดโครงการ

โครงการถือว่าเสร็จสมบูรณ์ เพราะ:
- มี workflow end-to-end ใช้งานจริง
- มี dbt models และ tests ครบสำหรับแกน analytics
- มี EDA artifacts และ risk outputs สำหรับอธิบายเชิงธุรกิจ
- มี Power BI dashboard ที่เชื่อมข้อมูลจริงจาก transformed layer
- มีเอกสาร runbook + summary + completion report ครบ

## 8) ข้อจำกัดที่ยังเหลือ

- ข้อมูล mock มีความหนาแน่นเวลาไม่มาก ทำให้บาง KPI ขยับน้อยหรือเป็น 0/blank ในบางช่วง
- High risk อาจเป็น 0 หากไม่มี HIGH rows ในช่วงเวลาที่ filter
- OEE ปัจจุบันยังเป็น availability proxy เนื่องจากยังไม่มี quality/performance fields ครบ

## 9) แนวทางพัฒนาต่อ

1. เพิ่ม field สำหรับ OEE เต็มรูปแบบ (good/reject/planned/runtime)
2. เพิ่มชุดข้อมูลจำลองที่มีเหตุการณ์เสี่ยงหลากหลายขึ้น
3. เพิ่มงานตรวจสุขภาพรายวันของ data pipeline แบบอัตโนมัติ
4. เพิ่ม regression checks สำหรับ DAX สำคัญ

## 10) ข้อความปิดโครงการ

โครงการนี้เสร็จสมบูรณ์ในระดับ portfolio-ready โดยแสดงความสามารถด้าน data engineering และ analytics ตั้งแต่ ingestion จนถึง decision-support dashboard ภายใต้ข้อจำกัดจริงของระบบและโครงสร้างพื้นฐาน
