[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$TaskName = "AI Config Registry Sync",
    [string]$SyncScriptRelativePath = "scripts\sync-registry.ps1",
    [string]$Schedule = "Daily",
    [string]$At = "09:00",
    [switch]$EnableAfterRegister
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message"
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$syncScript = Join-Path $repoRoot $SyncScriptRelativePath

if (-not (Test-Path $syncScript)) {
    throw "Sync script not found: $syncScript`nCreate scripts\sync-registry.ps1 first."
}

$scheduleKind = $Schedule.ToLowerInvariant()
switch ($scheduleKind) {
    "daily" {
        $trigger = New-ScheduledTaskTrigger -Daily -At $At
        break
    }
    "hourly" {
        $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(5) `
            -RepetitionInterval (New-TimeSpan -Hours 1) `
            -RepetitionDuration ([TimeSpan]::MaxValue)
        break
    }
    default {
        throw "Unsupported schedule '$Schedule'. Use Daily or Hourly."
    }
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$syncScript`""

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew

if ($PSCmdlet.ShouldProcess($TaskName, "Register scheduled task")) {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Principal $principal `
        -Settings $settings `
        -Force | Out-Null

    if (-not $EnableAfterRegister) {
        Disable-ScheduledTask -TaskName $TaskName | Out-Null
        Write-Step "Task registered and left disabled (manual-first default)."
        Write-Host "Run this to enable later:"
        Write-Host "  Enable-ScheduledTask -TaskName `"$TaskName`""
    }
    else {
        Enable-ScheduledTask -TaskName $TaskName | Out-Null
        Write-Step "Task registered and enabled."
    }
}
