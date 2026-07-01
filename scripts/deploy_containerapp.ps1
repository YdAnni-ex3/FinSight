<#
.SYNOPSIS
    Deploy the FinSight gateway to Azure Container Apps from the public GHCR image.
.DESCRIPTION
    The image is built by the 'Build gateway image' GitHub Actions workflow and
    published to ghcr.io. This script creates (or updates) the Container Apps
    environment and the gateway app with scale-to-zero. Azure OpenAI endpoint/key
    come from Azure; the Pinecone key is read from your local .env. Secrets are
    stored as Container App secrets, not plaintext env vars.

    Run `az login` first, and make the GHCR package public once.
.EXAMPLE
    ./scripts/deploy_containerapp.ps1
#>
[CmdletBinding()]
param(
    [string]$SubscriptionId = "",
    [string]$ResourceGroup = "finsight-rg",
    [string]$Location = "centralindia",
    [string]$Image = "ghcr.io/ydanni-ex3/finsight-gateway:latest"
)

# Container Apps + az emit progress/warnings to stderr; don't treat those as fatal.
$ErrorActionPreference = "Continue"
$tag = "project=finsight"

if (-not $SubscriptionId) { $SubscriptionId = az account show --query id -o tsv }
$suffix = $SubscriptionId.Replace("-", "").Substring(0, 6).ToLower()

$EnvName    = "finsight-env"
$AppName    = "finsight-gateway"
$OpenAiName = "finsight-openai-$suffix"

function Step($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }

# Auto-install the containerapp extension without prompting.
az config set extension.use_dynamic_install=yes_without_prompt | Out-Null
az account set --subscription $SubscriptionId

# Config + secrets: endpoint/key from Azure, Pinecone key from .env.
$endpoint = az cognitiveservices account show -n $OpenAiName -g $ResourceGroup --query properties.endpoint -o tsv
$aoaiKey = az cognitiveservices account keys list -n $OpenAiName -g $ResourceGroup --query key1 -o tsv
$pineconeKey = (Select-String -Path .env -Pattern '^FINSIGHT_PINECONE_API_KEY=(.*)$').Matches.Groups[1].Value
if (-not $pineconeKey) { throw "FINSIGHT_PINECONE_API_KEY not found in .env" }

function Read-Env($name) { (Select-String -Path .env -Pattern "^$name=(.*)$").Matches.Groups[1].Value }
$sfAccount = Read-Env "FINSIGHT_SNOWFLAKE_ACCOUNT"
$sfUser = Read-Env "FINSIGHT_SNOWFLAKE_USER"
$sfPassword = Read-Env "FINSIGHT_SNOWFLAKE_PASSWORD"

$secrets = @("aoai-key=$aoaiKey", "pinecone-key=$pineconeKey")
$envVars = @(
    "FINSIGHT_ENVIRONMENT=production",
    "FINSIGHT_AZURE_OPENAI_ENDPOINT=$endpoint",
    "FINSIGHT_AZURE_OPENAI_API_KEY=secretref:aoai-key",
    "FINSIGHT_AZURE_OPENAI_API_VERSION=2024-10-21",
    "FINSIGHT_AZURE_OPENAI_CHAT_DEPLOYMENT=chat",
    "FINSIGHT_AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=embeddings",
    "FINSIGHT_PINECONE_API_KEY=secretref:pinecone-key",
    "FINSIGHT_PINECONE_INDEX=finsight",
    "FINSIGHT_PINECONE_CLOUD=aws",
    "FINSIGHT_PINECONE_REGION=us-east-1",
    "FINSIGHT_CORS_ORIGINS=https://finsight-woad-beta.vercel.app",
    "FINSIGHT_CORS_ORIGIN_REGEX=https://finsight.*\.vercel\.app"
)

if ($sfAccount -and $sfUser -and $sfPassword) {
    Write-Host "Snowflake: configured -> persistent star-schema store" -ForegroundColor Green
    $secrets += "snowflake-password=$sfPassword"
    $envVars += @(
        "FINSIGHT_SNOWFLAKE_ACCOUNT=$sfAccount",
        "FINSIGHT_SNOWFLAKE_USER=$sfUser",
        "FINSIGHT_SNOWFLAKE_PASSWORD=secretref:snowflake-password",
        "FINSIGHT_SNOWFLAKE_WAREHOUSE=COMPUTE_WH",
        "FINSIGHT_SNOWFLAKE_DATABASE=FINSIGHT",
        "FINSIGHT_SNOWFLAKE_SCHEMA=ANALYTICS"
    )
}
else {
    Write-Host "Snowflake: not configured -> in-memory store" -ForegroundColor Yellow
}

Step "Container Apps environment $EnvName ($Location)"
$envExists = az containerapp env show -n $EnvName -g $ResourceGroup --query name -o tsv 2>$null
$appExists = az containerapp show -n $AppName -g $ResourceGroup --query name -o tsv 2>$null

if (-not $envExists) {
    az containerapp env create -n $EnvName -g $ResourceGroup --location $Location --tags $tag | Out-Null
}

if ($appExists) {    Step "Updating container app $AppName"
    az containerapp secret set -n $AppName -g $ResourceGroup --secrets $secrets | Out-Null
    az containerapp update -n $AppName -g $ResourceGroup --image $Image --set-env-vars $envVars | Out-Null
}
else {
    Step "Creating container app $AppName (scale-to-zero)"
    az containerapp create -n $AppName -g $ResourceGroup `
        --environment $EnvName --image $Image `
        --target-port 8000 --ingress external `
        --min-replicas 0 --max-replicas 2 `
        --secrets $secrets `
        --env-vars $envVars `
        --tags $tag | Out-Null
}

$fqdn = az containerapp show -n $AppName -g $ResourceGroup --query properties.configuration.ingress.fqdn -o tsv
Write-Host "`n=== Gateway is live ===" -ForegroundColor Green
Write-Host "URL:    https://$fqdn"
Write-Host "Health: https://$fqdn/healthz"
Write-Host "`nPoint the Vercel frontend at it:" -ForegroundColor Yellow
Write-Host "  NEXT_PUBLIC_API_URL=https://$fqdn"
