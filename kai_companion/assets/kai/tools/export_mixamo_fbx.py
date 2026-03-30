#!/usr/bin/env python3
"""
Export the Mixamo upload-staging FBX from Kai assets.

Usage:
  blender -b --python tools/export_mixamo_fbx.py --
  blender -b --python tools/export_mixamo_fbx.py -- --source kai_textured.glb --output kai_mixamo_ready.fbx
"""

import argparse
import os
import sys

import bpy


def log(msg):
    print(f"[MIXAMO_EXPORT] {msg}")


def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="kai_textured.glb")
    parser.add_argument("--output", default="kai_mixamo_ready.fbx")
    parser.add_argument("--embed-textures", action="store_true")
    parser.add_argument("--decimate-ratio", type=float, default=1.0)
    return parser.parse_args(argv)


def base_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False, confirm=False)


def ensure_abs(path, root):
    if os.path.isabs(path):
        return path
    return os.path.join(root, path)


def main():
    args = parse_args()
    root = base_dir()
    source = ensure_abs(args.source, root)
    output = ensure_abs(args.output, root)

    if not os.path.exists(source):
        log(f"Source not found: {source}")
        return 1

    clear_scene()
    log(f"Importing: {source}")
    bpy.ops.import_scene.gltf(filepath=source)

    if args.decimate_ratio < 0.999:
        ratio = max(0.05, min(1.0, args.decimate_ratio))
        log(f"Applying decimate ratio: {ratio:.2f}")
        for obj in bpy.context.scene.objects:
            if obj.type != "MESH":
                continue
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            mod = obj.modifiers.new(name="MixamoDecimate", type="DECIMATE")
            mod.ratio = ratio
            bpy.ops.object.modifier_apply(modifier=mod.name)

    # Keep only visible geometry/armature exports as expected by Mixamo.
    for obj in bpy.context.scene.objects:
        obj.select_set(obj.type in {"MESH", "ARMATURE"})

    os.makedirs(os.path.dirname(output), exist_ok=True)
    log(f"Exporting FBX: {output}")
    bpy.ops.export_scene.fbx(
        filepath=output,
        use_selection=True,
        object_types={"MESH", "ARMATURE"},
        apply_unit_scale=True,
        bake_space_transform=False,
        add_leaf_bones=False,
        path_mode="COPY" if args.embed_textures else "AUTO",
        embed_textures=args.embed_textures,
        axis_forward="-Z",
        axis_up="Y",
    )
    log("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
