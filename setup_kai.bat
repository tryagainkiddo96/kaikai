@echo off
REM Kai AI Setup Script
REM Creates Kai on your desktop with one click

echo ========================================
echo   Kai AI - One Click Setup
echo ========================================
echo.

set DESKTOP=%USERPROFILE%\OneDrive\Desktop
set KAI_DIR=%DESKTOP%\Kai-AI

echo [1/5] Creating Kai folder on desktop...
if exist "%KAI_DIR%" (
    echo Kai folder already exists. Updating...
    cd /d "%KAI_DIR%"
    git pull origin main
) else (
    echo Cloning Kai from GitHub...
    cd /d "%DESKTOP%"
    git clone https://github.com/tryagainkiddo96/kaikai.git "Kai-AI"
    cd /d "%KAI_DIR%"
)

echo.
echo [2/5] Creating virtual environment...
python -m venv .venv
call .venv\Scripts\activate.bat

echo.
echo [3/5] Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt
pip install playwright
playwright install chromium

echo.
echo [4/5] Creating launcher...
(
echo @echo off
echo cd /d "%KAI_DIR%"
echo call .venv\Scripts\activate.bat
echo echo.
echo echo ========================================
echo echo   Kai AI is starting...
echo echo ========================================
echo echo.
echo python -m kai_agent.assistant
echo pause
) > "%DESKTOP%\Start-Kai.bat"

echo.
echo [5/5] Done!
echo.
echo ========================================
echo   Kai AI is ready!
echo ========================================
echo.
echo   Desktop shortcut: Start-Kai.bat
echo   Project folder: %KAI_DIR%
echo.
echo   Commands to try:
echo   - "browse stfrancis.com"
echo   - "do task: get patient form from st francis hospital"
echo   - "plan: find the patient portal signup page"
echo   - "show documents"
echo.
echo   Double-click Start-Kai.bat to launch anytime.
echo ========================================
echo.

pause
