param(
    [switch]$LegacyMode
)

$ErrorActionPreference = "Stop"

if ($env:KAI_LAUNCHER_HIDDEN -ne "1") {
    $env:KAI_LAUNCHER_HIDDEN = "1"
    Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-ExecutionPolicy", "Bypass",
        "-File", $PSCommandPath
    ) -WindowStyle Hidden
    exit 0
}

$root = Split-Path -Parent $PSScriptRoot
$unifiedExe = Join-Path $root "dist\KaiUnified.exe"
$sourceUnifiedApp = Join-Path $root "kai_agent\kai_unified_app.py"
$probeScript = Join-Path $PSScriptRoot "probe_kai_bridge.py"
$useLegacy = $LegacyMode -or ($env:KAI_LEGACY_STACK -eq "1")

$bridgeScript = Join-Path $root "bridge\server.py"
$assistantModule = "kai_agent.assistant"
$companionPath = Join-Path $root "kai_companion"
$scenePath = $env:KAI_SCENE
if ([string]::IsNullOrWhiteSpace($scenePath)) {
    $scenePath = "res://scenes/kai_3d.tscn"
}
$bridgeHost = "127.0.0.1"
$bridgePort = 8765
$startCompanion = $env:KAI_START_COMPANION
if ([string]::IsNullOrWhiteSpace($startCompanion)) {
    $startCompanion = "0"
}
$startAssistant = $env:KAI_START_ASSISTANT
if ([string]::IsNullOrWhiteSpace($startAssistant)) {
    $startAssistant = "0"
}
$model = $env:KAI_MODEL
if ([string]::IsNullOrWhiteSpace($model)) {
    $model = "qwen3:4b-q4_K_M"
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

function Resolve-Executable {
    param(
        [string[]]$Candidates,
        [string]$Name
    )

    foreach ($candidate in $Candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) {
            continue
        }
        if (Test-Path $candidate) {
            return (Resolve-Path $candidate).Path
        }
    }

    $resolved = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -ne $resolved) {
        return $resolved.Source
    }

    throw "Could not find $Name. Add it to PATH or set the executable path in this launcher."
}

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
            # Ignore processes that do not expose a main window.
        }
    }

    return $false
}

function Get-LatestWriteTime {
    param(
        [string[]]$Paths
    )

    $latest = [datetime]::MinValue
    foreach ($path in $Paths) {
        if ([string]::IsNullOrWhiteSpace($path) -or -not (Test-Path $path)) {
            continue
        }
        $candidate = (Get-Item $path).LastWriteTime
        if ($candidate -gt $latest) {
            $latest = $candidate
        }
    }

    return $latest
}

