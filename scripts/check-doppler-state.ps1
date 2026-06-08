param(
    [string]$Project = "codingagents",
    [string]$Config = "dev"
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message"
}

$expectedKeys = @(
    "MORPH_API_KEY",
    "TAVILY_API_KEY",
    "EXA_API_KEY",
    "CONTEXT7_API_KEY",
    "STITCH_GOOGLE_API_KEY",
    "GITHUB_PERSONAL_ACCESS_TOKEN",
    "GOOGLE_OAUTH_CLIENT_ID",
    "GOOGLE_OAUTH_CLIENT_SECRET",
    "SUPABASE_SERVICE_KEY",
    "APIFY_TOKEN",
    "PLAID_CLIENT_ID",
    "PLAID_SECRET"
)

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

$missing = @()
foreach ($expected in $expectedKeys) {
    if ($existingLookup.ContainsKey($expected)) {
        Write-Host "[OK] $expected"
    }
    else {
        Write-Host "[MISSING] $expected"
        $missing += $expected
    }
}

Write-Host ""
if ($missing.Count -eq 0) {
    Write-Host "Check passed: all expected keys exist."
    exit 0
}

Write-Host "Check failed: $($missing.Count) expected key(s) missing."
exit 2
