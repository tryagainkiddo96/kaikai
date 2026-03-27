#!/usr/bin/env python3
"""
Inspect a Kai FBX/GLB asset in Blender and emit a JSON report.

Usage:
  blender -b --python tools/inspect_kai_asset.py -- --source path/to/asset.glb
  blender -b --python tools/inspect_kai_asset.py -- --source path/to/asset.fbx --report report.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import bpy


WALK_KEYWORDS = ("walk", "trot", "run", "gallop", "locomotion", "cycle", "move")
HELPER_PREFIXES = ("Icosphere",)


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    parser = argparse.ArgumentParser(description="Inspect a Kai asset")
    parser.add_argument("--source", required=True)
    parser.add_argument("--report")
    return parser.parse_args(argv)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False, confirm=False)


def import_source(source: str) -> None:
    ext = os.path.splitext(source)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=source)
        return
    if ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=source)
        return
    raise RuntimeError(f"Unsupported asset type: {source}")


def is_helper_object(obj: bpy.types.Object) -> bool:
    object_name = getattr(obj, "name", "")
    data_name = getattr(getattr(obj, "data", None), "name", "")
    return any(
        object_name.startswith(prefix) or data_name.startswith(prefix)
        for prefix in HELPER_PREFIXES
    )


def build_report(source: str) -> dict:
    objects = [obj for obj in bpy.context.scene.objects if not is_helper_object(obj)]
    armatures = [obj for obj in objects if obj.type == "ARMATURE"]
    meshes = [obj for obj in objects if obj.type == "MESH"]
    helper_objects = [obj for obj in bpy.context.scene.objects if is_helper_object(obj)]
    actions = list(bpy.data.actions)
    action_names = [action.name for action in actions]
    walk_actions = [
        name for name in action_names
        if any(keyword in name.lower() for keyword in WALK_KEYWORDS)
    ]
    return {
        "source": source,
        "object_count": len(objects),
        "mesh_count": len(meshes),
        "armature_count": len(armatures),
        "helper_object_count": len(helper_objects),
        "bone_count_total": sum(len(arm.data.bones) for arm in armatures),
        "armatures": [
            {"name": arm.name, "bone_count": len(arm.data.bones)}
            for arm in armatures
        ],
        "meshes": [
            {"name": mesh.name, "vertex_count": len(mesh.data.vertices)}
            for mesh in meshes
        ],
        "action_names": action_names,
        "walk_actions": walk_actions,
        "helper_objects": [
            {"name": obj.name, "type": obj.type, "data_name": getattr(getattr(obj, "data", None), "name", None)}
            for obj in helper_objects
        ],
    }


def main() -> int:
    args = parse_args()
    source = os.path.abspath(args.source)
    if not os.path.exists(source):
        raise FileNotFoundError(source)
    clear_scene()
    import_source(source)
    report = build_report(source)
    payload = json.dumps(report, indent=2)
    print(payload)
    if args.report:
        report_path = os.path.abspath(args.report)
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
