# Runs Grafana Alloy locally (no Docker) to ship the live gateway's /metrics to
# Grafana Cloud. Reads GRAFANA_CLOUD_* + GATEWAY_METRICS_* from .env, downloads
# the Alloy binary on first run, then scrapes + remote_writes using
# observability/alloy/config.alloy.
#
# Usage:  ./scripts/run_alloy.ps1        (Ctrl+C to stop)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

# 1) Load the Grafana Cloud + gateway vars from .env into this process.
$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) {
    throw ".env not found. Copy .env.example to .env and fill the GRAFANA_CLOUD_* values."
}
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$') {
        $name = $Matches[1]
        $value = $Matches[2].Trim('"')
        if ($name -like 'GRAFANA_CLOUD_*' -or $name -like 'GATEWAY_METRICS_*') {
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

foreach ($key in 'GRAFANA_CLOUD_PROM_URL', 'GRAFANA_CLOUD_PROM_USER', 'GRAFANA_CLOUD_API_KEY') {
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($key))) {
        throw "$key is empty in .env. Fill it from Grafana Cloud -> Prometheus -> Send Metrics."
    }
}

# 2) Download the Alloy binary on first run (into .tools/, which is gitignored).
$tools = Join-Path $root ".tools"
$alloy = Join-Path $tools "alloy-windows-amd64.exe"
if (-not (Test-Path $alloy)) {
    New-Item -ItemType Directory -Force -Path $tools | Out-Null
    $version = (Invoke-RestMethod "https://api.github.com/repos/grafana/alloy/releases/latest").tag_name
    $asset = "https://github.com/grafana/alloy/releases/download/$version/alloy-windows-amd64.exe.zip"
    $zip = Join-Path $tools "alloy.zip"
    Write-Host "Downloading Grafana Alloy $version ..."
    Invoke-WebRequest $asset -OutFile $zip
    Expand-Archive $zip -DestinationPath $tools -Force
    Remove-Item $zip
}

# 3) Run Alloy with the committed config (scrapes the gateway, ships to Grafana Cloud).
$config = Join-Path $root "observability\alloy\config.alloy"
Write-Host "Starting Alloy. Scraping the gateway and shipping to Grafana Cloud. Ctrl+C to stop."
Write-Host "Local Alloy UI: http://localhost:12345"
& $alloy run $config
