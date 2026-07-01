$base = "https://finsight-gateway.icymeadow-7a1423f4.centralindia.azurecontainerapps.io"
$file = Get-Item data/synthetic/statement_01.csv

"=== /healthz ==="
try { Invoke-RestMethod "$base/healthz" -TimeoutSec 60 | ConvertTo-Json -Compress } catch { $_.Exception.Message }

"=== /readyz ==="
try { Invoke-RestMethod "$base/readyz" -TimeoutSec 60 | ConvertTo-Json -Compress } catch { $_.Exception.Message }

"=== POST /api/statements/parse ==="
try {
    $r = Invoke-RestMethod "$base/api/statements/parse" -Method Post -Form @{ file = $file } -TimeoutSec 180
    $r.summary | ConvertTo-Json -Compress
} catch { $_.Exception.Message }

"=== POST /api/statements/index ==="
try {
    Invoke-RestMethod "$base/api/statements/index" -Method Post -Form @{ file = $file } -TimeoutSec 180 | ConvertTo-Json -Compress
} catch { $_.Exception.Message }

"=== POST /api/query ==="
try {
    $q = Invoke-RestMethod "$base/api/query" -Method Post -ContentType application/json -Body '{"question":"how much did I spend on food?","top_k":3}' -TimeoutSec 60
    "answer: " + $q.answer
    "matches: " + ($q.matches.Count)
} catch { $_.Exception.Message }
