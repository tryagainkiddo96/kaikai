param(
    [string]$Name = ""
)

$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

if (-not (git rev-parse --is-inside-work-tree 2>$null)) {
    throw "Not inside a git repository: $repo"
}

if ([string]::IsNullOrWhiteSpace($Name)) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $Name = "checkpoint-$stamp"
}

$branch = "codex/$Name"

git add -A
$status = git status --short
if ($status) {
    git commit -m "Checkpoint: $Name" | Out-Null
}

git branch $branch | Out-Null
Write-Output "Created checkpoint branch: $branch"
