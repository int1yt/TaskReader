@echo off
rem ============================================================
rem  Tool-Desktop runner (Windows)
rem  Usage: run.bat "my task sentence"
rem ============================================================
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m task_reader.cli %*
) else (
    python -m task_reader.cli %*
)
