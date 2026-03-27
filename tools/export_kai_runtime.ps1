$blender = "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"
$blend = "C:\Users\7nujy6xc\OneDrive\Documents\Playground\kai-ai\kai_companion\assets\kai\kai_texture_workspace.blend"
$script = "C:\Users\7nujy6xc\OneDrive\Documents\Playground\kai-ai\tools\export_kai_runtime_glb.py"
$project = "C:\Users\7nujy6xc\OneDrive\Documents\Playground\kai-ai\kai_companion"

if (-not (Test-Path $blender)) {
    throw "Blender not found at $blender"
}

if (-not (Test-Path $blend)) {
    throw "Kai texture workspace not found at $blend"
}

if (-not (Test-Path $script)) {
    throw "Export script not found at $script"
}

& $blender -b $blend --python $script

if ($LASTEXITCODE -ne 0) {
    throw "Blender export failed."
}

godot_console.exe --headless --path $project --import
