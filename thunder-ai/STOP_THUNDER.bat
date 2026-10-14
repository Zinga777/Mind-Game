@echo off
cd /d "%~dp0"
where py >nul 2>nul && (py -3 scripts\launcher.py stop & goto :end)
python scripts\launcher.py stop
:end
pause
