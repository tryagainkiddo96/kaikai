param(
    [Parameter(Mandatory = $true)]
    [string]$Branch
)

$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

if (-not (git rev-parse --is-inside-work-tree 2>$null)) {
    throw "Not inside a git repository: $repo"
}

$resolved = if ($Branch.StartsWith("codex/")) { $Branch } else { "codex/$Branch" }

git rev-parse --verify $resolved | Out-Null
git checkout $resolved | Out-Null

Write-Output "Restored checkpoint branch: $resolved"
