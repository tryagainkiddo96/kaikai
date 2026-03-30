#!/usr/bin/env python3
"""
Defensive Blender automation pass for KAI model idle animation polish.

Usage (from Blender CLI):
  blender -b --python tools/blender_kai_animation_pass.py --
  blender -b --python tools/blender_kai_animation_pass.py -- --source kai_mixamo_rigged_source.fbx --output kai_textured_rigged.glb --require-armature --require-walk-action
"""

import argparse
import math
import os
import sys
import traceback

import bpy
import mathutils


WALK_KEYWORDS = ("walk", "trot", "run", "gallop", "locomotion", "cycle", "move")


def log(message):
    print(f"[KAI_ANIM_PASS] {message}")


def norm(path):
    return os.path.normcase(os.path.abspath(path))


def get_cli_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="KAI animation quality pass")
    parser.add_argument("--source", help="Source .blend/.glb/.gltf path")
    parser.add_argument("--output", help="Output GLB path")
    parser.add_argument("--frame-start", type=int, default=1)
    parser.add_argument("--frame-end", type=int, default=121)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--require-armature", action="store_true")
    parser.add_argument("--require-walk-action", action="store_true")
    return parser.parse_args(argv)


def resolve_base_dir():
    script_file = os.path.abspath(__file__)
    tools_dir = os.path.dirname(script_file)
    return os.path.dirname(tools_dir)


def find_default_source(base_dir):
    candidates = [
        "kai_mixamo_rigged_source.fbx",
        "kai_textured.glb",
        "kai_texture_workspace.blend",
    ]
    for name in candidates:
        path = os.path.join(base_dir, name)
        if os.path.exists(path):
            return path
    return None


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False, confirm=False)
    for block in (bpy.data.meshes, bpy.data.armatures, bpy.data.materials, bpy.data.images, bpy.data.actions):
        for datablock in list(block):
            if datablock.users == 0:
                block.remove(datablock)


def is_helper_object(obj) -> bool:
    if obj is None:
        return False
    object_name = getattr(obj, "name", "")
    data_name = getattr(getattr(obj, "data", None), "name", "")
    return object_name.startswith("Icosphere") or data_name.startswith("Icosphere")


def remove_helper_objects() -> None:
    for obj in list(bpy.context.scene.objects):
        if is_helper_object(obj):
            bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0 and mesh.name.startswith("Icosphere"):
            bpy.data.meshes.remove(mesh)


def load_source(source_path):
    if not source_path:
        log("No --source provided; using currently opened scene.")
        return True

    if not os.path.exists(source_path):
        log(f"Source not found: {source_path}")
        return False

    ext = os.path.splitext(source_path)[1].lower()
    if ext == ".blend":
        current = bpy.data.filepath
        if not current or norm(current) != norm(source_path):
            log(f"Opening blend source: {source_path}")
            bpy.ops.wm.open_mainfile(filepath=source_path)
        else:
            log("Blend source already loaded.")
        return True

    if ext in (".glb", ".gltf"):
        log(f"Importing glTF source: {source_path}")
        clear_scene()
        bpy.ops.import_scene.gltf(filepath=source_path)
        return True
    if ext == ".fbx":
        log(f"Importing FBX source: {source_path}")
        clear_scene()
        bpy.ops.import_scene.fbx(filepath=source_path)
        return True

    log(f"Unsupported source extension: {ext}")
    return False


def pick_armature():
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    if not armatures:
        return None
    armatures.sort(key=lambda a: len(a.data.bones), reverse=True)
    return armatures[0]


def find_preferred_bone(arm_obj):
    if not arm_obj:
        return None
    preferred = [
        "chest",
        "spine",
        "torso",
        "body",
        "hips",
        "pelvis",
        "root",
    ]
    pose_bones = list(arm_obj.pose.bones)
    for token in preferred:
        for bone in pose_bones:
            if token in bone.name.lower():
                return bone
    return pose_bones[0] if pose_bones else None


def ensure_action(owner, name):
    if owner.animation_data is None:
        owner.animation_data_create()
    action = bpy.data.actions.new(name=name)
    owner.animation_data.action = action
    return action


def clear_nla_tracks(owner):
    if owner is None:
        return
    if owner.animation_data is None:
        owner.animation_data_create()
    tracks = owner.animation_data.nla_tracks
    for track in list(tracks):
        tracks.remove(track)


