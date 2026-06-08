param(
    [string]$Project = "codingagents",
    [string]$Config = "dev",
    [string]$ManifestPath,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message"
}

function Get-PlainTextFromSecureString {
    param([System.Security.SecureString]$SecureValue)

    if (-not $SecureValue) {
        return ""
    }

    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
if (-not $ManifestPath) {
    $ManifestPath = Join-Path $repoRoot "working\doppler-migration-manifest.json"
}

if (-not (Test-Path $ManifestPath)) {
    throw "Migration manifest not found: $ManifestPath"
}

$manifest = Get-Content -Path $ManifestPath -Raw | ConvertFrom-Json
if (-not $manifest.secrets) {
    throw "Manifest contains no secrets array: $ManifestPath"
}

if ($manifest.project) { $Project = $manifest.project }
if ($manifest.config) { $Config = $manifest.config }

$expectedKeys = @($manifest.secrets | ForEach-Object { $_.doppler_key })
if ($expectedKeys.Count -eq 0) {
    throw "No doppler_key entries found in manifest."
}

if (-not (Get-Command doppler -ErrorAction SilentlyContinue)) {
    throw "Doppler CLI is not installed or not on PATH."
}

Write-Step "Checking Doppler authentication"
try {
    & doppler whoami | Out-Null
}
catch {
    throw "Not authenticated with Doppler. Run 'doppler login' and retry."
}

Write-Step "Target: project '$Project' config '$Config' (manifest: $ManifestPath)"
Write-Step "Keys to process: $($expectedKeys.Count)"
if ($DryRun) {
    Write-Host "Dry-run mode enabled. No secrets will be written."
}

foreach ($entry in $manifest.secrets) {
    $key = $entry.doppler_key
    $sourcePaths = @($entry.source_paths)
    $pathHint = if ($sourcePaths.Count -gt 0) { " (sources: $($sourcePaths -join ', '))" } else { "" }

    if ($DryRun) {
        Write-Host "[DRY-RUN] Would prompt and set key: $key$pathHint"
        continue
    }

    Write-Host ""
    Write-Host "Enter value for $key$pathHint"
    $secure = Read-Host -AsSecureString "Secret value"
    $plainValue = Get-PlainTextFromSecureString -SecureValue $secure

    if ([string]::IsNullOrWhiteSpace($plainValue)) {
        Write-Host "Skipped $key (empty value)."
        continue
    }

    try {
        & doppler secrets set "$key=$plainValue" --project $Project --config $Config | Out-Null
        Write-Host "Set $key"
    }
    finally {
        $plainValue = $null
    }
}

Write-Host ""
Write-Step "Completed Doppler push workflow."
