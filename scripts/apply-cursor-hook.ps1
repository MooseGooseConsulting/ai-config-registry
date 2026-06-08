[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$HookFilePath = "$env:USERPROFILE\.cursor\hooks.json",
    [string]$SyncScriptRelativePath = "scripts\sync-registry.ps1",
    [string]$HookEvent = "PostAgentTurn"
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

$hookCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$syncScript`" -NoDashboard"

if (Test-Path $HookFilePath) {
    try {
        $raw = Get-Content -Path $HookFilePath -Raw
        $config = $raw | ConvertFrom-Json -Depth 20
    }
    catch {
        throw "Failed to parse hooks file as JSON: $HookFilePath`n$($_.Exception.Message)"
    }
}
else {
    $config = [ordered]@{}
}

$useNestedHooks = $false
if ($config.PSObject.Properties.Name -contains "hooks") {
    $useNestedHooks = $true
    if ($null -eq $config.hooks) {
        $config.hooks = [ordered]@{}
    }
}

$targetRoot = if ($useNestedHooks) { $config.hooks } else { $config }

if (-not ($targetRoot.PSObject.Properties.Name -contains $HookEvent)) {
    $targetRoot | Add-Member -MemberType NoteProperty -Name $HookEvent -Value @()
}

$eventHooks = @($targetRoot.$HookEvent)
if ($eventHooks.Count -eq 0) {
    $eventHooks = @()
}

$alreadyPresent = $false
$updatedLegacy = $false

for ($i = 0; $i -lt $eventHooks.Count; $i++) {
    $hook = $eventHooks[$i]

    if ($hook -is [string]) {
        if ($hook -eq $hookCommand) {
            $alreadyPresent = $true
        }
        elseif ($hook -match "sync-registry\.ps1") {
            $eventHooks[$i] = $hookCommand
            $updatedLegacy = $true
        }
        continue
    }

    if ($hook.PSObject.Properties.Name -contains "command") {
        if ($hook.command -eq $hookCommand) {
            $alreadyPresent = $true
        }
        elseif ($hook.command -match "sync-registry\.ps1") {
            $hook.command = $hookCommand
            $updatedLegacy = $true
        }
    }
}

if (-not $alreadyPresent -and -not $updatedLegacy) {
    $eventHooks += [ordered]@{
        type    = "command"
        command = $hookCommand
    }
    Write-Step "Added $HookEvent hook entry."
}
elseif ($updatedLegacy) {
    Write-Step "Updated existing registry sync hook entry."
}
else {
    Write-Step "Hook entry already up to date."
}

$targetRoot.$HookEvent = $eventHooks

$parentDir = Split-Path -Path $HookFilePath -Parent
if (-not (Test-Path $parentDir)) {
    New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
}

if ($PSCmdlet.ShouldProcess($HookFilePath, "Write hook configuration")) {
    $json = $config | ConvertTo-Json -Depth 20
    Set-Content -Path $HookFilePath -Value $json -Encoding UTF8
    Write-Step "Hook file updated: $HookFilePath"
}
