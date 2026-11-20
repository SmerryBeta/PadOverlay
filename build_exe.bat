@echo off
setlocal
cd /d "%~dp0"

python -m pip install -r requirements.txt pyinstaller -q
if errorlevel 1 exit /b 1

python -m PyInstaller --noconfirm --clean build_exe.spec
if errorlevel 1 exit /b 1

echo.
echo Built: dist\PadOverlay.exe
echo Drop the exe anywhere; first run copies config\ and skins\ beside it if missing.
endlocal
