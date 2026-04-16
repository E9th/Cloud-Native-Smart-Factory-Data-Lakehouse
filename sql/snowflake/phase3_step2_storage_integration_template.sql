-- Phase 3 - Step 2
-- Secure S3 access using Storage Integration (recommended for production/interviews).
-- Values below are aligned with the current smartfactory AWS account setup.
-- IMPORTANT: Do not recreate S3_INT on every run, because ExternalId can change and break AWS trust policy.

USE ROLE ACCOUNTADMIN;
USE WAREHOUSE COMPUTE_WH;
USE DATABASE SMARTFACTORY_DB;
USE SCHEMA RAW_DATA;

-- 1) First-time setup only (run once if S3_INT does not exist):
-- SHOW STORAGE INTEGRATIONS LIKE 'S3_INT';
-- CREATE OR REPLACE STORAGE INTEGRATION S3_INT
--   TYPE = EXTERNAL_STAGE
--   STORAGE_PROVIDER = 'S3'
--   ENABLED = TRUE
--   STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::319627300527:role/snowflake-s3-int-role'
--   STORAGE_ALLOWED_LOCATIONS = ('s3://smartfactory-datalake-dev-319627300527-us-east-1-an/');

-- 1b) Normal rerun path (safe): keep existing integration and only ensure it is enabled
ALTER STORAGE INTEGRATION S3_INT SET ENABLED = TRUE;

-- 2) Get Snowflake IAM user + external id and add them to the AWS role trust policy
DESC STORAGE INTEGRATION S3_INT;

-- 2b) Verify these values from DESC match AWS trust policy exactly:
-- - STORAGE_AWS_IAM_USER_ARN
-- - STORAGE_AWS_EXTERNAL_ID
-- If either value differs, update AWS role trust policy first, then retry LIST.

-- 3) Optional: dedicated file formats
CREATE OR REPLACE FILE FORMAT FF_SENSOR_JSON
  TYPE = JSON
  STRIP_OUTER_ARRAY = TRUE;

CREATE OR REPLACE FILE FORMAT FF_MES_CSV
  TYPE = CSV
  SKIP_HEADER = 1
  FIELD_OPTIONALLY_ENCLOSED_BY = '"';

-- 4) Create secure stage
CREATE OR REPLACE STAGE MY_SECURE_S3_STAGE
  STORAGE_INTEGRATION = S3_INT
  URL = 's3://smartfactory-datalake-dev-319627300527-us-east-1-an/';

-- 5) Verify access
LIST @MY_SECURE_S3_STAGE;

-- IMPORTANT:
-- If Step 5 fails with AssumeRole, re-check AWS trust policy values from DESC STORAGE INTEGRATION.
-- If Step 5 fails with AccessDenied on ListBucket, add s3:ListBucket and s3:GetObject to the IAM role permissions policy.
