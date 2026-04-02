# Kai 3D Model Recovery Checklist

## Problem
Godot can't load `kai_textured_rigged.glb` — "no loader found" error.
Root cause: broken Godot install, missing glTF importer, or corrupted import cache.

## Step 1: Verify Godot Install

```bash
# Check current Godot version
godot --version

# If missing or wrong version, install Godot 4.x stable
# Linux (official release):
wget https://github.com/godotengine/godot/releases/download/4.4.1-stable/Godot_v4.4.1-stable_linux.x86_64.zip
unzip Godot_v4.4.1-stable_linux.x86_64.zip
chmod +x Godot_v4.4.1-stable_linux.x86_64
sudo mv Godot_v4.4.1-stable_linux.x86_64 /usr/local/bin/godot

# Verify glTF support is present
godot --headless --version
# Must be 4.x — 3.x has different import pipeline
```

## Step 2: Clear Import Cache

```bash
cd kaikai/kai_companion

# Delete import cache — forces full reimport
rm -rf .godot/imported/
rm -f .godot/uid_cache.bin
rm -f .godot/global_script_class_cache.cfg

# Verify the model file exists and isn't corrupt
ls -lh assets/kai/kai_textured_rigged.glb
file assets/kai/kai_textured_rigged.glb
# Should say: "GLB binary glTF"
```

## Step 3: Reimport in Godot Editor

```bash
# Open in GUI editor (NOT headless) — headless can fail on GPU imports
cd kaikai/kai_companion
godot --editor .

# Wait for import to finish (progress bar at bottom)
# This may take 1-5 minutes for the 519K vertex model
```

## Step 4: Test the Model

In the Godot editor:
1. Open `res://scenes/kai_3d.tscn`
2. Check the 3D viewport — Kai model should appear
3. If model node shows red/error, check Output panel for errors
4. Run the scene: F6 → select `kai_3d.tscn`

Or from CLI:
```bash
cd kaikai/kai_companion
godot --path . res://scenes/kai_3d.tscn
```

## Step 5: If Still Broken

**"No loader found" still appears:**
- Godot build is missing glTF module
- Fix: reinstall from official release (Step 1)
- Portable/broken builds sometimes strip importers

**Model loads but textures are broken (TV static):**
- Textures need baking in Blender first
- Follow `tools/3D_PIPELINE_GUIDE.md` Steps 1-2
- This is expected — the rigged GLB has broken baked-in textures

**Model loads but no animations:**
- Export didn't include animations
- Re-export from Blender with "Export Animation" checked
- See Step 5 of pipeline guide

**Model loads but no tail:**
- Expected — Mixamo rig has no tail bones
- Run `tools/add_tail_bones.py` in Blender (Step 3 of pipeline guide)

## Nuclear Option (Different Machine)

If this machine's Godot install is fundamentally broken:
1. Clone repo to a machine with clean Godot 4.4+ install
2. Clear `.godot/` entirely: `rm -rf kaikai/kai_companion/.godot`
3. Open in editor, let it reimport
4. If it works there, the issue is the original machine's Godot build

## Launch Commands

```bash
# Widget (web UI)
cd kaikai && python3 kai_agent/widget_server.py

# Desktop panel
cd kaikai && python3 kai_agent/desktop_panel_unified.py

# 3D companion (needs working Godot + textures)
cd kaikai && tools/launch_kai_stack.ps1  # Windows
cd kaikai && KAI_USE_RIGGED_AVATAR=1 godot --path kai_companion  # Linux
```
