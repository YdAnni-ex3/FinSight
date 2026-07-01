$base = "https://finsight-gateway.icymeadow-7a1423f4.centralindia.azurecontainerapps.io"
$file = "data/synthetic/statement_01.csv"
# --ssl-no-revoke: bypass Windows Schannel CRL check when a corporate proxy blocks revocation servers.

function Post-Json($path, $json) {
    $tmp = New-TemporaryFile
    Set-Content -Path $tmp -Value $json -Encoding ascii -NoNewline
    try {
        curl.exe -sS --ssl-no-revoke --max-time 120 -X POST -H "Content-Type: application/json" `
            --data "@$tmp" "$base$path" | ConvertFrom-Json
    }
    finally { Remove-Item $tmp -Force }
}

"=== /healthz ==="
curl.exe -sS --ssl-no-revoke --max-time 90 "$base/healthz"; ""

"=== POST /api/statements/analyze ==="
$analyze = curl.exe -sS --ssl-no-revoke --max-time 180 -X POST -F "file=@$file" "$base/api/statements/analyze" | ConvertFrom-Json
"categorizer: $($analyze.summary.categorizer) | indexed: $($analyze.summary.indexed) ($($analyze.summary.retrieval)) | anomalies: $($analyze.summary.anomaly_count)"

"=== POST /api/query (RAG) ==="
$q = Post-Json "/api/query" '{"question":"how much did I spend on food?","top_k":3}'
"answer:  $($q.answer)"

"=== POST /api/agent (tool-using agent) ==="
$agent = Post-Json "/api/agent" '{"question":"How much did I spend on shopping, and were there any unusual charges?"}'
"answer: $($agent.answer)"
"tools:  $(($agent.steps | ForEach-Object { $_.tool }) -join ', ')"
