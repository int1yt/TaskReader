@echo off
cd /d "%~dp0"

echo ============================================
echo   TaskReader Desktop Pet - Uninstall
echo ============================================
echo.

echo Removing desktop shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Remove-Item ([Environment]::GetFolderPath('Desktop') + '\TaskReader.lnk') -Force -ErrorAction SilentlyContinue"

echo Removing Start Menu shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; Remove-Item ($ws.SpecialFolders('StartMenu') + '\TaskReader.lnk') -Force -ErrorAction SilentlyContinue"

echo Removing auto-start entry...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Remove-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'TaskReaderPet' -Force -ErrorAction SilentlyContinue"

echo.
echo Uninstall complete. Project folder kept: %cd%
echo Delete this folder manually to fully remove.
pause
