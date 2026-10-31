# Integration check: opens a real, temporary public Quick Tunnel, then closes it.
# Run: powershell -ExecutionPolicy Bypass -File scripts/test_tunnel.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$python = Join-Path $root 'backend\.venv\Scripts\python.exe'
$oldDebug = $env:DEBUG
$oldDatabase = $env:DATABASE_URL
$oldOrigin = $env:FRONTEND_ORIGIN
$runner = [powershell]::Create()
try {
    $env:DEBUG = 'true'
    $env:DATABASE_URL = 'sqlite://'
    $env:FRONTEND_ORIGIN = 'http://localhost:3000,https://dashboard.example'
    [void]$runner.AddScript('& $args[0]').AddArgument((Join-Path $PSScriptRoot 'tunnel.ps1'))
    $pending = $runner.BeginInvoke()
    $url = $null
    $deadline = [DateTime]::UtcNow.AddSeconds(120)
    while (!$pending.IsCompleted -and [DateTime]::UtcNow -lt $deadline) {
        $messages = ($runner.Streams.Information | ForEach-Object { $_.MessageData.ToString() }) -join "`n"
        if ($messages -match 'URL tunnel: (https://[a-z0-9-]+\.trycloudflare\.com)') {
            $url = $Matches[1]
            break
        }
        Start-Sleep -Milliseconds 500
    }
    if (!$url) {
        throw "Tunnel tidak siap: $($runner.Streams.Error | Out-String)"
    }
    Write-Host "URL tunnel terakhir: $url"
    & $python (Join-Path $PSScriptRoot 'smoke_test.py') 'http://localhost:8000'
    if ($LASTEXITCODE -ne 0) { throw 'Smoke test lokal gagal.' }
    # Quick Tunnel DNS/edge registration can lag behind URL creation.
    for ($attempt = 0; $attempt -lt 6; $attempt++) {
        & $python (Join-Path $PSScriptRoot 'smoke_test.py') $url
        if ($LASTEXITCODE -eq 0) { break }
        if ($attempt -eq 5) { throw 'Smoke test publik gagal.' }
        Start-Sleep -Seconds 5
    }
} finally {
    $runner.Stop() # Pipeline cancellation exercises tunnel.ps1's finally cleanup.
    $runner.Dispose()
    $env:DEBUG = $oldDebug
    $env:DATABASE_URL = $oldDatabase
    $env:FRONTEND_ORIGIN = $oldOrigin
}
Start-Sleep -Seconds 1
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 8000)
try {
    $listener.Start()
    Write-Host 'OK cleanup: port 8000 bebas setelah penghentian skrip.'
} finally { $listener.Stop() }
