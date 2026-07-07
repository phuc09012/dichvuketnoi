param(
    [string]$LocalBaseUrl = "http://127.0.0.1:8000",
    [string]$AiServiceUrl = "http://26.15.57.238:8000",
    [string]$AiDetectPath = "/api/v1/vision/detect",
    [string]$AuthHeaderName = "Authorization",
    [string]$AuthHeaderValue = "Bearer smart-campus-secret-token",
    [ValidateSet("base64", "url")]
    [string]$PayloadMode = "url",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Join-UrlPath {
    param(
        [Parameter(Mandatory = $true)][string]$BaseUrl,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $base = $BaseUrl.TrimEnd("/")
    if (-not $Path.StartsWith("/")) {
        $Path = "/" + $Path
    }
    return $base + $Path
}

function Convert-FileToBase64 {
    param(
        [Parameter(Mandatory = $true)][string]$Path
    )

    $bytes = [System.IO.File]::ReadAllBytes($Path)
    return [Convert]::ToBase64String($bytes)
}

try {
    $triggerUrl = Join-UrlPath -BaseUrl $LocalBaseUrl -Path "/camera/trigger"
    Write-Host "Fetching trigger from $triggerUrl"
    $trigger = Invoke-RestMethod -Method Get -Uri $triggerUrl

    if (-not $trigger.timestamp) {
        throw "Local trigger response is missing timestamp."
    }

    Write-Host "Snapshot URL: $($trigger.snapshot_url)"
    Write-Host "Timestamp   : $($trigger.timestamp)"

    if ($PayloadMode -eq "base64") {
        $snapshotPath = $trigger.probe.snapshot_path
        if (-not $snapshotPath) {
            throw "Local trigger response is missing probe.snapshot_path required for base64 mode."
        }

        if (-not [System.IO.Path]::IsPathRooted($snapshotPath)) {
            $snapshotPath = Join-Path (Get-Location) $snapshotPath
        }

        if (-not (Test-Path -LiteralPath $snapshotPath)) {
            throw "Snapshot file not found: $snapshotPath"
        }

        $imageBase64 = Convert-FileToBase64 -Path $snapshotPath
        $body = @{
            image_base64 = $imageBase64
            timestamp = $trigger.timestamp
        } | ConvertTo-Json -Depth 4
        Write-Host "Payload mode: base64"
        Write-Host "Snapshot file: $snapshotPath"
        Write-Host "Base64 length : $($imageBase64.Length)"
    }
    else {
        if (-not $trigger.snapshot_url) {
            throw "Local trigger response is missing snapshot_url required for url mode."
        }

        $body = @{
            image_url = $trigger.snapshot_url
            timestamp = $trigger.timestamp
        } | ConvertTo-Json -Depth 4
        Write-Host "Payload mode: url"
    }

    if ($DryRun) {
        Write-Host "DryRun enabled, not sending to AI Vision."
        Write-Output $body
        exit 0
    }

    $detectUrl = Join-UrlPath -BaseUrl $AiServiceUrl -Path $AiDetectPath
    Write-Host "Sending to $detectUrl"

    $headers = @{}
    if ($AuthHeaderName -and $AuthHeaderValue) {
        $headers[$AuthHeaderName] = $AuthHeaderValue
    }

    $response = Invoke-RestMethod `
        -Method Post `
        -Uri $detectUrl `
        -ContentType "application/json" `
        -Headers $headers `
        -Body $body

    $response | ConvertTo-Json -Depth 10
}
catch {
    Write-Error $_
    exit 1
}
