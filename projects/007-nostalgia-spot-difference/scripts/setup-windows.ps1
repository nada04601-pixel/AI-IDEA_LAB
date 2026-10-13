# One-time setup for Windows PowerShell. ASCII only on purpose (Windows PowerShell 5 encoding).
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\setup-windows.ps1 [-YouTube]
param([switch]$YouTube)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) { $python = "py"; $pyArgs = @("-3") } else { $python = "python"; $pyArgs = @() }
& $python @pyArgs --version
if ($LASTEXITCODE -ne 0) { Write-Host "Python 3.10+ is required: https://www.python.org/downloads/"; exit 1 }

if (-not (Test-Path ".venv")) { & $python @pyArgs -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
if ($YouTube) { & .\.venv\Scripts\python.exe -m pip install -r requirements-youtube.txt }
else { & .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt }

if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Write-Host "Created .env from .env.example" }

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  Write-Host ""
  Write-Host "FFmpeg not found. Install it with:  winget install --id Gyan.FFmpeg -e"
  Write-Host "Then open a NEW PowerShell window so PATH is refreshed."
}
& .\.venv\Scripts\python.exe main.py doctor
