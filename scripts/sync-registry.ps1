[CmdletBinding()]
param(
    [switch]$NoScan,
    [switch]$NoDashboard,
    [switch]$UpsertSupabase,
    [string]$ScannerScriptPath,
    [string]$DashboardScriptPath
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message"
}

function Resolve-FirstExistingPath {
    param([string[]]$CandidatePaths)

    foreach ($candidate in $CandidatePaths) {
        if (-not [string]::IsNullOrWhiteSpace($candidate)) {
            $resolved = Join-Path $repoRoot $candidate
            if (Test-Path $resolved) {
                return $resolved
            }
        }
    }

    return $null
}

function Assert-ScriptExists {
    param(
        [string]$ScriptPath,
        [string]$Purpose,
        [string[]]$Examples,
        [string]$PathFlag
    )

    if ($ScriptPath) {
        return
    }

    $exampleText = ($Examples | ForEach-Object { "  - $_" }) -join [Environment]::NewLine
    throw @"
Missing $Purpose script.

Expected one of these paths:
$exampleText

Add the script, or pass an explicit path:
  .\scripts\sync-registry.ps1 -$PathFlag .\scripts\<script-name>.(ps1|py)
"@
}

function Invoke-PythonScript {
    param(
        [string]$ScriptPath,
        [string[]]$ExtraArgs
    )

    $uvCmd = Get-Command uv -ErrorAction SilentlyContinue
    if ($uvCmd) {
        & uv run python $ScriptPath @ExtraArgs
        return
    }
    & python $ScriptPath @ExtraArgs
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Write-Verbose "Repo root resolved to $repoRoot"

$scannerCandidates = @(
    $ScannerScriptPath,
    "scripts\registry_scanner.py",
    "scripts\scan-registry.ps1",
    "scripts\scan-config-registry.ps1",
    "scripts\registry-scanner.ps1"
)

$dashboardCandidates = @(
    $DashboardScriptPath,
    "scripts\generate_registry_dashboard.py",
    "scripts\generate-registry-dashboard.ps1",
    "scripts\build-registry-dashboard.ps1",
    "scripts\registry-dashboard.ps1"
)

$scannerScript = Resolve-FirstExistingPath -CandidatePaths $scannerCandidates
$dashboardScript = Resolve-FirstExistingPath -CandidatePaths $dashboardCandidates

if (-not $NoScan) {
    Assert-ScriptExists -ScriptPath $scannerScript -Purpose "scanner" -Examples $scannerCandidates[1..($scannerCandidates.Length - 1)] -PathFlag "ScannerScriptPath"
}

if (-not $NoDashboard) {
    Assert-ScriptExists -ScriptPath $dashboardScript -Purpose "dashboard generator" -Examples $dashboardCandidates[1..($dashboardCandidates.Length - 1)] -PathFlag "DashboardScriptPath"
}

if ($NoScan -and $NoDashboard) {
    Write-Step "Nothing to run (-NoScan and -NoDashboard were both set)."
    exit 0
}

$upsertStatus = $null

if (-not $NoScan) {
    Write-Step "Running scanner script: $scannerScript"
    $scannerArgs = @()
    if ($UpsertSupabase) {
        $scannerArgs += "--upsert-supabase"
        Write-Step "Supabase upsert requested via -UpsertSupabase"
    }

    if ([IO.Path]::GetExtension($scannerScript) -eq ".py") {
        if ($UpsertSupabase -and (Get-Command doppler -ErrorAction SilentlyContinue)) {
            Push-Location $repoRoot
            try {
                & doppler run --project codingagents --config dev -- python $scannerScript @scannerArgs
            }
            finally {
                Pop-Location
            }
        }
        else {
            Push-Location $repoRoot
            try {
                Invoke-PythonScript -ScriptPath $scannerScript -ExtraArgs $scannerArgs
            }
            finally {
                Pop-Location
            }
        }
    }
    else {
        & $scannerScript @scannerArgs
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Scanner script failed with exit code ${LASTEXITCODE}: $scannerScript"
    }

    if ($UpsertSupabase) {
        $snapshotPath = Join-Path $repoRoot "working\registry_snapshot.json"
        if (Test-Path $snapshotPath) {
            $snapshot = Get-Content -Path $snapshotPath -Raw | ConvertFrom-Json
            if ($snapshot.supabase_upsert) {
                $upsertStatus = $snapshot.supabase_upsert
                Write-Step "Supabase upsert status: $($upsertStatus.status)"
                $upsertStatus.PSObject.Properties | ForEach-Object {
                    if ($_.Name -ne "status") {
                        Write-Host "  $($_.Name): $($_.Value)"
                    }
                }
                if ($upsertStatus.status -eq "failed") {
                    throw "Supabase upsert failed. See per-table status above."
                }
                if ($upsertStatus.status -eq "skipped") {
                    throw "Supabase upsert skipped ($($upsertStatus.reason)). Ensure SUPABASE_SERVICE_KEY is available via Doppler."
                }
            }
        }
    }
}

if (-not $NoDashboard) {
    Write-Step "Running dashboard generator script: $dashboardScript"
    if ([IO.Path]::GetExtension($dashboardScript) -eq ".py") {
        Push-Location $repoRoot
        try {
            Invoke-PythonScript -ScriptPath $dashboardScript
        }
        finally {
            Pop-Location
        }
    }
    else {
        & $dashboardScript
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Dashboard generator script failed with exit code ${LASTEXITCODE}: $dashboardScript"
    }
}

Write-Step "Registry sync completed successfully."
