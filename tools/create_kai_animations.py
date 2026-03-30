from __future__ import annotations

from dataclasses import dataclass
import math

import bpy


@dataclass
class BoneTargets:
    hips: bpy.types.PoseBone | None
    spine: bpy.types.PoseBone | None
    chest: bpy.types.PoseBone | None
    neck: bpy.types.PoseBone | None
    head: bpy.types.PoseBone | None
    jaw: bpy.types.PoseBone | None
    tail: list[bpy.types.PoseBone]
    front_left: list[bpy.types.PoseBone]
    front_right: list[bpy.types.PoseBone]
    hind_left: list[bpy.types.PoseBone]
    hind_right: list[bpy.types.PoseBone]


def find_armature() -> bpy.types.Object:
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    if not armatures:
        raise RuntimeError("Run prepare_kai_rig_runtime.py first so the rig is loaded in this Blender session.")
    return max(armatures, key=lambda obj: len(obj.data.bones))


def normalize_name(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def find_first_bone(armature: bpy.types.Object, tokens: tuple[str, ...]) -> bpy.types.PoseBone | None:
    for bone in armature.pose.bones:
        normalized = normalize_name(bone.name)
        if any(token in normalized for token in tokens):
            return bone
    return None


def find_side_chain(
    armature: bpy.types.Object,
    side: str,
    primary_tokens: tuple[str, ...],
    fallback_tokens: tuple[str, ...],
) -> list[bpy.types.PoseBone]:
    side_token = normalize_name(side)
    matches: list[bpy.types.PoseBone] = []
    for bone in armature.pose.bones:
        normalized = normalize_name(bone.name)
        if side_token not in normalized:
            continue
        if any(token in normalized for token in primary_tokens):
            matches.append(bone)
    if matches:
        return matches
    for bone in armature.pose.bones:
        normalized = normalize_name(bone.name)
        if side_token in normalized and any(token in normalized for token in fallback_tokens):
            matches.append(bone)
    return matches


def find_tail_chain(armature: bpy.types.Object) -> list[bpy.types.PoseBone]:
    tail = [
        bone
        for bone in armature.pose.bones
        if "tail" in normalize_name(bone.name)
    ]
    return sorted(tail, key=lambda bone: bone.name)


def get_targets(armature: bpy.types.Object) -> BoneTargets:
    return BoneTargets(
        hips=find_first_bone(armature, ("hips", "pelvis", "root")),
        spine=find_first_bone(armature, ("spine",)),
        chest=find_first_bone(armature, ("spine2", "spine1", "chest", "upperchest")),
        neck=find_first_bone(armature, ("neck",)),
        head=find_first_bone(armature, ("head",)),
        jaw=find_first_bone(armature, ("jaw", "mouth")),
        tail=find_tail_chain(armature),
        front_left=find_side_chain(armature, "left", ("arm", "shoulder", "forearm", "hand"), ("front",)),
        front_right=find_side_chain(armature, "right", ("arm", "shoulder", "forearm", "hand"), ("front",)),
        hind_left=find_side_chain(armature, "left", ("upleg", "leg", "foot", "toe"), ("hind", "back")),
        hind_right=find_side_chain(armature, "right", ("upleg", "leg", "foot", "toe"), ("hind", "back")),
    )


def clear_pose(armature: bpy.types.Object) -> None:
    for bone in armature.pose.bones:
        bone.rotation_mode = "XYZ"
        bone.location = (0.0, 0.0, 0.0)
        bone.rotation_euler = (0.0, 0.0, 0.0)
        bone.scale = (1.0, 1.0, 1.0)


def keyframe_pose(
    armature: bpy.types.Object,
    frame: int,
    pose_builder,
) -> None:
    bpy.context.scene.frame_set(frame)
    clear_pose(armature)
    pose_builder()
    for bone in armature.pose.bones:
        bone.keyframe_insert(data_path="location", frame=frame)
        bone.keyframe_insert(data_path="rotation_euler", frame=frame)
        bone.keyframe_insert(data_path="scale", frame=frame)


def rotate_chain(chain: list[bpy.types.PoseBone], x: float = 0.0, y: float = 0.0, z: float = 0.0) -> None:
    for index, bone in enumerate(chain):
        falloff = max(0.25, 1.0 - index * 0.22)
        bone.rotation_euler.x += x * falloff
        bone.rotation_euler.y += y * falloff
        bone.rotation_euler.z += z * falloff


def add_tail_wag(tail: list[bpy.types.PoseBone], strength: float) -> None:
    rotate_chain(tail, z=strength)


def push_action_to_nla(armature: bpy.types.Object, action: bpy.types.Action) -> None:
    animation_data = armature.animation_data_create()
    for track in list(animation_data.nla_tracks):
        if track.name == action.name:
            animation_data.nla_tracks.remove(track)
    track = animation_data.nla_tracks.new()
    track.name = action.name
    strip = track.strips.new(action.name, int(action.frame_range[0]), action)
    strip.action_frame_end = action.frame_range[1]
    track.mute = True
    animation_data.action = None


def recreate_action(name: str) -> bpy.types.Action:
    existing = bpy.data.actions.get(name)
    if existing is not None:
        bpy.data.actions.remove(existing)
    return bpy.data.actions.new(name=name)


def create_idle_action(armature: bpy.types.Object, targets: BoneTargets) -> bpy.types.Action:
    action = recreate_action("Idle")
    armature.animation_data_create().action = action

    def frame_1() -> None:
        if targets.hips:
            targets.hips.location.z += 0.01
        if targets.head:
            targets.head.rotation_euler.x += math.radians(4.0)
        add_tail_wag(targets.tail, math.radians(10.0))

    def frame_20() -> None:
        if targets.hips:
            targets.hips.location.z -= 0.012
        if targets.head:
            targets.head.rotation_euler.z += math.radians(3.0)
        add_tail_wag(targets.tail, math.radians(-12.0))

    def frame_40() -> None:
        if targets.hips:
            targets.hips.location.z += 0.008
        if targets.head:
            targets.head.rotation_euler.z += math.radians(-2.5)
        add_tail_wag(targets.tail, math.radians(8.0))

    def frame_60() -> None:
        frame_1()

    for frame, builder in ((1, frame_1), (20, frame_20), (40, frame_40), (60, frame_60)):
        keyframe_pose(armature, frame, builder)
    push_action_to_nla(armature, action)
    return action


def create_walk_action(armature: bpy.types.Object, targets: BoneTargets) -> bpy.types.Action:
    action = recreate_action("Walk")
    armature.animation_data_create().action = action

    def stride(front_forward: bool) -> None:
        front = math.radians(18.0 if front_forward else -18.0)
        hind = math.radians(-18.0 if front_forward else 18.0)
        rotate_chain(targets.front_left, x=front)
        rotate_chain(targets.front_right, x=-front)
        rotate_chain(targets.hind_left, x=hind)
        rotate_chain(targets.hind_right, x=-hind)
        if targets.hips:
            targets.hips.location.z += 0.015 if front_forward else -0.01
            targets.hips.location.y += 0.01 if front_forward else -0.01
        if targets.spine:
            targets.spine.rotation_euler.z += math.radians(3.0 if front_forward else -3.0)
        add_tail_wag(targets.tail, math.radians(6.0 if front_forward else -6.0))

    for frame, forward in ((1, True), (12, False), (24, True)):
        keyframe_pose(armature, frame, lambda forward=forward: stride(forward))
    push_action_to_nla(armature, action)
    return action


def create_bark_action(armature: bpy.types.Object, targets: BoneTargets) -> bpy.types.Action:
    action = recreate_action("Bark")
    armature.animation_data_create().action = action

    def ready_pose() -> None:
        if targets.hips:
            targets.hips.location.z += 0.018
        if targets.chest:
            targets.chest.rotation_euler.x += math.radians(-8.0)
        if targets.head:
            targets.head.rotation_euler.x += math.radians(-10.0)
        if targets.jaw:
            targets.jaw.rotation_euler.x += math.radians(6.0)
        add_tail_wag(targets.tail, math.radians(8.0))

    def bark_pose() -> None:
        if targets.chest:
            targets.chest.rotation_euler.x += math.radians(-16.0)
        if targets.head:
            targets.head.rotation_euler.x += math.radians(-22.0)
        if targets.jaw:
            targets.jaw.rotation_euler.x += math.radians(18.0)
        add_tail_wag(targets.tail, math.radians(-12.0))

    for frame, builder in ((1, ready_pose), (8, bark_pose), (16, ready_pose), (24, ready_pose)):
        keyframe_pose(armature, frame, builder)
    push_action_to_nla(armature, action)
    return action


def create_tail_wag_action(armature: bpy.types.Object, targets: BoneTargets) -> bpy.types.Action:
    action = recreate_action("TailWag")
    armature.animation_data_create().action = action

    def wag_left() -> None:
        if targets.head:
            targets.head.rotation_euler.z += math.radians(-4.0)
        add_tail_wag(targets.tail, math.radians(-24.0))

    def wag_right() -> None:
        if targets.head:
            targets.head.rotation_euler.z += math.radians(4.0)
        add_tail_wag(targets.tail, math.radians(24.0))

    for frame, builder in ((1, wag_left), (10, wag_right), (20, wag_left), (30, wag_right)):
        keyframe_pose(armature, frame, builder)
    push_action_to_nla(armature, action)
    return action


def create_lie_down_action(armature: bpy.types.Object, targets: BoneTargets) -> bpy.types.Action:
    action = recreate_action("LieDown")
    armature.animation_data_create().action = action

    def stand_pose() -> None:
        if targets.hips:
            targets.hips.location.z += 0.01
        add_tail_wag(targets.tail, math.radians(6.0))

    def lower_pose() -> None:
        if targets.hips:
            targets.hips.location.z -= 0.07
            targets.hips.rotation_euler.x += math.radians(8.0)
        rotate_chain(targets.front_left, x=math.radians(-12.0))
        rotate_chain(targets.front_right, x=math.radians(-12.0))
        rotate_chain(targets.hind_left, x=math.radians(20.0))
        rotate_chain(targets.hind_right, x=math.radians(20.0))
        if targets.head:
            targets.head.rotation_euler.x += math.radians(10.0)

    for frame, builder in ((1, stand_pose), (20, lower_pose), (40, lower_pose), (60, lower_pose)):
        keyframe_pose(armature, frame, builder)
    push_action_to_nla(armature, action)
    return action


def main() -> None:
    armature = find_armature()
    targets = get_targets(armature)
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 60
    create_idle_action(armature, targets)
    create_walk_action(armature, targets)
    create_bark_action(armature, targets)
    create_tail_wag_action(armature, targets)
    create_lie_down_action(armature, targets)
    clear_pose(armature)
    scene.frame_set(1)
    print("Created Kai actions: Idle, Walk, Bark, TailWag, LieDown")


if __name__ == "__main__":
    main()