function Wait-ForTcpPort {
    param(
        [string]$TargetHost,
        [int]$Port,
        [int]$TimeoutSeconds = 15
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
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
            Start-Sleep -Milliseconds 300
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

function Stop-KaiProcesses {
    param([System.Diagnostics.Process[]]$Processes)

    foreach ($process in $Processes) {
        if ($null -ne $process -and -not $process.HasExited) {
            try {
                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            } catch {
                # Best effort cleanup.
            }
        }
    }
}

$python = Resolve-Executable -Candidates @(
    $env:KAI_PYTHON,
    "C:\Users\7nujy6xc\AppData\Local\Programs\Python\Python312\python.exe",
    "C:\Users\7nujy6xc\AppData\Local\Programs\Python\Python311\python.exe"
) -Name "python"

$preferSourceUnified = $false
if ($env:KAI_FORCE_SOURCE -eq "1") {
    $preferSourceUnified = $true
} elseif ((Test-Path $unifiedExe) -and (Test-Path $sourceUnifiedApp)) {
    $latestUnifiedSource = Get-LatestWriteTime -Paths @(
        $sourceUnifiedApp,
        (Join-Path $root "kai_agent\desktop_panel_unified.py"),
        (Join-Path $root "kai_agent\assistant.py"),
        (Join-Path $root "kai_agent\bridge_server.py"),
        (Join-Path $root "kai_agent\bridge_client.py"),
        (Join-Path $root "kai_agent\desktop_tools.py"),
        (Join-Path $root "kai_companion\project.godot"),
        (Join-Path $root "kai_companion\scripts\kai_3d.gd"),
        (Join-Path $root "bridge\server.py")
    )
    $preferSourceUnified = $latestUnifiedSource -gt (Get-Item $unifiedExe).LastWriteTime
}

if (Test-WindowTitleRunning -TitleFragment "Kai Command Center") {
    Write-Host "Kai Command Center is already running."
    exit 0
}

if ((-not $useLegacy) -and (Test-Path $unifiedExe) -and (-not $preferSourceUnified)) {
    $unified = Start-Process -FilePath $unifiedExe -WorkingDirectory (Split-Path -Parent $unifiedExe) -PassThru
    Start-Sleep -Seconds 8
    if ($unified.HasExited) {
        throw "KaiUnified exited during startup."
    }
    if (-not (Test-TcpPortOpen -TargetHost $bridgeHost -Port $bridgePort)) {
        throw "KaiUnified started but bridge port 8765 did not open."
    }
    $probeOutput = & $python $probeScript --url "ws://$bridgeHost`:$bridgePort" --timeout 3 2>$null
    if (($probeOutput -join "`n").Trim() -ne "ok") {
        throw "KaiUnified started but bridge probe failed."
    }
    Write-Host "KaiUnified launched from $unifiedExe"
    exit 0
}

if (-not $useLegacy) {
    $unifiedArgs = @("-m", "kai_agent.kai_unified_app", "--workspace", $root, "--scene", $scenePath)
    $unified = Start-Process -FilePath $python -ArgumentList $unifiedArgs -WorkingDirectory $root -PassThru
    Start-Sleep -Seconds 8
    if ($unified.HasExited) {
        throw "Kai unified source app exited during startup."
    }
    if (-not (Test-TcpPortOpen -TargetHost $bridgeHost -Port $bridgePort)) {
        throw "Kai unified source app started but bridge port 8765 did not open."
    }
    $probeOutput = & $python $probeScript --url "ws://$bridgeHost`:$bridgePort" --timeout 3 2>$null
    if (($probeOutput -join "`n").Trim() -ne "ok") {
        throw "Kai unified source app started but bridge probe failed."
    }
    Write-Host "Kai unified source app launched from $sourceUnifiedApp"
    exit 0
}

$godot = Resolve-Executable -Candidates @(
    $env:KAI_GODOT,
    "C:\Users\7nujy6xc\AppData\Local\Microsoft\WinGet\Links\godot.exe",
    "C:\Program Files\Godot\Godot.exe"
) -Name "godot"

$processes = @()
$totalRamGb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
if ([string]::IsNullOrWhiteSpace($env:KAI_MODEL)) {
    $model = Select-KaiModel
    $env:KAI_MODEL = $model
}
if ([string]::IsNullOrWhiteSpace($env:OLLAMA_NUM_PARALLEL)) {
    $env:OLLAMA_NUM_PARALLEL = if ($totalRamGb -le 8.5) { "1" } else { "2" }
}
if ([string]::IsNullOrWhiteSpace($env:OLLAMA_MAX_LOADED_MODELS)) {
    $env:OLLAMA_MAX_LOADED_MODELS = "1"
}

try {
    if (-not (Test-TcpPortOpen -TargetHost $bridgeHost -Port $bridgePort)) {
        $bridge = Start-Process -FilePath $python -ArgumentList $bridgeScript -WorkingDirectory $root -PassThru
        $processes += $bridge

        if (-not (Wait-ForTcpPort -TargetHost $bridgeHost -Port $bridgePort -TimeoutSeconds 10)) {
            throw "Kai bridge did not become ready on ws://$bridgeHost`:$bridgePort"
        }
    } else {
        Write-Host "Kai bridge already listening on ws://$bridgeHost`:$bridgePort"
    }

    if ($startAssistant -eq "1") {
        $assistant = Start-Process -FilePath $python -ArgumentList @(
            "-m", $assistantModule,
            "--workspace", $root,
            "--model", $model
        ) -WorkingDirectory $root -PassThru
        $processes += $assistant
        Start-Sleep -Seconds 1
    }

    if ($startCompanion -eq "1") {
        $companionArgs = @("--path", $companionPath)
        if (-not [string]::IsNullOrWhiteSpace($scenePath)) {
            $companionArgs += $scenePath
        }
        if (Test-WindowTitleRunning -TitleFragment "Kai Companion") {
            Write-Host "Kai companion is already running."
        } else {
            $companion = Start-Process -FilePath $godot -ArgumentList $companionArgs -WorkingDirectory $companionPath -PassThru
            $processes += $companion
            Start-Sleep -Seconds 2
            if ($companion.HasExited) {
                throw "Kai companion exited during startup."
            }
        }
    } else {
        Write-Host "Kai companion skipped (panel-only mode)."
    }

    Write-Host "Kai stack launched."
    Write-Host "Bridge: ws://$bridgeHost`:$bridgePort"
    if ($startAssistant -eq "1") {
        Write-Host "Assistant model: $model"
    } else {
        Write-Host "Assistant model: disabled (desktop companion mode)"
    }
    if ($startCompanion -eq "1") {
        Write-Host "Companion: $companionPath"
        if (-not [string]::IsNullOrWhiteSpace($scenePath)) {
            Write-Host "Scene: $scenePath"
        }
    }
}
catch {
    Write-Host "Kai stack launch failed: $($_.Exception.Message)" -ForegroundColor Red
    Stop-KaiProcesses -Processes $processes
    throw
}
