@echo off
cd /d "%~dp0"

echo ============================================
echo   TaskReader Desktop Pet
echo ============================================
echo.

echo Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.8+ first.
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo   Python OK: 
python --version

echo Checking dependencies...
python -c "import jieba" 2>nul
if errorlevel 1 (
    echo   [WARNING] jieba not installed. Installing...
    pip install jieba
)
python -c "import tkinter" 2>nul
if errorlevel 1 (
    echo   [ERROR] tkinter not available. Please reinstall Python with tcl/tk support.
    pause
    exit /b 1
)
echo   Dependencies OK

echo Starting application...
echo.
echo If the app crashes, run this from cmd.exe to see the error:
echo   cd /d "%~dp0"
echo   python -m app.main
echo.

python -m app.main 2>"%TEMP%\taskreader_error.log"
if errorlevel 1 (
    echo.
    echo [ERROR] Application crashed. See error log:
    type "%TEMP%\taskreader_error.log"
    echo.
    pause
)
