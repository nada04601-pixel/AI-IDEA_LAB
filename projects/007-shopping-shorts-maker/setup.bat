@echo off
rem Shopping Shorts Maker setup for Windows. ASCII only on purpose: the real work is in setup.ps1.
rem Options: setup.bat -Cpu (force CPU PyTorch) / setup.bat -ReinstallTorch
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
pause
