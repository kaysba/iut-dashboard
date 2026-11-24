@echo off
cd /d "%~dp0"
where py >nul 2>nul && (py dashboard.py %*) || (python dashboard.py %*)
pause
