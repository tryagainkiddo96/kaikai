$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$python = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }
$args = if ($python -eq "py") { @("-3", "-m", "kai_agent.widget_server") } else { @("-m", "kai_agent.widget_server") }

Start-Process -FilePath $python -ArgumentList $args -WorkingDirectory $repoRoot
Start-Sleep -Seconds 2
Start-Process "http://127.0.0.1:8127"
