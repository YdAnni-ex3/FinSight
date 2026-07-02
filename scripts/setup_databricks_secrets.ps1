# Create the Databricks 'finsight' secret scope + Snowflake secrets for the
# gold -> Snowflake publish (03_gold_star notebook).
#
# Usage (set env first, then run):
#   $env:DATABRICKS_HOST  = "https://<workspace>.cloud.databricks.com"
#   $env:DATABRICKS_TOKEN = "<your Databricks PAT>"
#   ./scripts/setup_databricks_secrets.ps1
#
# Reads the Snowflake values from .env; no secrets are stored in this file.

$ErrorActionPreference = "Stop"

if (-not $env:DATABRICKS_HOST -or -not $env:DATABRICKS_TOKEN) {
    throw "Set DATABRICKS_HOST and DATABRICKS_TOKEN environment variables first."
}

$base = "$($env:DATABRICKS_HOST.TrimEnd('/'))/api/2.0"
$headers = @{ Authorization = "Bearer $($env:DATABRICKS_TOKEN)" }
function Read-Env($name) { (Select-String -Path .env -Pattern "^$name=(.*)$").Matches.Groups[1].Value }

try {
    Invoke-RestMethod -Method Post -Uri "$base/secrets/scopes/create" -Headers $headers `
        -ContentType "application/json" -Body '{"scope":"finsight"}' | Out-Null
    Write-Host "scope 'finsight' created"
}
catch {
    Write-Host "scope: $($_.Exception.Message) (ok if it already exists)"
}

$secrets = [ordered]@{
    sf_account  = Read-Env "FINSIGHT_SNOWFLAKE_ACCOUNT"
    sf_user     = Read-Env "FINSIGHT_SNOWFLAKE_USER"
    sf_password = Read-Env "FINSIGHT_SNOWFLAKE_PASSWORD"
}
foreach ($key in $secrets.Keys) {
    $body = @{ scope = "finsight"; key = $key; string_value = $secrets[$key] } | ConvertTo-Json
    Invoke-RestMethod -Method Post -Uri "$base/secrets/put" -Headers $headers `
        -ContentType "application/json" -Body $body | Out-Null
    Write-Host "put secret: $key"
}

Write-Host "--- keys in scope 'finsight' ---"
(Invoke-RestMethod -Method Get -Uri "$base/secrets/list?scope=finsight" -Headers $headers).secrets |
    ForEach-Object { $_.key }
