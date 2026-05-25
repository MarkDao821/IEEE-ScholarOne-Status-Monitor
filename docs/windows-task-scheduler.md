# Windows Task Scheduler

Run these commands from an elevated PowerShell window.

## Daily 09:00 Report

```powershell
$project = "D:\code\work\审稿状态推送\ieee-scholarone-status-monitor"
$python = Join-Path $project ".venv\Scripts\python.exe"
$action = New-ScheduledTaskAction -Execute $python -Argument "-m ieee_scholarone_monitor report" -WorkingDirectory $project
$trigger = New-ScheduledTaskTrigger -Daily -At 9:00
Register-ScheduledTask -TaskName "IEEE ScholarOne Status Monitor" -Action $action -Trigger $trigger -Description "Send IEEE ScholarOne manuscript status report" -Force
```

## Change-Only Checks

To check several times a day and notify only on changes, use `check` instead of `report`:

```powershell
$project = "D:\code\work\审稿状态推送\ieee-scholarone-status-monitor"
$python = Join-Path $project ".venv\Scripts\python.exe"
$action = New-ScheduledTaskAction -Execute $python -Argument "-m ieee_scholarone_monitor check" -WorkingDirectory $project
$trigger = New-ScheduledTaskTrigger -Daily -At 13:00
Register-ScheduledTask -TaskName "IEEE ScholarOne Change Check" -Action $action -Trigger $trigger -Description "Check IEEE ScholarOne manuscript status changes" -Force
```

## Test The Task

```powershell
Start-ScheduledTask -TaskName "IEEE ScholarOne Status Monitor"
Get-Content "D:\code\work\审稿状态推送\ieee-scholarone-status-monitor\logs\app.log" -Tail 80
```

## Temporary 1-Minute Test Trigger

```powershell
$taskName = "IEEE ScholarOne Status Monitor"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1) -RepetitionDuration (New-TimeSpan -Hours 2)
Set-ScheduledTask -TaskName $taskName -Trigger $trigger
```

Restore daily 09:00:

```powershell
$taskName = "IEEE ScholarOne Status Monitor"
$trigger = New-ScheduledTaskTrigger -Daily -At 9:00
Set-ScheduledTask -TaskName $taskName -Trigger $trigger
```
