# Start NOVA Desktop AI Assistant (Backend + Electron Shell)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$rootDir = Split-Path -Parent $scriptDir
Set-Location $rootDir

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Launching NOVA Desktop AI Assistant" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Clean up any existing process holding port 8000
$portInUse = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($portInUse) {
    Write-Host "Found existing process on port 8000 (PID: $($portInUse.OwningProcess)). Stopping..." -ForegroundColor DarkYellow
    Stop-Process -Id $portInUse.OwningProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
}

# 2. Start Backend API Server
$pythonExe = Join-Path $rootDir ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    Write-Host "[ERROR] Virtual environment not found at $pythonExe" -ForegroundColor Red
    exit 1
}

Write-Host "[1/2] Starting Python FastAPI Backend Server..." -ForegroundColor Yellow
$backendProcess = Start-Process -FilePath $pythonExe -ArgumentList "-m", "backend.app.main" -WorkingDirectory $rootDir -PassThru -WindowStyle Hidden

# Wait for backend health probe
$retries = 25
$backendReady = $false

for ($i = 0; $i -lt $retries; $i++) {
    Start-Sleep -Milliseconds 400
    try {
        $res = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -Method Get -TimeoutSec 2 -ErrorAction Stop
        if ($res.status -eq "healthy") {
            $backendReady = $true
            Write-Host "      Backend is ONLINE and HEALTHY (Uptime: $($res.uptime_seconds)s)" -ForegroundColor Green
            break
        }
    } catch {
        # continue waiting
    }
}

if (-not $backendReady) {
    Write-Host "[ERROR] Backend server failed to respond on http://127.0.0.1:8000/health" -ForegroundColor Red
    Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
    exit 1
}

# 3. Launch Electron Desktop App
Write-Host "[2/2] Launching Electron Desktop Window..." -ForegroundColor Yellow
$frontendDir = Join-Path $rootDir "frontend"
Set-Location $frontendDir

try {
    # Launch electron with local binary
    $electronCmd = Join-Path $frontendDir "node_modules\.bin\electron.cmd"
    if (Test-Path $electronCmd) {
        & $electronCmd .
    } else {
        npx electron .
    }
} finally {
    Write-Host "Closing background backend server..." -ForegroundColor Cyan
    Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
}
