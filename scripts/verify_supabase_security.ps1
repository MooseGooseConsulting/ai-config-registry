param(
    [string]$ProjectRef = "agookcvqnalxxcnhttmd"
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message"
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
        Write-Step "Checking Row Level Security via Supabase CLI"
        $allOk = $true
        foreach ($table in $tables) {
            $sql = @"
SELECT c.relname AS table_name, c.relrowsecurity AS rls_enabled
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relname = '$table';
"@
            $output = & supabase db query $sql 2>&1 | Out-String
            if ($LASTEXITCODE -ne 0) {
                Write-Host "[FAIL] $table - RLS query failed"
                $allOk = $false
                continue
            }
            if ($output -match "t\b|true|1") {
                Write-Host "[OK] $table -> RLS enabled"
            }
            else {
                Write-Host "[FAIL] $table -> RLS NOT enabled. Apply sql/002_row_level_security.sql"
                $allOk = $false
            }
        }
        if (-not $allOk) {
            Write-Host ""
            Write-Host "Run: .\scripts\bootstrap_supabase.ps1 (applies 001 + 002)"
            exit 1
        }
        Write-Step "RLS checks passed."
        exit 0
    }
    finally {
        Pop-Location
    }
}

$supabaseUrl = $env:SUPABASE_URL
$serviceKey = $env:SUPABASE_SERVICE_KEY
$anonKey = $env:SUPABASE_ANON_KEY

if (-not $supabaseUrl -or -not $serviceKey) {
    throw "Supabase CLI unavailable and SUPABASE_URL/SUPABASE_SERVICE_KEY not set."
}

Write-Step "Supabase CLI not found; limited REST checks only"
Write-Host "[WARN] Cannot verify RLS without Supabase CLI. Install CLI and re-run."
Write-Host "[INFO] Service-role table access check:"

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

if ($anonKey) {
    Write-Step "Testing anon key denial (must fail for all tables)"
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
            Write-Host "[OK] $table -> anon key denied ($($_.Exception.Message))"
        }
    }
    if (-not $anonBlocked) {
        Write-Host ""
        Write-Host "CRITICAL: anon key can read registry tables. Apply sql/002_row_level_security.sql"
        exit 1
    }
}
else {
    Write-Host "[WARN] SUPABASE_ANON_KEY not set; skipping anon denial test."
    Write-Host "       Set it temporarily to confirm RLS, or use Supabase CLI for full check."
}

Write-Step "Security checks completed (partial without CLI)."
exit 0
