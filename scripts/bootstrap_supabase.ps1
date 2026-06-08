param(
    [string]$ProjectRef = "agookcvqnalxxcnhttmd",
    [string]$SchemaFile = ".\sql\001_registry_schema.sql",
    [switch]$SkipLink
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message"
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$schemaPath = Join-Path $repoRoot $SchemaFile

if (-not (Test-Path $schemaPath)) {
    throw "Schema file not found: $schemaPath"
}

Write-Step "Using schema file: $schemaPath"

$supabaseCmd = Get-Command supabase -ErrorAction SilentlyContinue
if (-not $supabaseCmd) {
    Write-Step "Supabase CLI not found. Fallback instructions:"
    Write-Host "1) Install Supabase CLI: https://supabase.com/docs/guides/cli"
    Write-Host "2) Or apply SQL directly using psql / Supabase SQL Editor."
    Write-Host ""
    Write-Host "psql example (requires DB URL and credentials):"
    Write-Host "  psql <postgres-connection-string> -f `"$schemaPath`""
    Write-Host ""
    Write-Host "Supabase SQL Editor:"
    Write-Host "  Open project -> SQL Editor -> paste contents of 001_registry_schema.sql -> Run"
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

    Write-Step "Applying schema via supabase db query --file"
    & supabase db query --file $schemaPath
    if ($LASTEXITCODE -ne 0) {
        throw "supabase db query failed with exit code $LASTEXITCODE"
    }

    Write-Step "Schema applied successfully."
}
finally {
    Pop-Location
}
