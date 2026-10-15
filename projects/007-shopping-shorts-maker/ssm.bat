@echo off
rem Run "ssm" with the project's virtual environment (created by setup.bat).
set PYTHONUTF8=1
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo [ERROR] .venv not found. Run setup.bat first.
  exit /b 1
)
"%~dp0.venv\Scripts\python.exe" -m ssm %*
