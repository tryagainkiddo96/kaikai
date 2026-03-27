param(
  [string]$SourcePath,
  [string]$OutputPath
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$assetRoot = Join-Path $repoRoot "kai_companion\assets\kai"
$blenderScript = Join-Path $assetRoot "tools\blender_kai_animation_pass.py"
$inspectScript = Join-Path $assetRoot "tools\inspect_kai_asset.py"
$sourcePath = if ([string]::IsNullOrWhiteSpace($SourcePath)) {
  Join-Path $assetRoot "kai_mixamo_rigged_source.fbx"
} else {
  $SourcePath
}
$outputPath = if ([string]::IsNullOrWhiteSpace($OutputPath)) {
  Join-Path $assetRoot "kai_textured_rigged.glb"
} else {
  $OutputPath
}

if (-not (Test-Path $sourcePath)) {
  throw "Rigged Mixamo source not found: $sourcePath`nSave the post-Mixamo download as kai_mixamo_rigged_source.fbx before preparing the rig runtime."
}

if (-not (Test-Path $blenderScript)) {
  throw "Blender animation pass script not found: $blenderScript"
}

if (-not (Test-Path $inspectScript)) {
  throw "Blender asset inspection script not found: $inspectScript"
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

Write-Host "Preparing Kai animated runtime model..."
Write-Host "Source: $sourcePath"
Write-Host "Output: $outputPath"

function Get-KaiAssetReport {
  param(
    [Parameter(Mandatory = $true)][string]$AssetPath,
    [Parameter(Mandatory = $true)][string]$ReportName
  )

  $reportPath = Join-Path $repoRoot ("tmp\rig-inspect\" + $ReportName + ".json")
  New-Item -ItemType Directory -Force -Path (Split-Path $reportPath) | Out-Null
  & $blenderExe -b --python $inspectScript -- --source $AssetPath --report $reportPath
  if ($LASTEXITCODE -ne 0) {
    throw "Asset inspection failed for $AssetPath with exit code $LASTEXITCODE."
  }
  return Get-Content -Path $reportPath -Raw | ConvertFrom-Json
}

$sourceReport = Get-KaiAssetReport -AssetPath $sourcePath -ReportName "source"
if ($sourceReport.armature_count -lt 1 -or $sourceReport.bone_count_total -lt 1) {
  throw "Rig source is not actually rigged. Expected at least one armature and one bone in $sourcePath."
}
if ($sourceReport.walk_actions.Count -lt 1) {
  throw "Rig source is missing a walk-like action. Expected a Mixamo-style walk/trot/run clip in $sourcePath."
}

& $blenderExe -b --python $blenderScript -- --source $sourcePath --output $outputPath --require-armature --require-walk-action
if ($LASTEXITCODE -ne 0) {
  throw "Blender animation pass failed with exit code $LASTEXITCODE."
}

if (-not (Test-Path $outputPath)) {
  throw "Rig runtime export failed. Output was not created."
}

$outputReport = Get-KaiAssetReport -AssetPath $outputPath -ReportName "output"
if ($outputReport.armature_count -lt 1 -or $outputReport.bone_count_total -lt 1) {
  throw "Rig runtime export did not preserve an armature. Refusing to accept $outputPath."
}
if ($outputReport.walk_actions.Count -lt 1) {
  throw "Rig runtime export is missing a walk-like action. Refusing to accept $outputPath."
}

Write-Host "Kai rig runtime ready: $outputPath"
