@echo off
setlocal
cd /d "%~dp0\.."
python tests\fixtures\generate_fixtures.py || exit /b 1
python -m pytest %*
endlocal

