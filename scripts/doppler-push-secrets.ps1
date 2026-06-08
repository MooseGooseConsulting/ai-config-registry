param(
    [string]$Project = "codingagents",
    [string]$Config = "dev",
    [string]$ManifestPath,
    [switch]$DryRun,
    [switch]$ShowSourceHints
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "doppler-manifest.ps1")

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

function Resolve-SourceHint {
    param(
        [object]$Manifest,
        [string[]]$SourceRefs
    )

    if (-not $ShowSourceHints -or -not $SourceRefs -or -not $Manifest.source_catalog) {
        return ""
    }

    $labels = @()
    foreach ($ref in $SourceRefs) {
        $catalogEntry = $Manifest.source_catalog.PSObject.Properties[$ref]
        if ($catalogEntry -and $catalogEntry.Value.label) {
            $labels += [string]$catalogEntry.Value.label
        }
        else {
            $labels += $ref
        }
    }

    if ($labels.Count -eq 0) {
        return ""
    }
    return " (sources: $($labels -join ', '))"
}

function Invoke-DopplerSecretSet {
    param(
        [string]$Key,
        [string]$PlainValue,
        [string]$ProjectName,
        [string]$ConfigName
    )

    # Send the value over stdin. Do not construct KEY=value or place the secret value in argv.
    Write-Output -NoEnumerate $PlainValue |
        & doppler secrets set $Key --project $ProjectName --config $ConfigName --no-read-env --silent |
        Out-Null

    if ($LASTEXITCODE -ne 0) {
        throw "Doppler failed to set $Key."
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

$manifestEntries = @(Get-ManifestSecretEntries -Manifest $manifest)
$expectedKeys = @($manifestEntries | ForEach-Object { $_.DopplerKey } | Sort-Object -Unique)
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

Write-Step "Target: project '$Project' config '$Config'"
Write-Step "Manifest: $ManifestPath"
Write-Step "Keys to process: $($expectedKeys.Count)"
if ($DryRun) {
    Write-Host "Dry-run mode enabled. No secrets will be written."
}

foreach ($entry in $manifestEntries) {
    $key = $entry.DopplerKey
    $sourceHint = Resolve-SourceHint -Manifest $manifest -SourceRefs $entry.SourceRefs

    if ($DryRun) {
        Write-Host "[DRY-RUN] Would prompt and set key: $key$sourceHint"
        continue
    }

    Write-Host ""
    Write-Host "Enter value for $key$sourceHint"
    $secure = Read-Host -AsSecureString "Secret value"
    $plainValue = Get-PlainTextFromSecureString -SecureValue $secure

    if ([string]::IsNullOrWhiteSpace($plainValue)) {
        Write-Host "Skipped $key (empty value)."
        continue
    }

    try {
        Invoke-DopplerSecretSet -Key $key -PlainValue $plainValue -ProjectName $Project -ConfigName $Config
        Write-Host "Set $key"
    }
    finally {
        $plainValue = $null
    }
}

Write-Host ""
Write-Step "Completed Doppler push workflow."
