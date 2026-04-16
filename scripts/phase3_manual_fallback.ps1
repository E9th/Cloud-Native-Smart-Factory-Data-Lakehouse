param(
    [Parameter(Mandatory = $true)]
    [string]$BucketName,

    [string]$MesPrefix = "mes-data",
    [string]$SnowflakeStage = "MY_SECURE_S3_STAGE",
    [string]$PostgresContainer = "postgres",
    [string]$PostgresUser = "smartfactory_user",
    [string]$PostgresDatabase = "smartfactory_db",
    [string]$OutputDir = ".tmp/phase3-manual"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Assert-CommandExists {
    param([Parameter(Mandatory = $true)][string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found in PATH."
    }
}

function Export-TableCsvFromPostgresContainer {
    param(
        [Parameter(Mandatory = $true)][string]$ContainerName,
        [Parameter(Mandatory = $true)][string]$DbUser,
        [Parameter(Mandatory = $true)][string]$Database,
        [Parameter(Mandatory = $true)][string]$SelectSql,
        [Parameter(Mandatory = $true)][string]$HostFilePath
    )

    $copySql = "COPY ($SelectSql) TO STDOUT WITH CSV HEADER"

    docker exec $ContainerName psql -q -U $DbUser -d $Database -v ON_ERROR_STOP=1 -c $copySql > $HostFilePath
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to export CSV from PostgreSQL container."
    }
}

Assert-CommandExists -Name "docker"
Assert-CommandExists -Name "aws"

aws sts get-caller-identity | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "AWS credentials are not configured. Run 'aws configure' first."
}

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$workOrdersFile = Join-Path $OutputDir "work_orders_$timestamp.csv"
$machineStatusFile = Join-Path $OutputDir "machine_status_$timestamp.csv"

Export-TableCsvFromPostgresContainer `
    -ContainerName $PostgresContainer `
    -DbUser $PostgresUser `
    -Database $PostgresDatabase `
    -SelectSql "SELECT order_id, machine_id, product_name, target_quantity, order_status, created_at FROM work_orders" `
    -HostFilePath $workOrdersFile

Export-TableCsvFromPostgresContainer `
    -ContainerName $PostgresContainer `
    -DbUser $PostgresUser `
    -Database $PostgresDatabase `
    -SelectSql "SELECT machine_id, status, last_updated FROM machine_status" `
    -HostFilePath $machineStatusFile

$workOrdersS3Key = "$MesPrefix/work_orders/work_orders_$timestamp.csv"
$machineStatusS3Key = "$MesPrefix/machine_status/machine_status_$timestamp.csv"

aws s3 cp $workOrdersFile "s3://$BucketName/$workOrdersS3Key"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to upload work_orders CSV to S3."
}

aws s3 cp $machineStatusFile "s3://$BucketName/$machineStatusS3Key"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to upload machine_status CSV to S3."
}

Write-Host "Uploaded files:" -ForegroundColor Green
Write-Host "- s3://$BucketName/$workOrdersS3Key"
Write-Host "- s3://$BucketName/$machineStatusS3Key"

$copySqlTemplate = @'
-- Run in Snowflake worksheet after S3 upload.
USE ROLE ACCOUNTADMIN;
USE WAREHOUSE COMPUTE_WH;
USE DATABASE SMARTFACTORY_DB;
USE SCHEMA RAW_DATA;

COPY INTO SMARTFACTORY_DB.RAW_DATA.WORK_ORDERS_RAW
  (ORDER_ID, MACHINE_ID, PRODUCT_NAME, TARGET_QUANTITY, ORDER_STATUS, CREATED_AT)
FROM (
  SELECT
    $1::STRING,
    $2::STRING,
    $3::STRING,
    TRY_TO_NUMBER($4::STRING),
    $5::STRING,
    TRY_TO_TIMESTAMP_NTZ($6::STRING)
  FROM @__SNOWFLAKE_STAGE__/__MES_PREFIX__/work_orders
)
FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '"')
PATTERN = '.*work_orders_.*\\.csv'
ON_ERROR = 'CONTINUE';

COPY INTO SMARTFACTORY_DB.RAW_DATA.MACHINE_STATUS_RAW
  (MACHINE_ID, STATUS, LAST_UPDATED)
FROM (
  SELECT
    $1::STRING,
    $2::STRING,
    TRY_TO_TIMESTAMP_NTZ($3::STRING)
  FROM @__SNOWFLAKE_STAGE__/__MES_PREFIX__/machine_status
)
FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '"')
PATTERN = '.*machine_status_.*\\.csv'
ON_ERROR = 'CONTINUE';
'@

$copySql = $copySqlTemplate.Replace("__SNOWFLAKE_STAGE__", $SnowflakeStage).Replace("__MES_PREFIX__", $MesPrefix)

Write-Host ""
Write-Host "Snowflake SQL to run next:" -ForegroundColor Yellow
Write-Host $copySql

Write-Host ""
Write-Host "Then run validation SQL: sql/snowflake/phase3_step5_validation_queries.sql" -ForegroundColor Cyan
