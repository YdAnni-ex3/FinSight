<#
.SYNOPSIS
    Provision the Azure resources FinSight needs for Phase 2.

.DESCRIPTION
    Creates (idempotently): a resource group, a storage account with the
    'raw-statements' blob container, a Key Vault, an Azure OpenAI (Foundry)
    account, and two model deployments (chat + embeddings). Then prints the
    values to drop into your .env (or pushes them into Key Vault).

    Run `az login` FIRST. This uses YOUR subscription and consumes credit.

.EXAMPLE
    az login
    ./scripts/provision_azure.ps1

.NOTES
    Resource names are derived from your subscription id so re-runs are stable.
    Azure OpenAI defaults to a region with broad model availability (East US 2);
    storage/Key Vault go in your primary region (Central India). Change with
    -Location / -OpenAiLocation if a model isn't available in your region.
#>

[CmdletBinding()]
param(
    [string]$SubscriptionId = "",
    [string]$Location = "centralindia",
    [string]$OpenAiLocation = "eastus2",
    [string]$ResourceGroup = "finsight-rg",
    [string]$ChatModel = "gpt-5-mini",
    [string]$ChatModelVersion = "2025-08-07",
    [string]$EmbeddingsModel = "text-embedding-3-small",
    [string]$EmbeddingsModelVersion = "1",
    [switch]$PushToKeyVault
)

$ErrorActionPreference = "Stop"
$tag = "project=finsight"

# Resolve the subscription from the current `az login` context if not supplied.
if (-not $SubscriptionId) {
    $SubscriptionId = az account show --query id -o tsv
}

# Deterministic, globally-unique-ish names from the subscription id.
$suffix = $SubscriptionId.Replace("-", "").Substring(0, 6).ToLower()
$StorageName  = "finsight$suffix"            # 3-24 lowercase alphanumerics
$KeyVaultName = "finsight-kv-$suffix"        # 3-24 alphanumerics + hyphens
$OpenAiName   = "finsight-openai-$suffix"

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

Step "Selecting subscription $SubscriptionId"
az account set --subscription $SubscriptionId

Step "Resource group $ResourceGroup ($Location)"
az group create --name $ResourceGroup --location $Location --tags $tag | Out-Null

Step "Storage account $StorageName + 'raw-statements' container"
az storage account create --name $StorageName --resource-group $ResourceGroup `
    --location $Location --sku Standard_LRS --kind StorageV2 --tags $tag | Out-Null
$stKey = az storage account keys list -g $ResourceGroup -n $StorageName --query "[0].value" -o tsv
az storage container create --name raw-statements --account-name $StorageName `
    --account-key $stKey | Out-Null

Step "Key Vault $KeyVaultName"
az keyvault create --name $KeyVaultName --resource-group $ResourceGroup `
    --location $Location --enable-rbac-authorization false --tags $tag | Out-Null

Step "Azure OpenAI account $OpenAiName ($OpenAiLocation)"
az cognitiveservices account create --name $OpenAiName --resource-group $ResourceGroup `
    --location $OpenAiLocation --kind OpenAI --sku S0 --custom-domain $OpenAiName `
    --tags $tag --yes | Out-Null

$endpoint = az cognitiveservices account show -n $OpenAiName -g $ResourceGroup `
    --query properties.endpoint -o tsv
$key = az cognitiveservices account keys list -n $OpenAiName -g $ResourceGroup `
    --query key1 -o tsv

# Model deployments are the most environment-sensitive step. If one fails, list
# what's available with:
#   az cognitiveservices account list-models -n $OpenAiName -g $ResourceGroup -o table
Step "Deploying chat model '$ChatModel' as deployment 'chat'"
try {
    az cognitiveservices account deployment create -n $OpenAiName -g $ResourceGroup `
        --deployment-name chat --model-name $ChatModel --model-version $ChatModelVersion `
        --model-format OpenAI --sku-name GlobalStandard --sku-capacity 10 | Out-Null
} catch {
    Write-Warning "Chat deployment failed: $($_.Exception.Message)"
    Write-Warning "Run 'az cognitiveservices account list-models -n $OpenAiName -g $ResourceGroup -o table' to see available models/versions."
}

Step "Deploying embeddings model '$EmbeddingsModel' as deployment 'embeddings'"
try {
    az cognitiveservices account deployment create -n $OpenAiName -g $ResourceGroup `
        --deployment-name embeddings --model-name $EmbeddingsModel `
        --model-version $EmbeddingsModelVersion --model-format OpenAI `
        --sku-name Standard --sku-capacity 10 | Out-Null
} catch {
    Write-Warning "Embeddings deployment failed: $($_.Exception.Message)"
}

if ($PushToKeyVault) {
    Step "Pushing secrets into Key Vault $KeyVaultName"
    az keyvault secret set --vault-name $KeyVaultName --name azure-openai-endpoint --value $endpoint | Out-Null
    az keyvault secret set --vault-name $KeyVaultName --name azure-openai-key --value $key | Out-Null
}

Write-Host "`n=== DONE. Add these to your .env (gitignored) ===" -ForegroundColor Green
Write-Host "FINSIGHT_AZURE_OPENAI_ENDPOINT=$endpoint"
Write-Host "FINSIGHT_AZURE_OPENAI_API_KEY=<hidden - see below>"
Write-Host "FINSIGHT_AZURE_OPENAI_CHAT_DEPLOYMENT=chat"
Write-Host "FINSIGHT_AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=embeddings"
Write-Host "`nRetrieve the key when needed with:" -ForegroundColor Yellow
Write-Host "  az cognitiveservices account keys list -n $OpenAiName -g $ResourceGroup --query key1 -o tsv"
Write-Host "`nResource group '$ResourceGroup' - delete everything later with:" -ForegroundColor Yellow
Write-Host "  az group delete --name $ResourceGroup --yes"
