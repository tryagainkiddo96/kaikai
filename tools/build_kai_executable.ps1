$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$pythonExe = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
  $pythonExe = (Get-Command python).Source
} elseif (Test-Path "C:\Users\7nujy6xc\AppData\Local\Programs\Python\Python312\python.exe") {
  $pythonExe = "C:\Users\7nujy6xc\AppData\Local\Programs\Python\Python312\python.exe"
}
if ([string]::IsNullOrWhiteSpace($pythonExe)) {
  throw "Python was not found."
}

Write-Host "Installing/Updating PyInstaller..."
& $pythonExe -m pip install --upgrade pyinstaller

Write-Host "Building KaiUnified.exe ..."
& $pythonExe -m PyInstaller --noconfirm --clean KaiUnified.spec

$distExe = Join-Path $repoRoot "dist\KaiUnified.exe"
if (-not (Test-Path $distExe)) {
  throw "Build failed: $distExe was not created."
}

Write-Host ""
Write-Host "Build complete:"
Write-Host $distExe
