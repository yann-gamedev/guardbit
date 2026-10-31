# Install: winget install --id Cloudflare.cloudflared
# Run from any directory. Set DEBUG and FRONTEND_ORIGIN before starting.
# Ctrl+C stops this script's tunnel and Uvicorn; no other process is stopped.
$ErrorActionPreference = 'Stop'
$backend = Join-Path (Split-Path $PSScriptRoot -Parent) 'backend'
$activate = Join-Path $backend '.venv\Scripts\Activate.ps1'
$python = Join-Path $backend '.venv\Scripts\python.exe'
if (!(Test-Path $activate) -or !(Test-Path $python)) {
    throw 'Venv tidak ditemukan. Buat backend/.venv dan install backend/requirements.txt dahulu.'
}
$cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
if (!$cloudflared) {
    throw 'cloudflared tidak ditemukan. Jalankan winget install --id Cloudflare.cloudflared, lalu buka terminal baru.'
}
# Refuse an occupied port rather than exposing somebody else's server.
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 8000)
try { $listener.Start() } finally { $listener.Stop() }

$server = $null
$tunnel = $null
$oldPath = $env:PATH
$oldVenv = $env:VIRTUAL_ENV
$logs = Join-Path ([System.IO.Path]::GetTempPath()) ('guardbit-tunnel-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $logs | Out-Null
Write-Host "Log lokal: $logs"
try {
    . $activate
    $server = Start-Process -FilePath $python -ArgumentList '-m uvicorn app.main:app --host 127.0.0.1 --port 8000' -WorkingDirectory $backend -PassThru -NoNewWindow -RedirectStandardOutput "$logs\uvicorn.out.log" -RedirectStandardError "$logs\uvicorn.err.log"
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        $server.Refresh()
        if ($server.HasExited) { throw "Uvicorn berhenti. Periksa $logs\uvicorn.err.log" }
        # A direct socket avoids system HTTP proxies for this loopback readiness check.
        $connection = [System.Net.Sockets.TcpClient]::new()
        try {
            $connection.Connect('127.0.0.1', 8000)
            $ready = $true
        } catch { } finally { $connection.Dispose() }
        if ($ready) { break }
        Start-Sleep -Milliseconds 500
    }
    if (!$ready) { throw 'Uvicorn belum siap setelah 30 detik.' }
    $tunnel = Start-Process -FilePath $cloudflared.Source -ArgumentList 'tunnel --url http://localhost:8000' -WorkingDirectory $backend -PassThru -NoNewWindow -RedirectStandardOutput "$logs\cloudflared.out.log" -RedirectStandardError "$logs\cloudflared.err.log"
    Write-Host 'Menunggu URL Quick Tunnel. Ctrl+C untuk menghentikan kedua proses.'
    $url = $null
    $deadline = [DateTime]::UtcNow.AddSeconds(90)
    while ($true) {
        $server.Refresh()
        $tunnel.Refresh()
        if ($server.HasExited -or $tunnel.HasExited) {
            throw "Uvicorn/cloudflared berhenti. Periksa log di $logs"
        }
        if (!$url) {
            $text = (Get-Content "$logs\cloudflared.err.log", "$logs\cloudflared.out.log" -Raw -ErrorAction SilentlyContinue) -join "`n"
            if ($text -match 'https://[a-z0-9-]+\.trycloudflare\.com') {
                $url = $Matches[0]
                Write-Host "URL tunnel: $url"
                Write-Host "Smoke test dari root repo: python scripts/smoke_test.py $url"
            } elseif ([DateTime]::UtcNow -gt $deadline) {
                throw "URL tunnel belum tersedia setelah 90 detik. Periksa $logs"
            }
        }
        Start-Sleep -Milliseconds 500
    }
} finally {
    foreach ($process in @($tunnel, $server)) {
        if ($process) {
            $process.Refresh()
            if (!$process.HasExited) { Stop-Process -Id $process.Id -ErrorAction SilentlyContinue }
            $process.Dispose()
        }
    }
    if (Test-Path Function:deactivate) { deactivate }
    $env:PATH = $oldPath
    $env:VIRTUAL_ENV = $oldVenv
    Write-Host 'Tunnel dan Uvicorn milik skrip dihentikan.'
}
