-- Phase 3 - Optional but recommended
-- Prepare MES source tables in PostgreSQL for Airflow extraction tasks.
-- POSTGRESQL ONLY: do not run this file in Snowflake.
-- Notes:
-- - Uses PostgreSQL-specific syntax/functions: TIMESTAMPTZ, NOW(), ON CONFLICT.
-- - If run in Snowflake, you may see: "Unknown function NOW".

CREATE TABLE IF NOT EXISTS machine_status (
    machine_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS work_orders (
    order_id TEXT PRIMARY KEY,
    machine_id TEXT NOT NULL,
    product_name TEXT NOT NULL,
    target_quantity INTEGER NOT NULL,
    order_status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed sample rows for initial pipeline validation.
INSERT INTO machine_status (machine_id, status, last_updated)
VALUES
    ('M-001', 'RUNNING', NOW()),
    ('M-002', 'IDLE', NOW()),
    ('M-003', 'MAINTENANCE', NOW())
ON CONFLICT (machine_id)
DO UPDATE SET
    status = EXCLUDED.status,
    last_updated = EXCLUDED.last_updated;

INSERT INTO work_orders (order_id, machine_id, product_name, target_quantity, order_status, created_at)
VALUES
    ('WO-1001', 'M-001', 'Widget-A', 5000, 'OPEN', NOW()),
    ('WO-1002', 'M-002', 'Widget-B', 2500, 'IN_PROGRESS', NOW()),
    ('WO-1003', 'M-003', 'Widget-C', 1200, 'PLANNED', NOW())
ON CONFLICT (order_id)
DO UPDATE SET
    machine_id = EXCLUDED.machine_id,
    product_name = EXCLUDED.product_name,
    target_quantity = EXCLUDED.target_quantity,
    order_status = EXCLUDED.order_status,
    created_at = EXCLUDED.created_at;
