@echo off
setlocal
cd /d "%~dp0\.."
python -m pytest || exit /b 1
python -m PyInstaller --clean --noconfirm packaging\pyinstaller\d50_patch_librarian.spec || exit /b 1
copy /Y START_HERE.txt dist\D50PatchLibrarian\START_HERE.txt >nul || exit /b 1
copy /Y README.md dist\D50PatchLibrarian\README.md >nul || exit /b 1
copy /Y CHANGELOG.md dist\D50PatchLibrarian\CHANGELOG.md >nul || exit /b 1
copy /Y LICENSE dist\D50PatchLibrarian\LICENSE >nul || exit /b 1
echo Phase-2-GUI-Build: dist\D50PatchLibrarian\D50PatchLibrarian.exe
endlocal
