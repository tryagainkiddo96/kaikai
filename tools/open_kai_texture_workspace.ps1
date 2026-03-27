$blender = "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"
$blend = "C:\Users\7nujy6xc\OneDrive\Documents\Playground\kai-ai\kai_companion\assets\kai\kai_texture_workspace.blend"

if (-not (Test-Path $blender)) {
    throw "Blender not found at $blender"
}

if (-not (Test-Path $blend)) {
    throw "Kai texture workspace not found at $blend"
}

Start-Process $blender -ArgumentList "`"$blend`""
