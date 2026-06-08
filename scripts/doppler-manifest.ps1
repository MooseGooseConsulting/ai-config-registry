function Get-ManifestSecretEntries {
    param([object]$Manifest)

    $entries = @()
    foreach ($entry in @($Manifest.secrets)) {
        if (-not $entry.doppler_key) {
            continue
        }

        $sourceRefs = @()
        if ($entry.source_refs) {
            $sourceRefs = @($entry.source_refs)
        }
        elseif ($entry.source_paths) {
            # v1 compatibility: keep old manifests readable without printing machine paths.
            $sourceRefs = @($entry.source_paths | ForEach-Object { "legacy_source_path" })
        }

        $entries += [pscustomobject]@{
            DopplerKey = [string]$entry.doppler_key
            SourceRefs = $sourceRefs
            Required = [bool]$entry.required
        }
    }
    return $entries
}

function Resolve-DopplerManifestTarget {
    param(
        [string]$RepoRoot,
        [string]$ManifestPath,
        [string]$DefaultProject = "codingagents",
        [string]$DefaultConfig = "dev"
    )

    if (-not $ManifestPath) {
        if (-not $RepoRoot) {
            throw "RepoRoot is required when ManifestPath is not provided."
        }
        $ManifestPath = Join-Path $RepoRoot "working\doppler-migration-manifest.json"
    }

    $project = $DefaultProject
    $config = $DefaultConfig
    if (Test-Path $ManifestPath) {
        $manifest = Get-Content -Path $ManifestPath -Raw | ConvertFrom-Json
        if ($manifest.project) {
            $project = [string]$manifest.project
        }
        if ($manifest.config) {
            $config = [string]$manifest.config
        }
    }

    return [pscustomobject]@{
        Project = $project
        Config = $config
        ManifestPath = $ManifestPath
    }
}
