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
$bridgeScript = Join-Path $root "bridge\server.py"
$assistantModule = "kai_agent.assistant"
$companionPath = Join-Path $root "kai_companion"
$scenePath = $env:KAI_SCENE
if ([string]::IsNullOrWhiteSpace($scenePath)) {
    $scenePath = "res://scenes/kai_3d.tscn"
}
$bridgeHost = "127.0.0.1"
$bridgePort = 8765
$startAssistant = $env:KAI_START_ASSISTANT
if ([string]::IsNullOrWhiteSpace($startAssistant)) {
    $startAssistant = "0"
}
$model = $env:KAI_MODEL
if ([string]::IsNullOrWhiteSpace($model)) {
    $model = "qwen3:4b-q4_K_M"
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

$godot = Resolve-Executable -Candidates @(
    $env:KAI_GODOT,
    "C:\Users\7nujy6xc\AppData\Local\Microsoft\WinGet\Links\godot.exe",
    "C:\Program Files\Godot\Godot.exe"
) -Name "godot"

$processes = @()

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

    $companionArgs = @("--path", $companionPath)
    if (-not [string]::IsNullOrWhiteSpace($scenePath)) {
        $companionArgs += $scenePath
    }
    $companion = Start-Process -FilePath $godot -ArgumentList $companionArgs -WorkingDirectory $companionPath -PassThru
    $processes += $companion
    Start-Sleep -Seconds 2
    if ($companion.HasExited) {
        throw "Kai companion exited during startup."
    }

    Write-Host "Kai stack launched."
    Write-Host "Bridge: ws://$bridgeHost`:$bridgePort"
    if ($startAssistant -eq "1") {
        Write-Host "Assistant model: $model"
    } else {
        Write-Host "Assistant model: disabled (desktop companion mode)"
    }
    Write-Host "Companion: $companionPath"
    if (-not [string]::IsNullOrWhiteSpace($scenePath)) {
        Write-Host "Scene: $scenePath"
    }
}
catch {
    Write-Host "Kai stack launch failed: $($_.Exception.Message)" -ForegroundColor Red
    Stop-KaiProcesses -Processes $processes
    throw
}
