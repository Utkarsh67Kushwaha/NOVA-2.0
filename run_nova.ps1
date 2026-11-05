# ==============================================================================
# NOVA 2.0 Desktop Assistant - Local Launcher Script
# ==============================================================================

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "       Initializing NOVA 2.0 Desktop Assistant   " -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

$projectRoot = $PSScriptRoot

# Step 1: Start FastAPI Backend if not already running
$backendHealth = try { (Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 1).StatusCode } catch { $null }

if ($backendHealth -eq 200) {
    Write-Host "[OK] Backend server is already running on port 8000." -ForegroundColor Green
} else {
    Write-Host "[*] Starting FastAPI Backend server..." -ForegroundColor Yellow
    Start-Process -FilePath "$projectRoot\.venv\Scripts\python.exe" -ArgumentList "-m", "backend.app.main" -WorkingDirectory $projectRoot -WindowStyle Minimized
    Start-Sleep -Seconds 2
}

# Step 2: Start Electron Desktop Frontend
Write-Host "[*] Launching NOVA Electron UI..." -ForegroundColor Cyan
Set-Location "$projectRoot\frontend"
npm run dev
