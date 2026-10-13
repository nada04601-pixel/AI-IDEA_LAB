@echo off
rem Make one video (double-click). ASCII only on purpose.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
.venv\Scripts\python.exe main.py make
pause
