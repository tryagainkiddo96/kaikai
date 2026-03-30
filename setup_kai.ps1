# Kai AI One-Click Setup
# Run this in PowerShell: powershell -ExecutionPolicy Bypass -File setup_kai.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Kai AI - One Click Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$Desktop = "$env:USERPROFILE\OneDrive\Desktop"
if (-not (Test-Path $Desktop)) {
    $Desktop = "$env:USERPROFILE\Desktop"
}
$KaiDir = "$Desktop\Kai-AI"

# Step 1: Clone or update
Write-Host "[1/5] Getting Kai files..." -ForegroundColor Yellow
if (Test-Path $KaiDir) {
    Write-Host "  Updating existing Kai..." -ForegroundColor Gray
    Set-Location $KaiDir
    git pull origin main
} else {
    Write-Host "  Cloning Kai from GitHub..." -ForegroundColor Gray
    Set-Location $Desktop
    git clone https://github.com/tryagainkiddo96/kaikai.git "Kai-AI"
    Set-Location $KaiDir
}

# Step 2: Virtual environment
Write-Host ""
Write-Host "[2/5] Setting up Python environment..." -ForegroundColor Yellow
if (-not (Test-Path "$KaiDir\.venv")) {
    python -m venv .venv
}
& "$KaiDir\.venv\Scripts\Activate.ps1"

# Step 3: Install dependencies
Write-Host ""
Write-Host "[3/5] Installing dependencies (this takes a minute)..." -ForegroundColor Yellow
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
pip install playwright --quiet
playwright install chromium

# Step 4: Create launcher
Write-Host ""
Write-Host "[4/5] Creating desktop launcher..." -ForegroundColor Yellow

# Create batch launcher
$launcher = @"
@echo off
cd /d "$KaiDir"
call .venv\Scripts\activate.bat
set "KAI_MODEL=qwen3:4b-q4_K_M"
set "KAI_OLLAMA_TIMEOUT=180"
start "" "C:\Users\7nujy6xc\AppData\Local\Programs\Ollama\ollama.exe" serve >nul 2>nul
cls
echo.
echo  ========================================
echo    Kai AI is running
echo  ========================================
echo.
echo  Type your request and press Enter.
echo  Type /exit to quit.
echo.
python -m kai_agent.assistant --workspace "$KaiDir"
pause
"@
$launcher | Out-File -FilePath "$Desktop\Start-Kai.bat" -Encoding ASCII

# Step 5: Done
Write-Host ""
Write-Host "[5/5] Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Kai AI is ready!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Desktop shortcut: Start-Kai.bat" -ForegroundColor White
Write-Host "  Project folder: $KaiDir" -ForegroundColor White
Write-Host ""
Write-Host "  Try these commands in Kai:" -ForegroundColor Yellow
Write-Host '  - "browse stfrancis.com"' -ForegroundColor Gray
Write-Host '  - "do task: get patient form from st francis hospital cape girardeau MO"' -ForegroundColor Gray
Write-Host '  - "plan: find the patient portal signup page"' -ForegroundColor Gray
Write-Host '  - "show documents"' -ForegroundColor Gray
Write-Host ""
Write-Host "  Double-click Start-Kai.bat to launch anytime." -ForegroundColor White
Write-Host ""

Read-Host "Press Enter to launch Kai now"
$env:KAI_MODEL = "qwen3:4b-q4_K_M"
$env:KAI_OLLAMA_TIMEOUT = "180"
python -m kai_agent.assistant --workspace "$KaiDir"
