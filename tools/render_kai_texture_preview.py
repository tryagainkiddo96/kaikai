from __future__ import annotations

from pathlib import Path

import bpy


ROOT = Path(r"C:\Users\7nujy6xc\OneDrive\Documents\Playground\kai-ai")
BLEND_PATH = ROOT / "kai_companion" / "assets" / "kai" / "kai_texture_workspace.blend"
OUTPUT_PATH = ROOT / "tmp" / "renders" / "kai_texture_preview.png"


def main() -> None:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(OUTPUT_PATH)
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "TEXTURE"
    scene.display.shading.show_cavity = True
    scene.display.shading.show_object_outline = False
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 1280
    bpy.ops.render.render(write_still=True)
    print(f"Rendered preview to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