def add_action_as_nla_strip(owner, action, start_frame, end_frame):
    if owner is None or action is None:
        return
    if owner.animation_data is None:
        owner.animation_data_create()
    try:
        track = owner.animation_data.nla_tracks.new()
        track.name = action.name
        strip = track.strips.new(action.name, start_frame, action)
        strip.action_frame_start = start_frame
        strip.action_frame_end = end_frame
        strip.frame_end = end_frame
        strip.extrapolation = "HOLD_FORWARD"
    except Exception as exc:
        log(f"Skipping NLA strip for '{action.name}' on '{owner.name}': {exc}")


def insert_breath_keys_for_bone(arm_obj, bone, frame_start, frame_end):
    action = ensure_action(arm_obj, "KAI_Idle_Breath")
    total = max(20, frame_end - frame_start)
    amplitude = 0.015
    frames = [
        frame_start,
        frame_start + int(total * 0.25),
        frame_start + int(total * 0.50),
        frame_start + int(total * 0.75),
        frame_end,
    ]
    values = [0.0, amplitude, 0.0, -amplitude, 0.0]
    path = f'pose.bones["{bone.name}"].location'

    original = bone.location.copy()
    for frame, value in zip(frames, values):
        bone.location = original.copy()
        bone.location.z = original.z + value
        arm_obj.keyframe_insert(data_path=path, frame=frame, index=2)
    bone.location = original
    log(f"Applied breathing keys on bone '{bone.name}'.")
    return action


def insert_breath_keys_for_object(obj, frame_start, frame_end):
    action = ensure_action(obj, "KAI_Idle_Breath_Object")
    total = max(20, frame_end - frame_start)
    amplitude = 0.01
    frames = [
        frame_start,
        frame_start + int(total * 0.25),
        frame_start + int(total * 0.50),
        frame_start + int(total * 0.75),
        frame_end,
    ]
    values = [0.0, amplitude, 0.0, -amplitude, 0.0]

    original = obj.location.copy()
    for frame, value in zip(frames, values):
        obj.location = original.copy()
        obj.location.z = original.z + value
        obj.keyframe_insert(data_path="location", frame=frame, index=2)
    obj.location = original
    log(f"Applied breathing keys on object '{obj.name}'.")
    return action


def _insert_object_action(obj, action_name, frame_start, frame_end, z_amp, rot_x_amp, rot_z_amp, scale_amp):
    action = ensure_action(obj, action_name)
    total = max(20, frame_end - frame_start)
    frames = [
        frame_start,
        frame_start + int(total * 0.25),
        frame_start + int(total * 0.50),
        frame_start + int(total * 0.75),
        frame_end,
    ]
    curve = [0.0, 1.0, 0.0, -1.0, 0.0]

    loc_original = obj.location.copy()
    rot_original = obj.rotation_euler.copy()
    scl_original = obj.scale.copy()

    for frame, c in zip(frames, curve):
        obj.location = loc_original.copy()
        obj.rotation_euler = rot_original.copy()
        obj.scale = scl_original.copy()
        obj.location.z = loc_original.z + (z_amp * c)
        obj.rotation_euler.x = rot_original.x + (rot_x_amp * c)
        obj.rotation_euler.z = rot_original.z + (rot_z_amp * c)
        obj.scale.y = scl_original.y + (scale_amp * c * 0.65)
        obj.scale.x = scl_original.x - (scale_amp * c * 0.35)
        obj.scale.z = scl_original.z - (scale_amp * c * 0.25)
        obj.keyframe_insert(data_path="location", frame=frame)
        obj.keyframe_insert(data_path="rotation_euler", frame=frame)
        obj.keyframe_insert(data_path="scale", frame=frame)

    obj.location = loc_original
    obj.rotation_euler = rot_original
    obj.scale = scl_original
    log(f"Created object clip '{action_name}' on '{obj.name}'.")
    return action


