param()

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $repoRoot
try {
    git config core.hooksPath .githooks
    Write-Host "Git hooks installed: core.hooksPath=.githooks"
    Write-Host "Pre-commit: python scripts/secret_guard.py --staged"
    Write-Host "Pre-push: python scripts/secret_guard.py --range <remote..local>"
}
finally {
    Pop-Location
}
