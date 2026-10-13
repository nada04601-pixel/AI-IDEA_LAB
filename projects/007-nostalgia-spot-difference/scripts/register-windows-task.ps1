# Register a daily Windows Task Scheduler job (default 07:10). ASCII only on purpose.
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\register-windows-task.ps1 [-Time 07:10]
# Remove: Unregister-ScheduledTask -TaskName "NostalgiaSpotDifference" -Confirm:$false
param([string]$Time = "07:10")
$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root "scripts\run-daily.ps1"
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`"" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName "NostalgiaSpotDifference" -Action $action -Trigger $trigger `
  -Settings $settings -Description "Nostalgia spot-the-difference Shorts (daily)" -Force
Write-Host "Registered daily task at $Time. Logs: output\logs\scheduler.log"
