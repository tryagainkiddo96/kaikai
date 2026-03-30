"""
Kai Rig Prep Script (Blender)
Import Mixamo-rigged FBX, validate, fix weights, export GLB for Godot.

Usage:
  1. Upload kai_mixamo_ready.fbx to Mixamo.com
  2. Place markers, download rigged FBX
  3. Save as kai_mixamo_rigged_source.fbx in the kai assets folder
  4. Open Blender, run this script

Requires:
  - kai_mixamo_rigged_source.fbx (from Mixamo)
  - kai_textured.glb (canonical mesh for UV/texture reference)
  - kai_baked_albedo.png (from bake_kai_texture.py, if available)
"""

import bpy
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(bpy.data.filepath).parent if bpy.data.filepath else Path.home() / "Desktop" / "Kai-AI-Project" / "kai_companion" / "assets" / "kai"
MIXAMO_SOURCE = SCRIPT_DIR / "kai_mixamo_rigged_source.fbx"
CANONICAL_GLB = SCRIPT_DIR / "kai_textured.glb"
BAKED_TEXTURE = SCRIPT_DIR / "kai_baked_albedo.png"
OUTPUT_GLB = SCRIPT_DIR / "kai_textured_rigged.glb"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for obj in bpy.data.objects:
        bpy.data.objects.remove(obj)
    for mesh in bpy.data.meshes:
        bpy.data.meshes.remove(mesh)
    for arm in bpy.data.armatures:
        bpy.data.armatures.remove(arm)


def import_mixamo_fbx(path):
    """Import Mixamo FBX and return (armature, mesh) objects."""
    bpy.ops.import_scene.fbx(filepath=str(path))
    
    armature = None
    mesh = None
    
    for obj in bpy.context.scene.objects:
        if obj.type == 'ARMATURE':
            armature = obj
        elif obj.type == 'MESH':
            mesh = obj
    
    if not armature:
        raise RuntimeError("No armature found in Mixamo FBX")
    if not mesh:
        raise RuntimeError("No mesh found in Mixamo FBX")
    
    # Parent mesh to armature if not already
    if mesh.parent != armature:
        bpy.ops.object.select_all(action='DESELECT')
        mesh.select_set(True)
        armature.select_set(True)
        bpy.context.view_layer.objects.active = armature
        bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    
    return armature, mesh


def validate_rig(armature):
    """Check the rig has the essential bones."""
    bone_names = [b.name for b in armature.data.bones]
    
    required_bones = [
        'mixamorig:Hips',
        'mixamorig:Spine',
        'mixamorig:Head',
        'mixamorig:LeftUpLeg',
        'mixamorig:RightUpLeg',
        'mixamorig:LeftArm',
        'mixamorig:RightArm',
    ]
    
    missing = [b for b in required_bones if b not in bone_names]
    
    if missing:
        print(f"WARNING: Missing bones: {missing}")
        print(f"Available bones: {bone_names}")
        # Try to find alternative bone names (non-Mixamo rigs)
        print("If using a non-Mixamo rig, adjust the bone names in this script.")
    else:
        print(f"Rig validated: {len(bone_names)} bones, all required bones present")
    
    return len(missing) == 0


def fix_bone_names(armature):
    """Clean up Mixamo bone names (remove 'mixamorig:' prefix for Godot)."""
    for bone in armature.data.bones:
        if bone.name.startswith('mixamorig:'):
            bone.name = bone.name.replace('mixamorig:', '')
    print("Bone names cleaned (removed 'mixamorig:' prefix)")


def check_animations(armature):
    """List available animations on the armature."""
    if not armature.animation_data or not armature.animation_data.action:
        print("WARNING: No animation action found on armature")
        print("Add animations in Mixamo before downloading, or add them manually in Blender")
        return []
    
    actions = [armature.animation_data.action.name]
    print(f"Animation: {actions[0]} ({armature.animation_data.action.frame_range[1]} frames)")
    return actions


def apply_texture(mesh, texture_path):
    """Apply baked texture to the mesh material."""
    if not texture_path.exists():
        print(f"WARNING: Baked texture not found: {texture_path}")
        print("Run bake_kai_texture.py first, or apply texture manually")
        return
    
    # Clear materials
    mesh.data.materials.clear()
    
    # Create material
    mat = bpy.data.materials.new(name="KaiMaterial")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    
    # Standard PBR setup
    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (400, 0)
    
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (100, 0)
    bsdf.inputs['Roughness'].default_value = 0.7  # Fur-like roughness
    
    # Load texture
    tex = nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(str(texture_path))
    tex.location = (-300, 0)
    
    # UV Map
    uv = nodes.new('ShaderNodeUVMap')
    uv.location = (-500, 0)
    
    # Connect
    links.new(uv.outputs['UV'], tex.inputs['Vector'])
    links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
    
    mesh.data.materials.append(mat)
    print(f"Texture applied: {texture_path.name}")


def export_for_godot(armature, output_path):
    """Export rigged mesh as GLB for Godot."""
    bpy.ops.object.select_all(action='DESELECT')
    armature.select_set(True)
    for child in armature.children:
        child.select_set(True)
    bpy.context.view_layer.objects.active = armature
    
    bpy.ops.export_scene.gltf(
        filepath=str(output_path),
        export_format='GLB',
        export_selected=True,
        export_animations=True,
        export_skins=True,
        export_morph=True,
        export_materials='EXPORT',
    )
    print(f"Exported for Godot: {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 50)
    print("Kai Rig Prep Pipeline")
    print("=" * 50)
    
    if not MIXAMO_SOURCE.exists():
        print(f"ERROR: Mixamo source not found: {MIXAMO_SOURCE}")
        print("Download the rigged FBX from Mixamo and save it as:")
        print(f"  {MIXAMO_SOURCE}")
        return
    
    print(f"Mixamo source: {MIXAMO_SOURCE}")
    print(f"Output: {OUTPUT_GLB}")
    print()
    
    # Step 1: Clear
    print("Step 1: Clearing scene...")
    clear_scene()
    
    # Step 2: Import
    print("Step 2: Importing Mixamo FBX...")
    armature, mesh = import_mixamo_fbx(MIXAMO_SOURCE)
    print(f"  Armature: {armature.name}, {len(armature.data.bones)} bones")
    print(f"  Mesh: {mesh.name}, {len(mesh.data.vertices)} vertices")
    
    # Step 3: Validate
    print("Step 3: Validating rig...")
    validate_rig(armature)
    
    # Step 4: Clean bone names
    print("Step 4: Cleaning bone names...")
    fix_bone_names(armature)
    
    # Step 5: Check animations
    print("Step 5: Checking animations...")
    check_animations(armature)
    
    # Step 6: Apply texture
    print("Step 6: Applying texture...")
    apply_texture(mesh, BAKED_TEXTURE)
    
    # Step 7: Export
    print("Step 7: Exporting for Godot...")
    export_for_godot(armature, OUTPUT_GLB)
    
    print()
    print("=" * 50)
    print("DONE!")
    print(f"Rigged model: {OUTPUT_GLB}")
    print("Import this in Godot as Kai's runtime identity.")
    print("=" * 50)


if __name__ == "__main__":
    main()
