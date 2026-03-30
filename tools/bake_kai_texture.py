from __future__ import annotations

from pathlib import Path
import shutil

import bpy


ROOT = Path(r"C:\Users\7nujy6xc\OneDrive\Documents\Playground\kai-ai")
ASSET_DIR = ROOT / "kai_companion" / "assets" / "kai"
TEXTURED_SOURCE_GLB = ASSET_DIR / "kai_textured.glb"
MODEL_SOURCE_GLB = ASSET_DIR / "modelToUsed.glb"
PHOTO_TEXTURE_PATH = ASSET_DIR / "kai_photo_clean.png"
PAINT_TEXTURE_PATH = ASSET_DIR / "kai_texture_paint.png"
BAKED_ALBEDO_PATH = ASSET_DIR / "kai_baked_albedo.png"
OUTPUT_PATH = ASSET_DIR / "kai_textured_baked.glb"


def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_best_source() -> None:
    source_path = TEXTURED_SOURCE_GLB if TEXTURED_SOURCE_GLB.exists() else MODEL_SOURCE_GLB
    if not source_path.exists():
        raise FileNotFoundError(f"No Kai mesh source found at {source_path}")
    bpy.ops.import_scene.gltf(filepath=str(source_path))


def get_meshes() -> list[bpy.types.Object]:
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not meshes:
        raise RuntimeError("No mesh objects found after importing the Kai source mesh.")
    return meshes


def choose_source_texture() -> Path:
    for candidate in (PAINT_TEXTURE_PATH, PHOTO_TEXTURE_PATH):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"No texture source found. Expected {PAINT_TEXTURE_PATH.name} or {PHOTO_TEXTURE_PATH.name}."
    )


def copy_baked_albedo(source_path: Path) -> bpy.types.Image:
    shutil.copyfile(source_path, BAKED_ALBEDO_PATH)
    image = bpy.data.images.load(str(BAKED_ALBEDO_PATH), check_existing=True)
    image.name = "kai_baked_albedo"
    image.filepath_raw = str(BAKED_ALBEDO_PATH)
    image.file_format = "PNG"
    image.save()
    return image


def assign_baked_texture(meshes: list[bpy.types.Object], image: bpy.types.Image) -> None:
    material = bpy.data.materials.get("KaiBakedMaterial")
    if material is None:
        material = bpy.data.materials.new(name="KaiBakedMaterial")
        material.use_nodes = True

    nodes = material.node_tree.nodes
    links = material.node_tree.links
    for node in list(nodes):
        nodes.remove(node)

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (420, 0)

    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.location = (140, 0)
    principled.inputs["Roughness"].default_value = 0.88

    image_node = nodes.new("ShaderNodeTexImage")
    image_node.location = (-180, 0)
    image_node.image = image
    image_node.interpolation = "Smart"

    links.new(image_node.outputs["Color"], principled.inputs["Base Color"])
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])

    for mesh in meshes:
        mesh.data.materials.clear()
        mesh.data.materials.append(material)


def export_glb() -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in bpy.context.scene.objects:
        if obj.type in {"MESH", "ARMATURE"}:
            obj.select_set(True)
    bpy.ops.export_scene.gltf(
        filepath=str(OUTPUT_PATH),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_texcoords=True,
        export_normals=True,
        export_materials="EXPORT",
        export_image_format="AUTO",
    )


def main() -> None:
    reset_scene()
    import_best_source()
    meshes = get_meshes()
    baked_image = copy_baked_albedo(choose_source_texture())
    assign_baked_texture(meshes, baked_image)
    export_glb()
    print(f"Baked Kai albedo written to: {BAKED_ALBEDO_PATH}")
    print(f"Baked Kai GLB exported to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