def _insert_object_walk_action(obj, frame_start, frame_end):
    action = ensure_action(obj, "KAI_Walk")
    total = max(24, frame_end - frame_start)
    frames = [
        frame_start,
        frame_start + int(total * 0.125),
        frame_start + int(total * 0.25),
        frame_start + int(total * 0.375),
        frame_start + int(total * 0.5),
        frame_start + int(total * 0.625),
        frame_start + int(total * 0.75),
        frame_start + int(total * 0.875),
        frame_end,
    ]
    loc_original = obj.location.copy()
    rot_original = obj.rotation_euler.copy()
    scl_original = obj.scale.copy()

    for idx, frame in enumerate(frames):
        phase = (idx / max(1, len(frames) - 1)) * (math.pi * 2.0)
        obj.location = loc_original.copy()
        obj.rotation_euler = rot_original.copy()
        obj.scale = scl_original.copy()
        obj.location.x = loc_original.x + math.sin(phase * 0.5) * 0.018
        obj.location.z = loc_original.z + math.sin(phase) * 0.024
        obj.rotation_euler.x = rot_original.x + math.sin(phase + (math.pi * 0.5)) * 0.075
        obj.rotation_euler.z = rot_original.z + math.sin(phase * 0.5) * 0.12
        obj.scale.y = scl_original.y + math.sin(phase) * 0.015
        obj.scale.x = scl_original.x - math.sin(phase) * 0.009
        obj.scale.z = scl_original.z - math.sin(phase) * 0.006
        obj.keyframe_insert(data_path="location", frame=frame)
        obj.keyframe_insert(data_path="rotation_euler", frame=frame)
        obj.keyframe_insert(data_path="scale", frame=frame)

    obj.location = loc_original
    obj.rotation_euler = rot_original
    obj.scale = scl_original
    log(f"Created object clip 'KAI_Walk' on '{obj.name}'.")
    return action


def create_object_companion_action_set(obj, frame_start, frame_end):
    return [
        _insert_object_action(obj, "KAI_Idle", frame_start, frame_end, 0.012, 0.04, 0.02, 0.02),
        _insert_object_action(obj, "KAI_Alert", frame_start, frame_end, 0.009, 0.08, 0.04, 0.016),
        _insert_object_action(obj, "KAI_Wag", frame_start, frame_end, 0.010, 0.06, 0.12, 0.018),
        _insert_object_action(obj, "KAI_Rest", frame_start, frame_end, 0.006, -0.10, 0.02, 0.01),
        _insert_object_walk_action(obj, frame_start, frame_end),
    ]


def find_pose_bone(arm_obj, *tokens):
    if arm_obj is None:
        return None
    pose_bones = list(arm_obj.pose.bones)
    lowered_tokens = [token.lower() for token in tokens if token]
    for token in lowered_tokens:
        for bone in pose_bones:
            if token in bone.name.lower():
                return bone
    return None


def copy_pose_state(arm_obj, bones):
    state = {
        "__object_location__": arm_obj.location.copy(),
        "__object_rotation__": arm_obj.rotation_euler.copy(),
        "__object_scale__": arm_obj.scale.copy(),
    }
    for bone in bones:
        if bone is None:
            continue
        bone.rotation_mode = "XYZ"
        state[bone.name] = {
            "location": bone.location.copy(),
            "rotation": bone.rotation_euler.copy(),
            "scale": bone.scale.copy(),
        }
    return state


def restore_pose_state(arm_obj, bones, state):
    arm_obj.location = state["__object_location__"].copy()
    arm_obj.rotation_euler = state["__object_rotation__"].copy()
    arm_obj.scale = state["__object_scale__"].copy()
    for bone in bones:
        if bone is None:
            continue
        bone_state = state.get(bone.name)
        if not bone_state:
            continue
        bone.rotation_mode = "XYZ"
        bone.location = bone_state["location"].copy()
        bone.rotation_euler = bone_state["rotation"].copy()
        bone.scale = bone_state["scale"].copy()


def _apply_bone_transform(bone, location_delta=None, rotation_delta=None, scale_delta=None):
    if bone is None:
        return
    bone.rotation_mode = "XYZ"
    if location_delta is not None:
        bone.location = bone.location.copy() + location_delta
    if rotation_delta is not None:
        current = bone.rotation_euler.copy()
        bone.rotation_euler = mathutils.Euler(
            (
                current.x + rotation_delta.x,
                current.y + rotation_delta.y,
                current.z + rotation_delta.z,
            ),
            "XYZ",
        )
    if scale_delta is not None:
        bone.scale = bone.scale.copy() + scale_delta


def _key_armature_state(arm_obj, frame, bones):
    arm_obj.keyframe_insert(data_path="location", frame=frame)
    arm_obj.keyframe_insert(data_path="rotation_euler", frame=frame)
    arm_obj.keyframe_insert(data_path="scale", frame=frame)
    for bone in bones:
        if bone is None:
            continue
        bone.keyframe_insert(data_path="location", frame=frame)
        bone.keyframe_insert(data_path="rotation_euler", frame=frame)
        bone.keyframe_insert(data_path="scale", frame=frame)


