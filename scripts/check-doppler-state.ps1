param(
    [string]$Project = "codingagents",
    [string]$Config = "dev",
    [string]$ManifestPath
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "doppler-manifest.ps1")

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message"
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
if (-not $ManifestPath) {
    $ManifestPath = Join-Path $repoRoot "working\doppler-migration-manifest.json"
}
if (-not (Test-Path $ManifestPath)) {
    throw "Migration manifest not found: $ManifestPath"
}

$manifest = Get-Content -Path $ManifestPath -Raw | ConvertFrom-Json
if ($manifest.project) { $Project = $manifest.project }
if ($manifest.config) { $Config = $manifest.config }

$expectedEntries = @(Get-ManifestSecretEntries -Manifest $manifest)
if ($expectedEntries.Count -eq 0) {
    throw "No doppler_key entries found in manifest."
}

if (-not (Get-Command doppler -ErrorAction SilentlyContinue)) {
    throw "Doppler CLI is not installed or not on PATH."
}

Write-Step "Checking Doppler authentication"
$authOk = $true
try {
    & doppler whoami | Out-Null
}
catch {
    $authOk = $false
}

if (-not $authOk) {
    Write-Host "Auth: FAILED (run 'doppler login')"
    exit 1
}

Write-Host "Auth: OK"
Write-Step "Reading secret key names from project '$Project' config '$Config'"

$rawJson = & doppler secrets --only-names --json --project $Project --config $Config --no-read-env
if ($LASTEXITCODE -ne 0) {
    throw "Unable to read secrets from Doppler project '$Project' config '$Config'."
}

$parsed = $rawJson | ConvertFrom-Json
$existingNames = @()
if ($parsed -is [System.Collections.IDictionary]) {
    $existingNames = @($parsed.Keys)
}
else {
    $existingNames = @($parsed | Get-Member -MemberType NoteProperty | Select-Object -ExpandProperty Name)
}
$existingLookup = @{}
foreach ($name in $existingNames) {
    $existingLookup[$name.Trim()] = $true
}

$missingRequired = @()
$missingVerification = @()
foreach ($entry in $expectedEntries) {
    $expected = $entry.DopplerKey
    $category = if ($entry.Required) { "required" } else { "verification" }
    if ($existingLookup.ContainsKey($expected)) {
        Write-Host "[OK][$category] $expected"
    }
    else {
        Write-Host "[MISSING][$category] $expected"
        if ($entry.Required) {
            $missingRequired += $expected
        }
        else {
            $missingVerification += $expected
        }
    }
}

Write-Host ""
if (($missingRequired.Count + $missingVerification.Count) -eq 0) {
    Write-Host "Check passed: all expected manifest keys exist."
    exit 0
}

Write-Host "Check failed: $($missingRequired.Count) required and $($missingVerification.Count) verification key(s) missing."
exit 2
