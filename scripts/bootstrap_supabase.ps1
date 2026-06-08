param(
    [string]$ProjectRef = "agookcvqnalxxcnhttmd",
    [string[]]$SchemaFiles = @(
        ".\sql\001_registry_schema.sql",
        ".\sql\002_row_level_security.sql"
    ),
    [switch]$SkipLink
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message"
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$schemaPaths = @()
foreach ($schemaFile in $SchemaFiles) {
    $schemaPath = Join-Path $repoRoot $schemaFile
    if (-not (Test-Path $schemaPath)) {
        throw "Schema file not found: $schemaPath"
    }
    $schemaPaths += $schemaPath
}

Write-Step "Schema files to apply:"
foreach ($schemaPath in $schemaPaths) {
    Write-Host "  - $schemaPath"
}

$supabaseCmd = Get-Command supabase -ErrorAction SilentlyContinue
if (-not $supabaseCmd) {
    Write-Step "Supabase CLI not found. Fallback instructions:"
    Write-Host "1) Install Supabase CLI: https://supabase.com/docs/guides/cli"
    Write-Host "2) Or apply SQL directly using psql / Supabase SQL Editor."
    Write-Host ""
    Write-Host "psql example (requires DB URL and credentials):"
    foreach ($schemaPath in $schemaPaths) {
        Write-Host "  psql <postgres-connection-string> -f `"$schemaPath`""
    }
    Write-Host ""
    Write-Host "Supabase SQL Editor:"
    Write-Host "  Open project -> SQL Editor -> run 001_registry_schema.sql then 002_row_level_security.sql"
    exit 1
}

Push-Location $repoRoot
try {
    if (-not $SkipLink) {
        Write-Step "Linking Supabase project ref: $ProjectRef"
        & supabase link --project-ref $ProjectRef
        if ($LASTEXITCODE -ne 0) {
            throw "supabase link failed with exit code $LASTEXITCODE"
        }
    }

    foreach ($schemaPath in $schemaPaths) {
        Write-Step "Applying schema via supabase db query --file: $schemaPath"
        & supabase db query --file $schemaPath
        if ($LASTEXITCODE -ne 0) {
            throw "supabase db query failed for $schemaPath with exit code $LASTEXITCODE"
        }
    }

    Write-Step "All schema files applied successfully."
    Write-Step "Run .\scripts\verify_supabase_security.ps1 before -UpsertSupabase"
}
finally {
    Pop-Location
}
