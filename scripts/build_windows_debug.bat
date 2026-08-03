@echo off
setlocal
cd /d "%~dp0\.."
python -m pytest || exit /b 1
python -m PyInstaller --clean --noconfirm --onedir --console --name D50PatchLibrarian-debug --paths . --hidden-import mido.backends.rtmidi --hidden-import rtmidi main.py || exit /b 1
echo Debug-Build: dist\D50PatchLibrarian-debug\D50PatchLibrarian-debug.exe
endlocal
