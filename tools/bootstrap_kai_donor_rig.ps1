$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$assetRoot = Join-Path $repoRoot "kai_companion\assets\kai"
$blenderScript = Join-Path $assetRoot "tools\bootstrap_donor_rig.py"
$outputPath = Join-Path $assetRoot "kai_donor_bootstrap_rig_source.fbx"

if (-not (Test-Path $blenderScript)) {
  throw "Blender donor-bootstrap script not found: $blenderScript"
}

$blenderCmd = Get-Command blender -ErrorAction SilentlyContinue
$blenderExe = $null
if ($null -ne $blenderCmd) {
  $blenderExe = $blenderCmd.Source
} else {
  $candidates = @(
    "$env:LOCALAPPDATA\Microsoft\WinGet\Links\blender.exe",
    "C:\Program Files\Blender Foundation\Blender\blender.exe",
    "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"
  )
  foreach ($candidate in $candidates) {
    if (Test-Path $candidate) {
      $blenderExe = $candidate
      break
    }
  }
}
if ([string]::IsNullOrWhiteSpace($blenderExe)) {
  throw "Blender executable not found. Install Blender or add blender.exe to PATH."
}

Write-Host "Bootstrapping experimental Kai donor rig source..."
Write-Host "Output: $outputPath"

if (Test-Path $outputPath) {
  Remove-Item -Force $outputPath
}
$startedAt = Get-Date

& $blenderExe -b --python $blenderScript -- --output $outputPath
if ($LASTEXITCODE -ne 0) {
  throw "Kai donor rig bootstrap failed with exit code $LASTEXITCODE."
}

if (-not (Test-Path $outputPath)) {
  throw "Kai donor rig bootstrap did not create the expected output: $outputPath"
}

$outputInfo = Get-Item $outputPath
if ($outputInfo.LastWriteTime -lt $startedAt) {
  throw "Kai donor rig bootstrap did not refresh the expected output: $outputPath"
}

Write-Host "Experimental Kai donor rig source ready: $outputPath"
