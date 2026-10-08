@echo off
rem AI Shorts Studio launcher for Windows. ASCII only on purpose: the real work is in start-windows.ps1.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-windows.ps1"
if errorlevel 1 pause
