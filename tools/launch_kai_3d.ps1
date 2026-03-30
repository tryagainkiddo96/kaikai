$env:KAI_SCENE = "res://scenes/kai_3d.tscn"
powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "launch_kai_stack.ps1")
