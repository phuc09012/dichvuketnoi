$envFile = Join-Path $PSScriptRoot ".env"
if (-not (Test-Path -LiteralPath $envFile)) {
    Copy-Item (Join-Path $PSScriptRoot ".env.example") $envFile
}

Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
    $parts = $_.Split('=', 2)
    $name = $parts[0].Trim()
    $value = $parts[1]
    Set-Item -Path "Env:$name" -Value $value
}

if (-not $env:CAMERA_STREAM_URL) {
    $env:CAMERA_STREAM_URL = "https://camera.labaiotdnu.app/video?key=matkhau_cua_ban"
}

if (-not $env:CAMERA_ID) { $env:CAMERA_ID = "cam-gate-a" }
if (-not $env:CAMERA_LOCATION) { $env:CAMERA_LOCATION = "Main Gate A" }
if (-not $env:MOTION_THRESHOLD) { $env:MOTION_THRESHOLD = "0.08" }
if (-not $env:HOST) { $env:HOST = "0.0.0.0" }
if (-not $env:PORT) { $env:PORT = "8000" }

uvicorn app.main:app --host $env:HOST --port $env:PORT
