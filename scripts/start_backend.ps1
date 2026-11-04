# Start NOVA Python FastAPI Backend
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$rootDir = Split-Path -Parent $scriptDir
Set-Location $rootDir

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Starting NOVA FastAPI Backend Server" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$pythonExe = Join-Path $rootDir ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Host "[ERROR] Virtual environment not found at $pythonExe" -ForegroundColor Red
    Write-Host "Please run: python -m venv .venv; .\.venv\Scripts\pip install -r backend\requirements.txt" -ForegroundColor Yellow
    exit 1
}

& $pythonExe -m backend.app.main
