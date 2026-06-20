param(
    [string]$PeersFile = "peers.json"
)

if (-not (Test-Path -LiteralPath $PeersFile)) {
    Copy-Item "peers.example.json" $PeersFile
    Write-Host "Created $PeersFile from peers.example.json. Update IP addresses, then run again."
    exit 1
}

python a2_connect.py --peers-file $PeersFile
