# Executive One-Pager (TH)

โครงการ: Cloud-Native Smart Factory Data Lakehouse
วันที่: 2026-04-19
สถานะ: Project Completed

## 1) Problem

โรงงานต้องการมองเห็นความเสี่ยงเครื่องจักรและสถานะงานแบบทันเวลา แต่ข้อมูลกระจัดกระจายในหลายระบบ (IoT stream, MES, raw files) ทำให้ตัดสินใจเชิงปฏิบัติการช้า

## 2) Solution

พัฒนา data platform แบบ end-to-end บนแนวทาง cloud-native:
- รับข้อมูลเซ็นเซอร์ผ่าน API/Queue
- ลงข้อมูลดิบที่ S3 และโหลดเข้า Snowflake RAW
- แปลงข้อมูลด้วย dbt เป็นมุมมองเชิงธุรกิจ
- วิเคราะห์เชิงลึกด้วย Python (baseline, breach, risk score)
- สร้าง Power BI Dashboard สำหรับการตัดสินใจรายชั่วโมง

## 3) End-to-End Process

Telemetry -> RabbitMQ -> S3 -> Snowflake RAW -> dbt Staging/Marts -> Python EDA -> Power BI

ผลลัพธ์หลักในชั้นข้อมูล:
- fct_machine_health_hourly
- fct_work_orders_status
- fct_machine_risk_hourly

## 4) Business Value

- มองเห็นเครื่องที่มีความเสี่ยงสูงก่อนเกิดเหตุรุนแรง
- จัดลำดับงานซ่อมบำรุงตาม risk score
- ติดตามสถานะเครื่องและ work orders ในหน้าเดียว
- ลดเวลาค้นหาปัญหาข้ามหลายระบบ

## 5) Key Technical Outcomes

- Pipeline ทำงานได้ end-to-end จริง
- dbt tests ผ่านสำหรับโมเดลหลักและกฎคุณภาพข้อมูล
- สร้าง risk model รายชั่วโมงพร้อมระดับ LOW/MEDIUM/HIGH
- สร้าง EDA artifacts สำหรับอธิบายเชิงเทคนิคและเชิงธุรกิจ
- Dashboard พร้อมเดโมและใช้งานนำเสนอ

## 6) Issues Handled During Delivery

- แก้ปัญหา IAM/Snowflake stage permissions
- มี fallback flow เมื่อ Airflow runtime ติดข้อจำกัดเครือข่าย
- แก้ parser/deprecation ใน dbt test syntax
- แก้ Power BI slicer propagation ด้วย Dim_HOUR
- แก้ KPI blank behavior ด้วย measure fallback (COALESCE)

## 7) Tech Stack at a Glance

- Ingestion/API: Node.js, TypeScript, Express, RabbitMQ
- Batch + Data Lake: Python, pika, boto3, AWS S3
- Warehouse + Transform: Snowflake, dbt
- Analytics + BI: pandas, matplotlib, seaborn, Power BI
- Orchestration + Infra: Airflow, Docker Compose
- Performance test: k6

## 8) Final Status

โครงการเสร็จสมบูรณ์ในระดับ Portfolio/Interview-ready โดยมีเอกสาร runbook, summary, completion report และ dashboard ที่ใช้งานจริงครบถ้วน

เอกสารอ้างอิงหลัก:
- docs/project-completion-report.md
- docs/project-completion-report.th.md
- docs/phase-4-analytics-final.md
