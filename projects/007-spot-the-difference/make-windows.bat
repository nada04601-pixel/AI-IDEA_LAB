@echo off
rem Spot-the-difference shorts maker for Windows. ASCII only on purpose: the real work is in make-windows.ps1.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0make-windows.ps1" %*
pause
