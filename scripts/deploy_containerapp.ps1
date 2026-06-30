<#
.SYNOPSIS
    Build and deploy the FinSight gateway to Azure Container Apps.
.DESCRIPTION
    Creates an Azure Container Registry, builds the gateway image in the cloud
    (no local Docker), creates a Container Apps environment, and deploys the
    gateway with scale-to-zero. Azure OpenAI endpoint/key come from Azure; the
    Pinecone key is read from your local .env. Secrets are stored as Container
    App secrets, not plaintext env vars.

    Run `az login` first.
.EXAMPLE
    ./scripts/deploy_containerapp.ps1
#>
[CmdletBinding()]
param(
    [string]$SubscriptionId = "",
    [string]$ResourceGroup = "finsight-rg",
    [string]$Location = "centralindia",
    [string]$ImageTag = "latest"
)

$ErrorActionPreference = "Stop"
$tag = "project=finsight"

if (-not $SubscriptionId) { $SubscriptionId = az account show --query id -o tsv }
$suffix = $SubscriptionId.Replace("-", "").Substring(0, 6).ToLower()

$AcrName    = "finsightacr$suffix"
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

Step "Azure Container Registry $AcrName"
az acr create -n $AcrName -g $ResourceGroup --sku Basic --admin-enabled true --tags $tag | Out-Null
$acrServer = az acr show -n $AcrName --query loginServer -o tsv

Step "Building gateway image in the cloud (az acr build)"
az acr build -r $AcrName -t "finsight-gateway:$ImageTag" -f services/gateway/Dockerfile . | Out-Null

Step "Container Apps environment $EnvName ($Location)"
az containerapp env create -n $EnvName -g $ResourceGroup --location $Location --tags $tag | Out-Null

$acrUser = az acr credential show -n $AcrName --query username -o tsv
$acrPass = az acr credential show -n $AcrName --query "passwords[0].value" -o tsv

Step "Deploying container app $AppName (scale-to-zero)"
az containerapp create -n $AppName -g $ResourceGroup `
    --environment $EnvName `
    --image "$acrServer/finsight-gateway:$ImageTag" `
    --registry-server $acrServer --registry-username $acrUser --registry-password $acrPass `
    --target-port 8000 --ingress external `
    --min-replicas 0 --max-replicas 2 `
    --secrets "aoai-key=$aoaiKey" "pinecone-key=$pineconeKey" `
    --env-vars `
    "FINSIGHT_ENVIRONMENT=production" `
    "FINSIGHT_AZURE_OPENAI_ENDPOINT=$endpoint" `
    "FINSIGHT_AZURE_OPENAI_API_KEY=secretref:aoai-key" `
    "FINSIGHT_AZURE_OPENAI_API_VERSION=2024-10-21" `
    "FINSIGHT_AZURE_OPENAI_CHAT_DEPLOYMENT=chat" `
    "FINSIGHT_AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=embeddings" `
    "FINSIGHT_PINECONE_API_KEY=secretref:pinecone-key" `
    "FINSIGHT_PINECONE_INDEX=finsight" `
    "FINSIGHT_PINECONE_CLOUD=aws" `
    "FINSIGHT_PINECONE_REGION=us-east-1" `
    --tags $tag | Out-Null

$fqdn = az containerapp show -n $AppName -g $ResourceGroup --query properties.configuration.ingress.fqdn -o tsv
Write-Host "`n=== Gateway is live ===" -ForegroundColor Green
Write-Host "URL:    https://$fqdn"
Write-Host "Health: https://$fqdn/healthz"
Write-Host "`nPoint the Vercel frontend at it:" -ForegroundColor Yellow
Write-Host "  NEXT_PUBLIC_API_URL=https://$fqdn"
