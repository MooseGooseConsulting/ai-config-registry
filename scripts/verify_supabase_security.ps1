param(
    [string]$ProjectRef = "agookcvqnalxxcnhttmd",
    [switch]$SchemaOnly
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message"
}

function Test-OutputTrue {
    param([string]$Output)
    return ($Output -match "(?i)\b(t|true)\b")
}

function Test-OutputFalse {
    param([string]$Output)
    return ($Output -match "(?i)\b(f|false)\b")
}

function Get-HttpStatusCode {
    param([object]$ErrorRecord)
    $response = $ErrorRecord.Exception.Response
    if ($response -and $response.StatusCode) {
        return [int]$response.StatusCode
    }
    return $null
}

$tables = @(
    "ecosystems",
    "skills",
    "mcp_servers",
    "hooks",
    "secrets_manifest",
    "cli_tools"
)

$supabaseCmd = Get-Command supabase -ErrorAction SilentlyContinue
if ($supabaseCmd) {
    Push-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))
    try {
        Write-Step "Checking Row Level Security and revoked anon/authenticated grants via Supabase CLI"
        $allOk = $true
        foreach ($table in $tables) {
            $sql = @"
SELECT c.relrowsecurity AS rls_enabled
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relname = '$table';
"@
            $rlsQueryOutput = & supabase db query $sql 2>&1
            $rlsQueryExitCode = $LASTEXITCODE
            $output = $rlsQueryOutput | Out-String
            if ($rlsQueryExitCode -ne 0) {
                Write-Host "[FAIL] $table - RLS query failed"
                $allOk = $false
                continue
            }
            if (Test-OutputTrue -Output $output) {
                Write-Host "[OK] $table -> RLS enabled"
            }
            else {
                Write-Host "[FAIL] $table -> RLS NOT enabled. Apply sql/002_row_level_security.sql"
                $allOk = $false
            }

            $grantSql = @"
SELECT
  has_table_privilege('anon', 'public.$table', 'SELECT') AS anon_select,
  has_table_privilege('authenticated', 'public.$table', 'SELECT') AS auth_select;
"@
            $grantQueryOutput = & supabase db query $grantSql 2>&1
            $grantQueryExitCode = $LASTEXITCODE
            $grantOutput = $grantQueryOutput | Out-String
            if ($grantQueryExitCode -ne 0) {
                Write-Host "[FAIL] $table - grant query failed"
                $allOk = $false
                continue
            }
            if (Test-OutputFalse -Output $grantOutput -and -not (Test-OutputTrue -Output $grantOutput)) {
                Write-Host "[OK] $table -> anon/authenticated SELECT grants revoked"
            }
            else {
                Write-Host "[FAIL] $table -> anon/authenticated SELECT grant still present"
                $allOk = $false
            }
        }
        if (-not $allOk) {
            Write-Host ""
            Write-Host "Run: .\scripts\bootstrap_supabase.ps1 (applies 001 + 002)"
            exit 1
        }
        Write-Step "Schema-level RLS and grant checks passed."
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Host "[FAIL] Supabase CLI is required to verify schema RLS/grants."
    Write-Host "       Install Supabase CLI or run bootstrap/verification from a machine that has it."
    exit 1
}

$supabaseUrl = $env:SUPABASE_URL
if (-not $supabaseUrl -and $ProjectRef) {
    $supabaseUrl = "https://$ProjectRef.supabase.co"
}
$serviceKey = $env:SUPABASE_SERVICE_KEY
$anonKey = $env:SUPABASE_ANON_KEY

if ($SchemaOnly) {
    Write-Host "[WARN] -SchemaOnly set; anon key denial was not required for this partial verification."
    Write-Step "Security checks completed (schema-only partial mode)."
    exit 0
}

if (-not $supabaseUrl -or -not $serviceKey -or -not $anonKey) {
    Write-Host "[FAIL] Cannot complete strict verification without SUPABASE_URL, SUPABASE_SERVICE_KEY, and SUPABASE_ANON_KEY."
    Write-Host "       Use -SchemaOnly only when you intentionally want the partial RLS/grant check."
    exit 1
}

Write-Step "Testing service-role reachability and anon key denial"
$serviceHeaders = @{
    apikey        = $serviceKey
    Authorization = "Bearer $serviceKey"
}
foreach ($table in $tables) {
    $uri = "$($supabaseUrl.TrimEnd('/'))/rest/v1/$table?select=id&limit=1"
    try {
        $null = Invoke-WebRequest -Uri $uri -Headers $serviceHeaders -Method GET
        Write-Host "[OK] $table reachable with service_role (expected)"
    }
    catch {
        Write-Host "[FAIL] $table service_role access: $($_.Exception.Message)"
        exit 1
    }
}

$anonHeaders = @{
    apikey        = $anonKey
    Authorization = "Bearer $anonKey"
}
$anonBlocked = $true
foreach ($table in $tables) {
    $uri = "$($supabaseUrl.TrimEnd('/'))/rest/v1/$table?select=id&limit=1"
    try {
        $response = Invoke-WebRequest -Uri $uri -Headers $anonHeaders -Method GET
        Write-Host "[FAIL] $table -> anon key CAN read data (HTTP $($response.StatusCode))"
        $anonBlocked = $false
    }
    catch {
        $statusCode = Get-HttpStatusCode -ErrorRecord $_
        if ($statusCode -in @(401, 403, 404)) {
            Write-Host "[OK] $table -> anon key denied (HTTP $statusCode)"
        }
        else {
            Write-Host "[FAIL] $table -> anon denial check inconclusive: $($_.Exception.Message)"
            $anonBlocked = $false
        }
    }
}

if (-not $anonBlocked) {
    Write-Host ""
    Write-Host "CRITICAL: anon key can read registry tables or denial could not be proven. Apply sql/002_row_level_security.sql"
    exit 1
}

Write-Step "Security checks completed; anon key denial verified."
exit 0
