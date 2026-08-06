@echo off
chcp 65001 >nul
cd /d "%~dp0"

if "%~1"=="" (
    echo ============================================
    echo   TaskReader 桌宠
    echo ============================================
    echo.
    echo 用法：
    echo   run.bat                   启动桌宠应用
    echo   run.bat "句子文本"       解析任务（命令行模式）
    echo   start_bot.bat            启动桌宠（含系统托盘）
    echo.
    pause
    exit /b 0
)

rem ============================================================
rem  CLI mode: parse task sentence
rem ============================================================
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m task_reader.cli %*
) else (
    python -m task_reader.cli %*
)
