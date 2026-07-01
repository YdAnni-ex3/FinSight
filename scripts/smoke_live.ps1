$base = "https://finsight-gateway.icymeadow-7a1423f4.centralindia.azurecontainerapps.io"
$file = "data/synthetic/statement_01.csv"
# --ssl-no-revoke: bypass Windows Schannel CRL check when a corporate proxy blocks revocation servers.

"=== /healthz ==="
curl.exe -sS --ssl-no-revoke --max-time 90 "$base/healthz"; ""

"=== /readyz ==="
curl.exe -sS --ssl-no-revoke --max-time 60 "$base/readyz"; ""

"=== POST /api/statements/parse ==="
$parse = curl.exe -sS --ssl-no-revoke --max-time 180 -X POST -F "file=@$file" "$base/api/statements/parse"
($parse | ConvertFrom-Json).summary | ConvertTo-Json -Compress

"=== POST /api/statements/index ==="
curl.exe -sS --ssl-no-revoke --max-time 180 -X POST -F "file=@$file" "$base/api/statements/index"; ""

"=== POST /api/query ==="
$body = '{"question":"how much did I spend on food?","top_k":3}'
$tmp = New-TemporaryFile
Set-Content -Path $tmp -Value $body -Encoding ascii -NoNewline
$q = curl.exe -sS --ssl-no-revoke --max-time 120 -X POST -H "Content-Type: application/json" --data "@$tmp" "$base/api/query" | ConvertFrom-Json
Remove-Item $tmp -Force
"answer:  $($q.answer)"
"matches: $($q.matches.Count)"
