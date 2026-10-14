@echo off
title THUNDER AI
cd /d "%~dp0"
where py >nul 2>nul && (py -3 scripts\launcher.py start & goto :end)
where python >nul 2>nul && (python scripts\launcher.py start & goto :end)
echo Python 3.11 or newer is needed. Download it from https://www.python.org/downloads/
echo During installation tick "Add Python to PATH", then double-click START_THUNDER again.
pause
:end
