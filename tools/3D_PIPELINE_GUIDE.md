# Kai 3D Model Pipeline — Step by Step

**Goal:** Fix the broken textures, add tail bones, add animations, export working GLB for Godot.

**Status:** Rig working (Mixamo confirmed), textures broken (TV static noise).

**All scripts are in `tools/` — run each one in order inside Blender.**

---

## Prerequisites

- Blender 3.6+ or 4.x installed
- Files in `kai_companion/assets/kai/`:
  - `kai_textured.glb` — canonical mesh (has UVs)
  - `kai_textured_rigged.glb` — Mixamo rigged version
  - `kai_photo_clean.png` — Kai's photo (for texture baking)
  - `kai_mixamo_ready.fbx` — the FBX you uploaded to Mixamo

---

## Step 1: Bake the Texture

**This is the critical fix.** The rigged GLB has broken textures baked in.

```
1. Open Blender
2. File → Import → glTF 2.0 → select kai_textured.glb
   (NOT the rigged one — use the canonical mesh for baking)
3. Switch to "Scripting" workspace (top tab bar)
4. Click "Open" in the text editor
5. Navigate to: tools/bake_kai_texture.py
6. Click "Run Script" (or Alt+P)
7. Wait for it to finish (may take 1-5 minutes)
```

**What it does:**
- Loads `kai_photo_clean.png` as a texture
- Maps it onto the mesh using existing UVs
- Bakes at 2048x2048 resolution
- Saves `kai_baked_albedo.png` and `kai_textured_baked.glb`

**Expected output in Blender console:**
```
Step 1: Clearing scene...
Step 2: Importing model...
  Mesh: Mesh_0, 519942 vertices
Step 3: Setting up bake material...
Step 4: Baking texture (2048x2048)...
Bake complete!
Step 6: Saving baked texture...
Saved texture: /path/to/kai_baked_albedo.png
Step 7: Exporting baked GLB...
Exported: /path/to/kai_textured_baked.glb
DONE!
```

**If bake fails:**
- Make sure Cycles render engine is available (check top bar)
- If GPU error, the script forces CPU baking
- If UV error, the canonical mesh might not have UVs — check in UV Editor

---

## Step 2: Import Rigged Model + Apply Baked Texture

```
1. Close Blender (or File → New → General)
2. File → Import → glTF 2.0 → select kai_textured_rigged.glb
3. You should see the rigged mesh with armature
4. Switch to "Scripting" workspace
5. Open: tools/prepare_kai_rig_runtime.py
6. Click "Run Script"
```

**What it does:**
- Validates rig bones
- Cleans bone names (removes "mixamorig:" prefix for Godot)
- Applies `kai_baked_albedo.png` as the texture
- Lists available animations
- Exports `kai_textured_rigged.glb` for Godot

**Expected output:**
```
Step 2: Importing Mixamo FBX...
  Armature: Armature, 65 bones
  Mesh: Mesh_0, 519942 vertices
Step 3: Validating rig...
Rig validated: 65 bones, all required bones present
Step 4: Cleaning bone names...
Bone names cleaned
Step 5: Checking animations...
Animation: mixamo.com (150 frames)
Step 6: Applying texture...
Texture applied: kai_baked_albedo.png
Step 7: Exporting for Godot...
Exported for Godot: /path/to/kai_textured_rigged.glb
DONE!
```

---

## Step 3: Add Tail Bones

Mixamo rigs don't have tail bones. This adds a 3-segment tail.

```
1. Keep the rigged model open in Blender
2. Open: tools/add_tail_bones.py
3. Click "Run Script"
```

**Expected output:**
```
Adding Tail Bones to Kai Rig
========================================
Attaching tail to: Hips
Added 3 tail bones

Tail bone chain:
  Tail1: head=<coords>, tail=<coords>
  Tail2: head=<coords>, tail=<coords>
  Tail3: head=<coords>, tail=<coords>
Pose bone limits set for tail
DONE!
```

---

## Step 4: Add Animations

```
1. Keep the rigged model open (with tail bones now)
2. Open: tools/create_kai_animations.py
3. Click "Run Script"
```

**Expected output:**
```
Kai Animation Creator
========================================
Created Idle animation (60 frames)
Created Walk animation (120 frames)
Created Bark animation (30 frames)
Created TailWag animation (40 frames)
Created LieDown animation (45 frames)

Created animations:
  - Idle (60 frames)
  - Walk (120 frames)
  - Bark (30 frames)
  - TailWag (40 frames)
  - LieDown (45 frames)
DONE!
```

---

## Step 5: Final Export for Godot

```
1. Select the armature in the viewport (right-click it)
2. File → Export → glTF 2.0 (.glb/.gltf)
3. Save as: kai_textured_rigged.glb
   (overwrite the old one in kai_companion/assets/kai/)
4. In export settings, CHECK these boxes:
   ☑️ Format: GLB
   ☑️ Selected Objects (armature + mesh should be selected)
   ☑️ Mesh → Apply Modifiers
   ☑️ Animation → Export Animation
   ☑️ Animation → Group by NLA Track
   ☑️ Armature → Export Skinning
   ☑️ Materials → Export Materials
5. Click "Export glTF 2.0"
```

---

## Step 6: Test in Godot

```
1. Open kai_companion/project.godot in Godot
2. Run with environment variable:
   
   Linux/Mac:
     KAI_USE_RIGGED_AVATAR=1 godot --path /path/to/kai_companion
   
   Windows PowerShell:
     $env:KAI_USE_RIGGED_AVATAR="1"; godot --path C:\path\to\kai_companion

3. You should see:
   - Kai with proper Shiba coat texture (not static noise)
   - Idle breathing animation
   - Walk animation when Kai patrols
   - Bark animation
   - Tail wagging (if tail bones were added)
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Bake produces black texture | Check that the photo loaded — look at the Image Editor in Blender |
| Bake is very slow | Normal for 519K vertices. Wait 5-10 min. |
| Rig has no animations | Mixamo download must include animations. Re-download from Mixamo with an animation selected. |
| Tail bones don't appear | Make sure you're in Object mode before running the script |
| Godot shows hologram | The old broken-texture GLB is still there. Make sure Step 5 overwrote it. |
| Godot shows no animation | Check export settings — "Export Animation" must be checked |
| Bones named with "mixamorig:" prefix | Run prepare_kai_rig_runtime.py Step 4 again |

---

## File Checklist After Completion

```
kai_companion/assets/kai/
├── kai_textured.glb              ✅ Canonical mesh (unchanged)
├── kai_textured_rigged.glb       ✅ NEW — baked texture + rig + animations
├── kai_baked_albedo.png          ✅ NEW — baked texture file
├── kai_photo_clean.png           ✅ Original photo (unchanged)
├── kai_mixamo_ready.fbx          ✅ Original FBX (unchanged)
└── ... (other files unchanged)
```

The ONLY file Godot cares about is `kai_textured_rigged.glb`. Everything else is reference/tooling.
