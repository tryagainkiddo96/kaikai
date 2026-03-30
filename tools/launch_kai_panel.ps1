$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (Get-Command python -ErrorAction SilentlyContinue) {
  $python = "python"
  $args = @("-m", "kai_agent.desktop_panel")
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
  $python = "py"
  $args = @("-3.12", "-m", "kai_agent.desktop_panel")
} else {
  throw "Python was not found."
}

& $python @args
