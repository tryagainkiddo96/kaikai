$env:KAI_USE_RIGGED_AVATAR = "1"
$env:KAI_3D_MODEL_OVERRIDE = "res://assets/kai/kai_textured_rigged.glb"
$env:KAI_SCENE = "res://scenes/kai_3d.tscn"
powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "launch_kai_stack.ps1")
