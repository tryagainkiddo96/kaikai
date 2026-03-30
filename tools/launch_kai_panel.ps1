$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Test-WindowTitleRunning {
  param(
    [string]$TitleFragment
  )

  $needle = $TitleFragment.ToLowerInvariant()
  foreach ($process in Get-Process -ErrorAction SilentlyContinue) {
    try {
      $title = [string]$process.MainWindowTitle
      if (-not [string]::IsNullOrWhiteSpace($title) -and $title.ToLowerInvariant().Contains($needle)) {
        return $true
      }
    } catch {
      # Ignore processes without a main window.
    }
  }

  return $false
}

function Test-TcpPortOpen {
  param(
    [string]$TargetHost,
    [int]$Port
  )

  try {
    $client = [System.Net.Sockets.TcpClient]::new()
    $async = $client.BeginConnect($TargetHost, $Port, $null, $null)
    if ($async.AsyncWaitHandle.WaitOne(500)) {
      $client.EndConnect($async)
      $client.Close()
      return $true
    }
    $client.Close()
  } catch {
    return $false
  }

  return $false
}

function Wait-ForTcpPort {
  param(
    [string]$TargetHost,
    [int]$Port,
    [int]$TimeoutSeconds = 8
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    if (Test-TcpPortOpen -TargetHost $TargetHost -Port $Port) {
      return $true
    }
    Start-Sleep -Milliseconds 300
  }

  return $false
}

function Ensure-OllamaRunning {
  $ollamaHost = "127.0.0.1"
  $ollamaPort = 11434
  if (Test-TcpPortOpen -TargetHost $ollamaHost -Port $ollamaPort) {
    return
  }

  $ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
  if ($null -eq $ollamaCmd) {
    return
  }

  Start-Process -FilePath $ollamaCmd.Source -ArgumentList @("serve") -WorkingDirectory $repoRoot -WindowStyle Hidden | Out-Null
  Wait-ForTcpPort -TargetHost $ollamaHost -Port $ollamaPort -TimeoutSeconds 10 | Out-Null
}

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

if (Get-Command python -ErrorAction SilentlyContinue) {
  $python = (Get-Command python).Source
  $pythonDir = Split-Path -Parent $python
  $pythonw = Join-Path $pythonDir "pythonw.exe"
  if (Test-Path $pythonw) {
    $launcher = $pythonw
  } else {
    $launcher = $python
  }
  $args = @("-m", "kai_agent.desktop_panel", "--workspace", $repoRoot)
} elseif (Get-Command pyw -ErrorAction SilentlyContinue) {
  $launcher = "pyw"
  $args = @("-3", "-m", "kai_agent.desktop_panel", "--workspace", $repoRoot)
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
  $launcher = "py"
  $args = @("-3", "-m", "kai_agent.desktop_panel", "--workspace", $repoRoot)
} else {
  throw "Python was not found."
}

Ensure-OllamaRunning
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
if ((Test-WindowTitleRunning -TitleFragment "Kai Command Center") -or (Test-WindowTitleRunning -TitleFragment "Kai Nexus")) {
  Write-Host "Kai panel is already running."
  exit 0
}
Start-Process -FilePath $launcher -ArgumentList $args -WorkingDirectory $repoRoot -WindowStyle Hidden | Out-Null
