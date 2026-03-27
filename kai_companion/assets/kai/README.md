Temporary avatar spec for the current Kai companion placeholder:

- realistic male Shiba Inu
- black and tan coat
- white or cream chest, muzzle, and paw markings
- clean silhouette suitable for desktop companion presentation

The active companion runtime loads only the canonical photo-replica path.

Current asset roles:

- `kai_textured.glb`: current canonical photo-replica appearance asset for Kai
- `kai_textured_rigged.glb`: provisional rigged photo-replica candidate derived from the canonical photo replica
- `kai-lite.glb`: low-poly motion reference donor only, not loaded as Kai's runtime identity
- `modelToUsed.glb`, `kai_runtime_candidate.glb`, `kai_animated.glb`, `kai.glb`: transitional legacy lineage, not canonical runtime assets

Runtime rule:

- Do not silently substitute the low-poly donor as if it were the real Kai model.
- Do not auto-discover transitional assets in runtime.
- Keep the photo-replica asset as the only runtime identity until `kai_textured_rigged.glb` is validated.

Current promotion note:

- `kai_textured_rigged.glb` now has a local weight-baked rig candidate with `trot` and `KAI_Idle_Breath`.
- It boots cleanly in Godot when loaded as a `res://` override asset.
- It is still a promotion candidate, not the default runtime identity, until likeness and motion quality are reviewed together.

## Blender animation quality pass (headless)

This folder now includes a defensive Blender script that adds subtle idle motion and exports the next rig target GLB:

- Script: `tools/blender_kai_animation_pass.py`
- Default source detection order:
  - `kai_mixamo_rigged_source.fbx`
  - `kai_textured.glb`
  - `kai_texture_workspace.blend`
- Default output: `kai_textured_rigged.glb`

### Run from this directory

```powershell
cd C:\Users\7nujy6xc\OneDrive\Documents\Playground\kai-ai\kai_companion\assets\kai
blender -b --python tools\blender_kai_animation_pass.py --
```

### Optional explicit source/output

```powershell
cd C:\Users\7nujy6xc\OneDrive\Documents\Playground\kai-ai\kai_companion\assets\kai
blender -b --python tools\blender_kai_animation_pass.py -- --source kai_mixamo_rigged_source.fbx --output kai_textured_rigged.glb --require-armature --require-walk-action
```

### What the script does

- Tries to load the validated rigged Mixamo source first, then the canonical photo-replica source.
- Adds a gentle breathing loop on a likely chest/spine/root bone (or mesh object fallback).
- Generates companion-style clips when object-level animation is used:
  - `KAI_Idle`
  - `KAI_Alert`
  - `KAI_Wag`
  - `KAI_Rest`
  - `KAI_Walk`
- Adds blink keys when blink-like shape keys are detected.
- Applies Bezier/auto-clamped keyframe smoothing.
- Builds NLA strips for created actions so GLB export keeps multiple clips.
- Logs each step and safely skips unavailable rig/shape-key features without hard crashing.

## Mixamo Fast Path (Auto-Rig + Animation Library)

Use this when you want fast, high-quality movement clips with minimal manual rigging.

Upload staging file in this folder:
- `kai_mixamo_ready.fbx`

Expected post-Mixamo download for rig prep:
- `kai_mixamo_rigged_source.fbx`

You can regenerate it anytime:

```powershell
cd C:\Users\7nujy6xc\OneDrive\Documents\Playground\kai-ai\kai_companion\assets\kai
blender -b --python tools\export_mixamo_fbx.py -- --source kai_textured.glb --output kai_mixamo_ready.fbx
```

Suggested pipeline:
1. Upload `kai_mixamo_ready.fbx` to Mixamo.
2. Auto-rig with marker placement.
3. Download the rigged result with the needed walk-like animation and save it as `kai_mixamo_rigged_source.fbx`.
4. Run `tools/prepare_kai_rig_runtime.ps1` or the Blender animation pass with `--require-armature --require-walk-action`.
5. Export `kai_textured_rigged.glb` only after the rigged source passes inspection.

Material note:
- `kai_texture_paint.png` is only an authoring texture. Runtime color changes do not apply until the mesh is re-exported into `kai_textured.glb` or `kai_textured_rigged.glb`.

## Experimental Local Bootstrap

Use this only for evaluation when no validated external rig source exists yet.

- Script: `tools/bootstrap_donor_rig.py`
- Wrapper: `..\..\..\tools\bootstrap_kai_donor_rig.ps1`
- Output: `kai_donor_bootstrap_rig_source.fbx`

What it does:
- weight-bakes the canonical Kai mesh against the low-poly donor armature
- preserves the donor `trot` action when possible
- produces an experimental rig source for review, not a validated final rig