def _armature_curve_frames(frame_start, frame_end):
    total = max(20, frame_end - frame_start)
    return [
        frame_start,
        frame_start + int(total * 0.25),
        frame_start + int(total * 0.50),
        frame_start + int(total * 0.75),
        frame_end,
    ]


def _insert_armature_action(arm_obj, action_name, frame_start, frame_end, per_frame_callback):
    action = ensure_action(arm_obj, action_name)
    frames = _armature_curve_frames(frame_start, frame_end)
    controls = {
        "root": find_pose_bone(arm_obj, "root"),
        "hips": find_pose_bone(arm_obj, "hips", "pelvis", "torso"),
        "chest": find_pose_bone(arm_obj, "chest", "spine_fk.008", "spine_fk.007", "spine"),
        "neck": find_pose_bone(arm_obj, "neck"),
        "head": find_pose_bone(arm_obj, "head"),
        "tail": find_pose_bone(arm_obj, "tail"),
    }
    active_bones = [bone for bone in controls.values() if bone is not None]
    original_state = copy_pose_state(arm_obj, active_bones)

    for idx, frame in enumerate(frames):
        restore_pose_state(arm_obj, active_bones, original_state)
        per_frame_callback(frame=frame, idx=idx, count=len(frames), controls=controls)
        _key_armature_state(arm_obj, frame, active_bones)

    restore_pose_state(arm_obj, active_bones, original_state)
    log(f"Created armature clip '{action_name}' on '{arm_obj.name}'.")
    return action


def create_armature_idle_action(arm_obj, frame_start, frame_end):
    curve = [0.0, 1.0, 0.0, -1.0, 0.0]

    def _callback(frame, idx, count, controls):
        c = curve[idx]
        arm_obj.location.z += 0.004 * c
        _apply_bone_transform(controls["chest"], location_delta=mathutils.Vector((0.0, 0.0, 0.012 * c)))
        _apply_bone_transform(controls["neck"], rotation_delta=mathutils.Euler((0.02 * c, 0.0, 0.015 * c), "XYZ"))
        _apply_bone_transform(controls["head"], rotation_delta=mathutils.Euler((0.025 * c, 0.0, -0.02 * c), "XYZ"))

    return _insert_armature_action(arm_obj, "KAI_Idle", frame_start, frame_end, _callback)


def create_armature_alert_action(arm_obj, frame_start, frame_end):
    curve = [0.0, 1.0, 0.25, 0.8, 0.0]

    def _callback(frame, idx, count, controls):
        c = curve[idx]
        arm_obj.location.z += 0.008 * c
        arm_obj.rotation_euler.x += -0.02 * c
        _apply_bone_transform(controls["hips"], rotation_delta=mathutils.Euler((-0.05 * c, 0.0, 0.0), "XYZ"))
        _apply_bone_transform(controls["chest"], rotation_delta=mathutils.Euler((0.08 * c, 0.0, 0.0), "XYZ"))
        _apply_bone_transform(controls["neck"], rotation_delta=mathutils.Euler((0.18 * c, 0.0, 0.02 * c), "XYZ"))
        _apply_bone_transform(controls["head"], rotation_delta=mathutils.Euler((0.2 * c, 0.0, -0.03 * c), "XYZ"))

    return _insert_armature_action(arm_obj, "KAI_Alert", frame_start, frame_end, _callback)


def create_armature_wag_action(arm_obj, frame_start, frame_end):
    curve = [0.0, 1.0, 0.0, -1.0, 0.0]

    def _callback(frame, idx, count, controls):
        c = curve[idx]
        arm_obj.location.x += 0.006 * c
        _apply_bone_transform(controls["hips"], rotation_delta=mathutils.Euler((0.0, 0.0, 0.09 * c), "XYZ"))
        _apply_bone_transform(controls["chest"], rotation_delta=mathutils.Euler((0.0, 0.0, -0.05 * c), "XYZ"))
        _apply_bone_transform(controls["neck"], rotation_delta=mathutils.Euler((0.01 * c, 0.0, -0.08 * c), "XYZ"))
        _apply_bone_transform(controls["head"], rotation_delta=mathutils.Euler((0.0, 0.0, -0.14 * c), "XYZ"))
        if controls["tail"] is not None:
            _apply_bone_transform(controls["tail"], rotation_delta=mathutils.Euler((0.0, 0.0, 0.28 * c), "XYZ"))

    return _insert_armature_action(arm_obj, "KAI_Wag", frame_start, frame_end, _callback)


