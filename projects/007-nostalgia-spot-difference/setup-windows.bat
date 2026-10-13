@echo off
rem One-click setup for Windows. ASCII only on purpose: the real work is in scripts\setup-windows.ps1.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup-windows.ps1"
pause
