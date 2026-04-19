$ErrorActionPreference = "Stop"

# Load known connection settings for this project.
$env:SNOWFLAKE_ACCOUNT = "fqprtyy-mtc24161"
$env:SNOWFLAKE_USER = "THANAPON"
$env:SNOWFLAKE_ROLE = "ACCOUNTADMIN"
$env:SNOWFLAKE_WAREHOUSE = "COMPUTE_WH"
$env:SNOWFLAKE_DATABASE = "SMARTFACTORY_DB"
$env:SNOWFLAKE_SCHEMA = "RAW_DATA"

# Prompt for password without showing it on screen.
$securePassword = Read-Host "Snowflake password" -AsSecureString
$ptr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
try {
    $env:SNOWFLAKE_PASSWORD = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
}
finally {
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}

Write-Output "Snowflake environment variables are set for this terminal session."
Write-Output "ACCOUNT=$env:SNOWFLAKE_ACCOUNT"
Write-Output "USER=$env:SNOWFLAKE_USER"
Write-Output "ROLE=$env:SNOWFLAKE_ROLE"
Write-Output "WAREHOUSE=$env:SNOWFLAKE_WAREHOUSE"
Write-Output "DATABASE=$env:SNOWFLAKE_DATABASE"
Write-Output "SCHEMA=$env:SNOWFLAKE_SCHEMA"
