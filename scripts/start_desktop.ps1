# Start NOVA Full Desktop Application (Backend + Electron Shell)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$rootDir = Split-Path -Parent $scriptDir
Set-Location $rootDir

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Launching NOVA Desktop AI Assistant" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 1. Start backend process
$pythonExe = Join-Path $rootDir ".venv\Scripts\python.exe"
Write-Host "[1/3] Starting Backend API Server..." -ForegroundColor Yellow
$backendJob = Start-Job -ScriptBlock {
    param($root, $py)
    Set-Location $root
    & $py -m backend.app.main
} -ArgumentList $rootDir, $pythonExe

# 2. Wait for backend health probe
Write-Host "[2/3] Waiting for Backend Health probe on http://127.0.0.1:8000/health..." -ForegroundColor Yellow
$retries = 20
$backendReady = $false

for ($i = 0; $i -lt $retries; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $res = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -Method Get -TimeoutSec 2 -ErrorAction Stop
        if ($res.status -eq "healthy") {
            $backendReady = $true
            Write-Host "       Backend is HEALTHY (Uptime: $($res.uptime_seconds)s)" -ForegroundColor Green
            break
        }
    } catch {
        # continue waiting
    }
}

if (-not $backendReady) {
    Write-Host "[ERROR] Backend failed to start. Job output:" -ForegroundColor Red
    Receive-Job $backendJob
    Stop-Job $backendJob
    Remove-Job $backendJob
    exit 1
}

# 3. Launch Frontend Electron Shell
Write-Host "[3/3] Launching Electron Desktop Shell..." -ForegroundColor Yellow
Set-Location (Join-Path $rootDir "frontend")

try {
    npm run dev
} finally {
    Write-Host "Stopping background backend job..." -ForegroundColor Cyan
    Stop-Job $backendJob
    Remove-Job $backendJob
}
