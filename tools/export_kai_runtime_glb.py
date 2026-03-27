from __future__ import annotations

from pathlib import Path

import bpy


ROOT = Path(r"C:\Users\7nujy6xc\OneDrive\Documents\Playground\kai-ai")
ASSET_DIR = ROOT / "kai_companion" / "assets" / "kai"
OUTPUT_PATH = ASSET_DIR / "kai_textured.glb"
TEXTURE_PATH = ASSET_DIR / "kai_texture_paint.png"


def find_model_object() -> bpy.types.Object | None:
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH":
            return obj
    return None


def ensure_texture_is_saved() -> None:
    image = bpy.data.images.get("kai_texture_paint")
    if image is None and TEXTURE_PATH.exists():
        image = bpy.data.images.load(str(TEXTURE_PATH), check_existing=True)
    if image is not None:
        image.filepath_raw = str(TEXTURE_PATH)
        image.file_format = "PNG"
        image.save()


def export_glb(model: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    model.select_set(True)
    bpy.context.view_layer.objects.active = model
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
    ensure_texture_is_saved()
    model = find_model_object()
    if model is None:
        raise RuntimeError("No mesh object found in the active Blender scene.")
    export_glb(model)
    print(f"Exported Kai runtime GLB to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
