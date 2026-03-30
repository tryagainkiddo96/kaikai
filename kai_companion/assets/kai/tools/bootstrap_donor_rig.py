#!/usr/bin/env python3
"""
Bootstrap an experimental Kai rig source by binding the canonical Kai mesh to
the low-poly donor armature, using `kai_runtime_candidate.glb` as a safer proxy
when it is available.

This is an explicit bootstrap path for local testing only. It does not make the
result canonical; it creates a reproducible experimental rig source for review.

Usage:
  blender -b --python tools/bootstrap_donor_rig.py --
  blender -b --python tools/bootstrap_donor_rig.py -- --source kai_textured.glb --donor kai-lite.glb --output kai_donor_bootstrap_rig_source.fbx
  blender -b --python tools/bootstrap_donor_rig.py -- --proxy kai_runtime_candidate.glb
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict

import bpy
import mathutils
from mathutils import kdtree


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    parser = argparse.ArgumentParser(description="Bootstrap an experimental Kai donor rig")
    parser.add_argument("--source", default="kai_textured.glb")
    parser.add_argument("--proxy", default="kai_runtime_candidate.glb")
    parser.add_argument("--donor", default="kai-lite.glb")
    parser.add_argument("--output", default="kai_donor_bootstrap_rig_source.fbx")
    return parser.parse_args(argv)


def log(message: str) -> None:
    print(f"[KAI_DONOR_BOOTSTRAP] {message}")


def base_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def abs_path(path: str, root: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.join(root, path)


def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_gltf(path: str) -> None:
    bpy.ops.import_scene.gltf(filepath=path)


def world_bbox(obj: bpy.types.Object) -> tuple[mathutils.Vector, mathutils.Vector]:
    corners = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
    mins = mathutils.Vector(
        (min(v.x for v in corners), min(v.y for v in corners), min(v.z for v in corners))
    )
    maxs = mathutils.Vector(
        (max(v.x for v in corners), max(v.y for v in corners), max(v.z for v in corners))
    )
    return mins, maxs


def import_gltf_objects(path: str) -> list[bpy.types.Object]:
    before = {obj.name for obj in bpy.context.scene.objects}
    import_gltf(path)
    return [obj for obj in bpy.context.scene.objects if obj.name not in before]


def pick_single_object(
    objects: list[bpy.types.Object],
    obj_type: str,
    exclude_names: set[str] | None = None,
) -> bpy.types.Object:
    exclude_names = exclude_names or set()
    candidates = [
        obj for obj in objects
        if obj.type == obj_type and obj.name not in exclude_names
    ]
    if not candidates:
        raise RuntimeError(f"No object of type {obj_type} found.")
    candidates.sort(key=lambda obj: len(getattr(obj.data, "vertices", [])), reverse=True)
    return candidates[0]


def apply_scale(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)


def copy_world_matrix(target: bpy.types.Object, source: bpy.types.Object) -> None:
    target.matrix_world = source.matrix_world.copy()


def clear_vertex_groups(mesh: bpy.types.Object) -> None:
    while mesh.vertex_groups:
        mesh.vertex_groups.remove(mesh.vertex_groups[0])


def remove_armature_modifiers(mesh: bpy.types.Object) -> None:
    for modifier in list(mesh.modifiers):
        if modifier.type == "ARMATURE":
            mesh.modifiers.remove(modifier)


def weighted_vertex_count(mesh: bpy.types.Object) -> int:
    count = 0
    for vertex in mesh.data.vertices:
        if vertex.groups:
            count += 1
    return count


def deform_group_names(armature: bpy.types.Object) -> set[str]:
    return {
        bone.name
        for bone in armature.data.bones
        if getattr(bone, "use_deform", False)
    }


def source_vertex_weights(
    mesh: bpy.types.Object,
    allowed_groups: set[str],
) -> tuple[kdtree.KDTree, dict[int, dict[str, float]]]:
    group_lookup = {group.index: group.name for group in mesh.vertex_groups}
    weights_by_vertex: dict[int, dict[str, float]] = {}
    weighted_vertices: list[tuple[mathutils.Vector, int]] = []
    for vertex in mesh.data.vertices:
        weights: dict[str, float] = {}
        for assignment in vertex.groups:
            group_name = group_lookup.get(assignment.group)
            if not group_name or group_name not in allowed_groups:
                continue
            if assignment.weight <= 0.0:
                continue
            weights[group_name] = assignment.weight
        if not weights:
            continue
        weights_by_vertex[vertex.index] = weights
        weighted_vertices.append((mesh.matrix_world @ vertex.co, vertex.index))

    if not weighted_vertices:
        raise RuntimeError(f"Source mesh {mesh.name} had no weighted vertices to bake from.")

    tree = kdtree.KDTree(len(weighted_vertices))
    for location, vertex_index in weighted_vertices:
        tree.insert(location, vertex_index)
    tree.balance()
    return tree, weights_by_vertex


def bake_weights_from_source(
    target: bpy.types.Object,
    source: bpy.types.Object,
    allowed_groups: set[str],
    max_influences: int = 4,
) -> None:
    clear_vertex_groups(target)
    if not allowed_groups:
        raise RuntimeError("No deform bones were available for weight baking.")

    tree, weights_by_vertex = source_vertex_weights(source, allowed_groups)
    target_groups = {
        name: target.vertex_groups.new(name=name)
        for name in sorted(allowed_groups)
    }
    weighted_vertices = 0

    for vertex in target.data.vertices:
        world_position = target.matrix_world @ vertex.co
        _, source_index, _distance = tree.find(world_position)
        raw_weights = weights_by_vertex.get(source_index, {})
        if not raw_weights:
            continue
        sorted_weights = sorted(
            raw_weights.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:max_influences]
        total = sum(weight for _name, weight in sorted_weights)
        if total <= 0.0:
            continue
        for group_name, weight in sorted_weights:
            target_groups[group_name].add([vertex.index], weight / total, "REPLACE")
        weighted_vertices += 1

    if weighted_vertices <= 0:
        raise RuntimeError(f"Weight bake produced zero weighted vertices on {target.name}.")


def prune_empty_vertex_groups(mesh: bpy.types.Object) -> None:
    used_group_names = {
        mesh.vertex_groups[assignment.group].name
        for vertex in mesh.data.vertices
        for assignment in vertex.groups
        if assignment.weight > 0.0
    }
    for group in list(mesh.vertex_groups):
        if group.name not in used_group_names:
            mesh.vertex_groups.remove(group)


def attach_armature_modifier(mesh: bpy.types.Object, armature: bpy.types.Object) -> None:
    remove_armature_modifiers(mesh)
    modifier = mesh.modifiers.new(name="KaiArmature", type="ARMATURE")
    modifier.object = armature
    mesh.parent = armature
    mesh.matrix_parent_inverse = armature.matrix_world.inverted()


def hide_object(obj: bpy.types.Object) -> None:
    obj.hide_set(True)
    obj.hide_render = True


def bbox_diagonal_length(obj: bpy.types.Object) -> float:
    mins, maxs = world_bbox(obj)
    return (maxs - mins).length


def main() -> int:
    args = parse_args()
    root = base_dir()
    source_path = abs_path(args.source, root)
    proxy_path = abs_path(args.proxy, root)
    donor_path = abs_path(args.donor, root)
    output_path = abs_path(args.output, root)

    if not os.path.exists(source_path):
        raise FileNotFoundError(source_path)
    proxy_exists = os.path.exists(proxy_path)
    if not os.path.exists(donor_path):
        raise FileNotFoundError(donor_path)

    reset_scene()
    source_objects = import_gltf_objects(source_path)
    canonical_mesh = pick_single_object(source_objects, "MESH")
    canonical_mesh.name = "KaiCanonical"

    proxy_mesh = canonical_mesh
    if proxy_exists and os.path.normcase(proxy_path) != os.path.normcase(source_path):
        proxy_objects = import_gltf_objects(proxy_path)
        proxy_mesh = pick_single_object(proxy_objects, "MESH")
        proxy_mesh.name = "KaiProxy"
        log(f"Proxy: {proxy_path}")
    else:
        log("Proxy: source mesh reused because kai_runtime_candidate.glb was unavailable or matched the source.")

    donor_objects = import_gltf_objects(donor_path)
    donor_armature = pick_single_object(donor_objects, "ARMATURE")
    donor_mesh = pick_single_object(donor_objects, "MESH", exclude_names={"Icosphere"})
    donor_mesh.name = "KaiDonorMesh"

    for obj in list(bpy.context.scene.objects):
        if obj.type == "MESH" and obj.name == "Icosphere":
            bpy.data.objects.remove(obj, do_unlink=True)

    bpy.context.view_layer.update()

    reference_mesh = proxy_mesh
    reference_diag = max(bbox_diagonal_length(reference_mesh), 0.001)
    donor_diag = max(bbox_diagonal_length(donor_mesh), 0.001)
    scale_factor = reference_diag / donor_diag
    donor_armature.scale = tuple(v * scale_factor for v in donor_armature.scale)
    donor_mesh.scale = tuple(v * scale_factor for v in donor_mesh.scale)
    bpy.context.view_layer.update()

    reference_min, reference_max = world_bbox(reference_mesh)
    donor_min, donor_max = world_bbox(donor_mesh)
    donor_center = (donor_min + donor_max) * 0.5
    reference_center = (reference_min + reference_max) * 0.5
    offset = reference_center - donor_center
    donor_armature.location += offset
    donor_mesh.location += offset
    bpy.context.view_layer.update()

    apply_scale(donor_armature)
    apply_scale(donor_mesh)

    if proxy_mesh is not canonical_mesh:
        copy_world_matrix(canonical_mesh, proxy_mesh)
        bpy.context.view_layer.update()
        apply_scale(proxy_mesh)
    else:
        copy_world_matrix(canonical_mesh, reference_mesh)
        bpy.context.view_layer.update()

    deform_groups = deform_group_names(donor_armature)

    if proxy_mesh is not canonical_mesh:
        bake_weights_from_source(proxy_mesh, donor_mesh, deform_groups)
        prune_empty_vertex_groups(proxy_mesh)
    else:
        clear_vertex_groups(proxy_mesh)
    remove_armature_modifiers(proxy_mesh)
    attach_armature_modifier(proxy_mesh, donor_armature)
    bpy.context.view_layer.update()

    apply_scale(canonical_mesh)
    if proxy_mesh is canonical_mesh:
        bake_weights_from_source(canonical_mesh, donor_mesh, deform_groups)
    else:
        bake_weights_from_source(canonical_mesh, proxy_mesh, deform_groups)
    prune_empty_vertex_groups(canonical_mesh)
    remove_armature_modifiers(canonical_mesh)
    attach_armature_modifier(canonical_mesh, donor_armature)
    bpy.context.view_layer.update()

    if proxy_mesh is not canonical_mesh:
        hide_object(proxy_mesh)

    donor_mesh.hide_set(True)
    donor_mesh.hide_render = True

    bpy.ops.object.select_all(action="DESELECT")
    canonical_mesh.select_set(True)
    donor_armature.select_set(True)
    bpy.context.view_layer.objects.active = donor_armature

    output_dir = os.path.dirname(output_path) or "."
    os.makedirs(output_dir, exist_ok=True)
    bpy.ops.export_scene.fbx(
        filepath=output_path,
        use_selection=True,
        object_types={"MESH", "ARMATURE"},
        apply_unit_scale=True,
        bake_space_transform=False,
        add_leaf_bones=False,
        bake_anim=True,
        bake_anim_use_all_actions=True,
        path_mode="AUTO",
        axis_forward="-Z",
        axis_up="Y",
    )

    log(f"Source: {source_path}")
    if proxy_mesh is canonical_mesh:
        log("Proxy: source mesh reused as reference")
    else:
        log(f"Proxy: {proxy_path}")
    log(f"Donor: {donor_path}")
    log(f"Output: {output_path}")
    log(f"Scale factor: {scale_factor:.4f}")
    if proxy_mesh is not canonical_mesh:
        log(f"Proxy vertex groups created: {len(proxy_mesh.vertex_groups)}")
        log(f"Proxy weighted vertices: {weighted_vertex_count(proxy_mesh)}")
    log(f"Vertex groups created: {len(canonical_mesh.vertex_groups)}")
    log(f"Weighted vertices: {weighted_vertex_count(canonical_mesh)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
