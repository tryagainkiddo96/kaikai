"""
Kai Texture Bake Script (Blender)
Run in Blender to bake Kai's photo onto the mesh UV layout.

Usage:
  1. Open Blender
  2. Switch to Scripting workspace
  3. Open this file
  4. Click "Run Script"

Requires:
  - kai_textured.glb in the same directory as this script
  - kai_photo_clean.png in the same directory
"""

import bpy
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(bpy.data.filepath).parent if bpy.data.filepath else Path.home() / "Desktop" / "Kai-AI-Project" / "kai_companion" / "assets" / "kai"
GLB_PATH = SCRIPT_DIR / "kai_textured.glb"
PHOTO_PATH = SCRIPT_DIR / "kai_photo_clean.png"
OUTPUT_TEXTURE = SCRIPT_DIR / "kai_baked_albedo.png"
OUTPUT_GLB = SCRIPT_DIR / "kai_textured_baked.glb"

BAKE_RESOLUTION = 2048  # Texture resolution (2048 or 4096 for quality)

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def clear_scene():
    """Remove all objects from scene."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for mesh in bpy.data.meshes:
        bpy.data.meshes.remove(mesh)
    for mat in bpy.data.materials:
        bpy.data.materials.remove(mat)
    for img in bpy.data.images:
        bpy.data.images.remove(img)


def import_glb(path):
    """Import GLB file and return the mesh object."""
    bpy.ops.import_scene.gltf(filepath=str(path))
    # Find the mesh object
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH':
            return obj
    raise RuntimeError("No mesh found in imported GLB")


def setup_bake_material(obj, photo_path):
    """
    Set up a material that maps the photo onto the mesh using existing UVs.
    This creates a simple material with the photo as the base color texture.
    """
    # Clear existing materials
    obj.data.materials.clear()
    
    # Create new material
    mat = bpy.data.materials.new(name="KaiBake")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    
    # Clear default nodes
    nodes.clear()
    
    # Create nodes
    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (400, 0)
    
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (100, 0)
    
    # Load photo as texture
    photo_img = bpy.data.images.load(str(photo_path))
    tex_node = nodes.new('ShaderNodeTexImage')
    tex_node.image = photo_img
    tex_node.location = (-300, 0)
    
    # UV Map node
    uv_node = nodes.new('ShaderNodeUVMap')
    uv_node.location = (-500, 0)
    # Use the first UV map (should be the model's existing UVs)
    if obj.data.uv_layers:
        uv_node.uv_map = obj.data.uv_layers[0].name
    
    # Connect: UV → Texture → Base Color → BSDF → Output
    links.new(uv_node.outputs['UV'], tex_node.inputs['Vector'])
    links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
    
    # Assign material
    obj.data.materials.append(mat)
    
    return mat


def bake_texture(obj, resolution):
    """
    Bake the photo projection onto a new UV-mapped texture.
    This 'commits' the photo to the mesh's UV layout.
    """
    # Create bake target image
    bake_img = bpy.data.images.new(
        name="KaiBakedAlbedo",
        width=resolution,
        height=resolution,
        alpha=True,
        float_buffer=False
    )
    
    mat = obj.data.materials[0]
    nodes = mat.node_tree.nodes
    
    # Create a new texture node for the bake target
    bake_node = nodes.new('ShaderNodeTexImage')
    bake_node.image = bake_img
    bake_node.location = (-300, -300)
    
    # Select the bake target node (this is where Blender writes)
    nodes.active = bake_node
    bake_node.select = True
    
    # Deselect all other texture nodes
    for node in nodes:
        if node != bake_node and node.type == 'TEX_IMAGE':
            node.select = False
    
    # Make sure the object is selected and active
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    
    # Set bake settings
    bpy.context.scene.cycles.device = 'CPU'  # Use CPU for compatibility
    bpy.context.scene.render.bake.use_selected_to_active = False
    bpy.context.scene.render.bake.use_clear = True
    bpy.context.scene.render.bake.margin = 16  # Texture margin to avoid seams
    
    # Select the correct render engine for baking
    original_engine = bpy.context.scene.render.engine
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.samples = 1  # Bake is exact, no sampling needed
    
    # Switch to texture paint mode for bake target
    bpy.ops.object.mode_set(mode='TEXTURE_PAINT')
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Bake!
    print(f"Baking at {resolution}x{resolution}...")
    bpy.ops.object.bake(type='DIFFUSE')
    
    # Restore engine
    bpy.context.scene.render.engine = original_engine
    
    # Clean up: remove the bake target node, keep only the baked texture
    # Update the main texture node to use the baked image
    main_tex = None
    for node in nodes:
        if node.type == 'TEX_IMAGE' and node != bake_node:
            main_tex = node
            break
    
    if main_tex:
        main_tex.image = bake_img
    
    # Remove the temporary bake node
    nodes.remove(bake_node)
    
    print("Bake complete!")
    return bake_img


def save_baked_texture(image, output_path):
    """Save the baked texture to disk."""
    image.filepath_raw = str(output_path)
    image.file_format = 'PNG'
    image.save()
    print(f"Saved texture: {output_path}")


def export_glb(obj, output_path):
    """Export the baked model as GLB."""
    # Select only the mesh
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    
    # Export GLB with textures embedded
    bpy.ops.export_scene.gltf(
        filepath=str(output_path),
        export_format='GLB',
        export_selected=True,
        export_materials='EXPORT',
        export_texcoords=True,
        export_normals=True,
    )
    print(f"Exported: {output_path}")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    print("=" * 50)
    print("Kai Texture Bake Pipeline")
    print("=" * 50)
    
    # Verify files exist
    if not GLB_PATH.exists():
        print(f"ERROR: GLB not found: {GLB_PATH}")
        print("Place kai_textured.glb in:", SCRIPT_DIR)
        return
    
    if not PHOTO_PATH.exists():
        print(f"ERROR: Photo not found: {PHOTO_PATH}")
        print("Place kai_photo_clean.png in:", SCRIPT_DIR)
        return
    
    print(f"GLB: {GLB_PATH}")
    print(f"Photo: {PHOTO_PATH}")
    print(f"Output texture: {OUTPUT_TEXTURE}")
    print(f"Output GLB: {OUTPUT_GLB}")
    print()
    
    # Step 1: Clear scene
    print("Step 1: Clearing scene...")
    clear_scene()
    
    # Step 2: Import model
    print("Step 2: Importing model...")
    obj = import_glb(GLB_PATH)
    print(f"  Mesh: {obj.name}, {len(obj.data.vertices)} vertices")
    print(f"  UV layers: {[uv.name for uv in obj.data.uv_layers]}")
    
    # Step 3: Set up bake material
    print("Step 3: Setting up bake material (photo → UV)...")
    mat = setup_bake_material(obj, PHOTO_PATH)
    
    # Step 4: Preview (optional — comment out for faster batch runs)
    print("Step 4: Setting viewport to Material Preview...")
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.type = 'MATERIAL'
    
    # Step 5: Bake
    print(f"Step 5: Baking texture ({BAKE_RESOLUTION}x{BAKE_RESOLUTION})...")
    bake_img = bake_texture(obj, BAKE_RESOLUTION)
    
    # Step 6: Save baked texture
    print("Step 6: Saving baked texture...")
    save_baked_texture(bake_img, OUTPUT_TEXTURE)
    
    # Step 7: Export baked GLB
    print("Step 7: Exporting baked GLB...")
    export_glb(obj, OUTPUT_GLB)
    
    print()
    print("=" * 50)
    print("DONE!")
    print(f"Baked texture: {OUTPUT_TEXTURE}")
    print(f"Baked model: {OUTPUT_GLB}")
    print("=" * 50)


if __name__ == "__main__":
    main()
