param(
    [int]$Runs = 10,
    [int]$StartupWaitSeconds = 8,
    [switch]$Rebuild
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$exePath = Join-Path $repoRoot "dist\KaiUnified.exe"
$probeScriptPath = Join-Path $PSScriptRoot "probe_kai_bridge.py"
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$artifactsRoot = Join-Path $repoRoot "tmp\verification\kai_unified\$timestamp"

New-Item -ItemType Directory -Path $artifactsRoot -Force | Out-Null

function Resolve-Python {
    $resolved = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $resolved) {
        return $resolved.Source
    }
    $fallback = "C:\Users\7nujy6xc\AppData\Local\Programs\Python\Python312\python.exe"
    if (Test-Path $fallback) {
        return $fallback
    }
    throw "Python was not found for bridge verification."
}

$pythonExe = Resolve-Python

function Get-ProcessSnapshot {
    return Get-CimInstance Win32_Process |
        Where-Object { $_.Name -in @("KaiUnified.exe", "godot.exe", "ollama.exe") } |
        Select-Object Name, ProcessId, ParentProcessId, CommandLine
}

function Get-BridgeOwners {
    $connections = Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue
    if ($null -eq $connections) {
        return @()
    }
    return @($connections | Select-Object -ExpandProperty OwningProcess -Unique)
}

function Get-DescendantProcessIds {
    param([int[]]$RootIds)

    $all = Get-CimInstance Win32_Process | Select-Object ProcessId, ParentProcessId
    $pending = [System.Collections.Generic.Queue[int]]::new()
    $seen = [System.Collections.Generic.HashSet[int]]::new()

    foreach ($rootId in $RootIds) {
        if ($seen.Add($rootId)) {
            $pending.Enqueue($rootId)
        }
    }

    while ($pending.Count -gt 0) {
        $current = $pending.Dequeue()
        foreach ($process in $all) {
            if ($process.ParentProcessId -eq $current -and $seen.Add($process.ProcessId)) {
                $pending.Enqueue($process.ProcessId)
            }
        }
    }

    return @($seen)
}

function Stop-ProcessTree {
    param([int[]]$RootIds)

    $allIds = Get-DescendantProcessIds -RootIds $RootIds | Sort-Object -Descending
    foreach ($processId in $allIds) {
        try {
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        } catch {
            # Best effort cleanup only.
        }
    }
}

function Test-BridgeHandshake {
    param([string]$Url = "ws://127.0.0.1:8765")

    $previousErrorAction = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = & $pythonExe $probeScriptPath --url $Url --timeout 3 2>$null
        $exitCode = $LASTEXITCODE
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $previousErrorAction
    }
    return ($exitCode -eq 0 -and (($output -join "`n").Trim() -eq "ok"))
}

if ($Rebuild) {
    $buildLog = Join-Path $artifactsRoot "build.log"
    & powershell.exe -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "build_kai_executable.ps1") *>&1 |
        Tee-Object -FilePath $buildLog | Out-Null
}

if (-not (Test-Path $exePath)) {
    throw "Could not find KaiUnified.exe at $exePath"
}

$results = @()

for ($run = 1; $run -le $Runs; $run++) {
    $runDir = Join-Path $artifactsRoot ("run-{0:D2}" -f $run)
    $logDir = Join-Path $runDir "logs"
    $dataDir = Join-Path $runDir "data"
    New-Item -ItemType Directory -Path $runDir, $logDir, $dataDir -Force | Out-Null

    $env:KAI_WORKSPACE = $repoRoot
    $env:KAI_DATA_ROOT = $dataDir
    $env:KAI_LOG_ROOT = $logDir

    $snapshotBefore = Join-Path $runDir "processes-before.json"
    Get-ProcessSnapshot | ConvertTo-Json -Depth 4 | Set-Content -Path $snapshotBefore -Encoding UTF8

    $staleBridgeOwners = @(Get-BridgeOwners)
    if ($staleBridgeOwners.Count -gt 0) {
        Stop-ProcessTree -RootIds $staleBridgeOwners
        Start-Sleep -Seconds 2
    }

    $runStart = Get-Date
    $launch = Start-Process -FilePath $exePath -PassThru
    Start-Sleep -Seconds $StartupWaitSeconds

    $kaiProcesses = Get-Process -Name KaiUnified -ErrorAction SilentlyContinue |
        Where-Object { $_.StartTime -ge $runStart.AddSeconds(-2) }
    $processIds = @($kaiProcesses | Select-Object -ExpandProperty Id)
    $runOwnedProcessIds = @(Get-DescendantProcessIds -RootIds (@($launch.Id) + $processIds))
    $bridgeOk = Test-BridgeHandshake
    $launchAlive = $kaiProcesses.Count -gt 0
    $bridgeOwners = @(Get-BridgeOwners)
    $bridgeOwnedByRun = @($bridgeOwners | Where-Object { $runOwnedProcessIds -contains $_ }).Count -gt 0
    $logPath = Join-Path $logDir "events.jsonl"
    $launchLogExists = Test-Path $logPath
    $launchErrorFound = $false
    if ($launchLogExists) {
        $launchErrorFound = Select-String -Path $logPath -Pattern '"event_type": "launch_error"|"event_type": "bridge_startup_error"' -Quiet
    }

    $result = [ordered]@{
        run = $run
        launch_pid = $launch.Id
        started_at = $runStart.ToString("o")
        kai_process_count = @($kaiProcesses).Count
        process_ids = $processIds
        launch_alive = $launchAlive
        bridge_ok = $bridgeOk
        bridge_owner_ids = $bridgeOwners
        bridge_owned_by_run = $bridgeOwnedByRun
        launch_log_exists = $launchLogExists
        launch_error_found = $launchErrorFound
        pass = ($launchAlive -and $bridgeOk -and $bridgeOwnedByRun -and -not $launchErrorFound)
    }

    $resultPath = Join-Path $runDir "result.json"
    $result | ConvertTo-Json -Depth 4 | Set-Content -Path $resultPath -Encoding UTF8
    $results += [pscustomobject]$result

    Stop-ProcessTree -RootIds @($launch.Id) + @($kaiProcesses | Select-Object -ExpandProperty Id)
    Start-Sleep -Seconds 2

    $snapshotAfter = Join-Path $runDir "processes-after.json"
    Get-ProcessSnapshot | ConvertTo-Json -Depth 4 | Set-Content -Path $snapshotAfter -Encoding UTF8
}

$summaryPath = Join-Path $artifactsRoot "summary.json"
$results | ConvertTo-Json -Depth 4 | Set-Content -Path $summaryPath -Encoding UTF8

$failedRuns = @($results | Where-Object { -not $_.pass })
Write-Host "Artifacts: $artifactsRoot"
Write-Host "Passed runs: $($results.Count - $failedRuns.Count)/$($results.Count)"

if ($failedRuns.Count -gt 0) {
    throw "KaiUnified verification failed on run(s): $(@($failedRuns.run) -join ', ')"
}
