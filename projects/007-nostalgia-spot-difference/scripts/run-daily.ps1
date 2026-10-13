# Called by Windows Task Scheduler. ASCII only on purpose.
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONIOENCODING = "utf-8"
& .\.venv\Scripts\python.exe main.py daily *>> "output\logs\scheduler.log"
exit $LASTEXITCODE
