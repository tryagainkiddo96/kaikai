$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Select-KaiModel {
  param(
    [string]$DefaultModel = "qwen3:4b-q4_K_M"
  )

  try {
    $listOutput = & ollama list 2>$null
    if (-not $listOutput) {
      return $DefaultModel
    }
    $available = @()
    foreach ($line in $listOutput) {
      if ($line -match "^\s*NAME\s+") {
        continue
      }
      $name = ($line -split "\s+")[0].Trim()
      if (-not [string]::IsNullOrWhiteSpace($name)) {
        $available += $name
      }
    }
    foreach ($preferred in @("qwen3:4b-q4_K_M", "llama3:latest", "mistral:latest", "llama2:latest")) {
      if ($available -contains $preferred) {
        return $preferred
      }
    }
  } catch {
    return $DefaultModel
  }
  return $DefaultModel
}

$totalRamGb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
if ([string]::IsNullOrWhiteSpace($env:KAI_MODEL)) {
  $env:KAI_MODEL = Select-KaiModel
}
if ([string]::IsNullOrWhiteSpace($env:OLLAMA_NUM_PARALLEL)) {
  $env:OLLAMA_NUM_PARALLEL = if ($totalRamGb -le 8.5) { "1" } else { "2" }
}
if ([string]::IsNullOrWhiteSpace($env:OLLAMA_MAX_LOADED_MODELS)) {
  $env:OLLAMA_MAX_LOADED_MODELS = "1"
}

$python = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }
$args = if ($python -eq "py") { @("-3", "-m", "kai_agent.widget_server") } else { @("-m", "kai_agent.widget_server") }

Start-Process -FilePath $python -ArgumentList $args -WorkingDirectory $repoRoot
Start-Sleep -Seconds 2
Start-Process "http://127.0.0.1:8127"
