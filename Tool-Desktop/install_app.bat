@echo off
cd /d "%~dp0"

echo ============================================
echo   TaskReader Desktop Pet - Installer
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.8+ first.
    pause
    exit /b 1
)

echo [1/3] Installing Python dependencies...
pip install jieba pystray Pillow -q 2>nul
echo        Done.

echo [2/3] Checking Ollama (optional)...
ollama --version >nul 2>&1
if errorlevel 1 (
    echo        Ollama not detected. LLM enhancement disabled.
) else (
    echo        Ollama is ready.
)

echo [3/3] Creating shortcuts...
cscript //nologo create_shortcuts.vbs
if errorlevel 1 (
    echo        Shortcut creation failed. Try running as Administrator.
) else (
    echo        Desktop + Start Menu shortcuts created.
)

echo.
echo ============================================
echo   Installation complete!
echo   Launch via: desktop shortcut or start_bot.bat
echo   Uninstall:   uninstall.bat
echo ============================================
pause