def create_armature_rest_action(arm_obj, frame_start, frame_end):
    curve = [0.0, 1.0, 1.0, 1.0, 0.0]

    def _callback(frame, idx, count, controls):
        c = curve[idx]
        arm_obj.location.z += -0.01 * c
        arm_obj.rotation_euler.x += 0.05 * c
        _apply_bone_transform(controls["hips"], rotation_delta=mathutils.Euler((0.08 * c, 0.0, 0.0), "XYZ"))
        _apply_bone_transform(controls["chest"], rotation_delta=mathutils.Euler((-0.12 * c, 0.0, 0.0), "XYZ"))
        _apply_bone_transform(controls["neck"], rotation_delta=mathutils.Euler((-0.25 * c, 0.0, 0.02 * c), "XYZ"))
        _apply_bone_transform(controls["head"], rotation_delta=mathutils.Euler((-0.32 * c, 0.0, -0.02 * c), "XYZ"))

    return _insert_armature_action(arm_obj, "KAI_Rest", frame_start, frame_end, _callback)


def duplicate_walk_action(arm_obj):
    walk_source = next(
        (
            action for action in bpy.data.actions
            if any(keyword in action.name.lower() for keyword in WALK_KEYWORDS)
        ),
        None,
    )
    if walk_source is None:
        return None
    action = walk_source.copy()
    action.name = "KAI_Walk"
    if arm_obj.animation_data is None:
        arm_obj.animation_data_create()
    arm_obj.animation_data.action = action
    log(f"Created walk alias '{action.name}' from '{walk_source.name}'.")
    return action


def create_armature_companion_action_set(arm_obj, frame_start, frame_end):
    return [
        create_armature_idle_action(arm_obj, frame_start, frame_end),
        create_armature_alert_action(arm_obj, frame_start, frame_end),
        create_armature_wag_action(arm_obj, frame_start, frame_end),
        create_armature_rest_action(arm_obj, frame_start, frame_end),
        duplicate_walk_action(arm_obj),
    ]


def find_blink_shape_keys():
    tokens = ("blink", "eye_close", "eyelid", "closeeye", "eyeshut", "winkt")
    matches = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or not obj.data.shape_keys:
            continue
        key_blocks = obj.data.shape_keys.key_blocks
        for kb in key_blocks:
            name = kb.name.lower()
            if kb.name == "Basis":
                continue
            if any(token in name for token in tokens):
                matches.append((obj, kb))
    return matches


def insert_blink_keys(frame_start, frame_end):
    blink_targets = find_blink_shape_keys()
    if not blink_targets:
        log("No blink-like shape keys found. Skipping blink pass.")
        return []

    actions = []
    span = max(24, frame_end - frame_start)
    blink_starts = [
        frame_start + int(span * 0.2),
        frame_start + int(span * 0.52),
        frame_start + int(span * 0.82),
    ]

    for obj, kb in blink_targets:
        sk = obj.data.shape_keys
        if sk.animation_data is None:
            sk.animation_data_create()
        action = bpy.data.actions.new(name=f"KAI_Blink_{obj.name}")
        sk.animation_data.action = action

        path = f'key_blocks["{kb.name}"].value'
        for start in blink_starts:
            key_frames = [max(frame_start, start - 1), start, min(frame_end, start + 2)]
            key_values = [0.0, 1.0, 0.0]
            for f, v in zip(key_frames, key_values):
                kb.value = v
                sk.keyframe_insert(data_path=path, frame=f)
        kb.value = 0.0
        actions.append(action)
        log(f"Applied blink keys on '{obj.name}:{kb.name}'.")
    return actions


def smooth_actions(actions):
    for action in actions:
        if not action:
            continue
        # Blender 5+ can store animation in layered channels where `fcurves`
        # may not be exposed on Action directly.
        if not hasattr(action, "fcurves"):
            log(f"Skipping smoothing for action '{action.name}' (no legacy fcurves API).")
            continue
        for fcurve in action.fcurves:
            for kp in fcurve.keyframe_points:
                kp.interpolation = "BEZIER"
                kp.handle_left_type = "AUTO_CLAMPED"
                kp.handle_right_type = "AUTO_CLAMPED"


