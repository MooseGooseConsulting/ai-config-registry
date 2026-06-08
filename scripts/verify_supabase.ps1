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
        Write-Step "Querying table counts via Supabase CLI"
        $allOk = $true
        foreach ($table in $tables) {
            $sql = "SELECT COUNT(*) AS row_count FROM public.$table;"
            $output = & supabase db query $sql 2>&1
            if ($LASTEXITCODE -ne 0) {
                Write-Host "[FAIL] $table - query failed"
                $allOk = $false
                continue
            }
            Write-Host "[OK] $table -> $output"
        }
        if (-not $allOk) { exit 1 }
        Write-Step "All table count queries completed."
        exit 0
    }
    finally {
        Pop-Location
    }
}

$supabaseUrl = $env:SUPABASE_URL
$serviceKey = $env:SUPABASE_SERVICE_KEY
if (-not $supabaseUrl -or -not $serviceKey) {
    throw "Supabase CLI unavailable and SUPABASE_URL/SUPABASE_SERVICE_KEY not set. Run with Doppler or install Supabase CLI."
}

Write-Step "Querying table counts via REST API"
$headers = @{
    apikey         = $serviceKey
    Authorization  = "Bearer $serviceKey"
    Prefer         = "count=exact"
    Range          = "0-0"
}

$allOk = $true
foreach ($table in $tables) {
    $uri = "$($supabaseUrl.TrimEnd('/'))/rest/v1/$table?select=id"
    try {
        $response = Invoke-WebRequest -Uri $uri -Headers $headers -Method GET
        $countHeader = $response.Headers["Content-Range"]
        if ($countHeader -match "/(\d+)$") {
            Write-Host "[OK] $table -> $($Matches[1]) rows"
        }
        else {
            Write-Host "[OK] $table -> response received (count header: $countHeader)"
        }
    }
    catch {
        Write-Host "[FAIL] $table - $($_.Exception.Message)"
        $allOk = $false
    }
}

if (-not $allOk) { exit 1 }
Write-Step "All table count queries completed."
exit 0