def action_names_have_walk(names):
    for name in names:
        lowered = name.lower()
        if any(keyword in lowered for keyword in WALK_KEYWORDS):
            return True
    return False


def set_scene_timing(frame_start, frame_end, fps):
    scene = bpy.context.scene
    scene.frame_start = frame_start
    scene.frame_end = frame_end
    scene.render.fps = fps


def export_glb(output_path):
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    remove_helper_objects()
    bpy.ops.object.select_all(action="DESELECT")
    for obj in bpy.context.scene.objects:
        if obj.type in {"MESH", "ARMATURE"} and not is_helper_object(obj):
            obj.select_set(True)
    export_active = next(
        (obj for obj in bpy.context.scene.objects if obj.select_get() and obj.type == "ARMATURE"),
        None,
    )
    if export_active is None:
        export_active = next((obj for obj in bpy.context.scene.objects if obj.select_get()), None)
    if export_active is not None:
        bpy.context.view_layer.objects.active = export_active
    bpy.ops.export_scene.gltf(
        filepath=output_path,
        export_format="GLB",
        use_selection=True,
        export_animations=True,
        export_animation_mode="ACTIONS",
        export_frame_range=True,
        export_merge_animation="NONE",
        export_force_sampling=True,
    )
    log(f"Exported GLB: {output_path}")


def run_pass(frame_start, frame_end):
    touched_actions = []

    arm_obj = pick_armature()
    if arm_obj:
        bone = find_preferred_bone(arm_obj)
        if bone:
            touched_actions.append(insert_breath_keys_for_bone(arm_obj, bone, frame_start, frame_end))
            touched_actions.extend(create_armature_companion_action_set(arm_obj, frame_start, frame_end))
        else:
            log("Armature found but no pose bones were available.")
    else:
        fallback_obj = next((o for o in bpy.context.scene.objects if o.type == "MESH"), None)
        if fallback_obj:
            touched_actions.append(insert_breath_keys_for_object(fallback_obj, frame_start, frame_end))
            touched_actions.extend(create_object_companion_action_set(fallback_obj, frame_start, frame_end))
        else:
            log("No armature or mesh object found for breathing pass.")

    touched_actions.extend(insert_blink_keys(frame_start, frame_end))
    smooth_actions(touched_actions)

    export_actions = list(bpy.data.actions)

    # Ensure source and created clips can be exported as their own animations.
    if arm_obj:
        clear_nla_tracks(arm_obj)
        for action in export_actions:
            add_action_as_nla_strip(arm_obj, action, frame_start, frame_end)
    else:
        fallback_obj = next((o for o in bpy.context.scene.objects if o.type == "MESH"), None)
        clear_nla_tracks(fallback_obj)
        for action in export_actions:
            add_action_as_nla_strip(fallback_obj, action, frame_start, frame_end)

    return touched_actions, export_actions


def main():
    args = get_cli_args()
    base_dir = resolve_base_dir()
    source = args.source or find_default_source(base_dir)

    if source and not os.path.isabs(source):
        source = os.path.join(base_dir, source)

    output = args.output
    if not output:
        output = os.path.join(base_dir, "kai_textured_rigged.glb")
    elif not os.path.isabs(output):
        output = os.path.join(base_dir, output)

    log(f"Base directory: {base_dir}")
    log(f"Resolved source: {source if source else 'CURRENT_SCENE'}")
    log(f"Resolved output: {output}")

    ok = load_source(source)
    if not ok:
        log("Load step failed; animation pass aborted.")
        return 1
    remove_helper_objects()

    if args.require_armature and pick_armature() is None:
        log("Required armature was not found on the source asset; refusing to export a rig target.")
        return 1

    set_scene_timing(args.frame_start, args.frame_end, args.fps)
    touched, export_actions = run_pass(args.frame_start, args.frame_end)
    if not touched:
        log("No actions were created. Export will still run if scene is valid.")
    if args.require_walk_action and not action_names_have_walk([action.name for action in export_actions]):
        log("Required walk-like action was not found; refusing to export a rig target.")
        return 1

    export_glb(output)
    log("Animation quality pass completed.")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        log(f"Fatal error: {exc}")
        traceback.print_exc()
        code = 1
    sys.exit(code)
