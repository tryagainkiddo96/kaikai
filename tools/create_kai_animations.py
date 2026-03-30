"""
Kai Animation Creator (Blender)
Add basic animations to the rigged Kai model.
Run AFTER prepare_kai_rig_runtime.py.

Creates:
  - Idle (breathing + subtle sway, 60 frames)
  - Walk cycle (120 frames)
  - Bark (30 frames)
  - Tail wag (40 frames)
  - Lie down (45 frames)

Usage:
  1. Open the rigged model in Blender (after rig prep)
  2. Run this script
  3. Export with prepare_kai_rig_runtime.py export step
"""

import bpy
import math

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

FPS = 30

def get_armature():
    """Get the armature in the scene."""
    for obj in bpy.context.scene.objects:
        if obj.type == 'ARMATURE':
            return obj
    raise RuntimeError("No armature found. Import the rigged model first.")


def set_keyframe(bone_name, frame, location=None, rotation=None, scale=None):
    """Set a keyframe on a bone at a specific frame."""
    armature = bpy.context.object
    bpy.context.scene.frame_set(frame)
    
    if bone_name in armature.pose.bones:
        pbone = armature.pose.bones[bone_name]
        if location:
            pbone.location = location
            pbone.keyframe_insert(data_path="location", frame=frame)
        if rotation:
            pbone.rotation_euler = rotation
            pbone.keyframe_insert(data_path="rotation_euler", frame=frame)
        if scale:
            pbone.scale = scale
            pbone.keyframe_insert(data_path="scale", frame=frame)


def create_action(name, frame_start, frame_end):
    """Create a new action for the armature."""
    armature = get_armature()
    
    # Enter pose mode
    bpy.ops.object.select_all(action='DESELECT')
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')
    
    # Create action
    action = bpy.data.actions.new(name=name)
    
    if not armature.animation_data:
        armature.animation_data_create()
    
    armature.animation_data.action = action
    
    # Set frame range
    bpy.context.scene.frame_start = frame_start
    bpy.context.scene.frame_end = frame_end
    
    return action


# ---------------------------------------------------------------------------
# Animations
# ---------------------------------------------------------------------------

def create_idle_animation():
    """Breathing + subtle body sway (60 frames, looping)."""
    action = create_action("Idle", 1, 60)
    armature = get_armature()
    
    # Spine breathing — scale up/down
    spine_bones = ['Spine', 'Spine1', 'Spine2']
    
    for frame in [1, 30, 60]:
        bpy.context.scene.frame_set(frame)
        for bone_name in spine_bones:
            if bone_name in armature.pose.bones:
                pbone = armature.pose.bones[bone_name]
                if frame == 30:
                    pbone.scale = (1.0, 1.0, 1.03)  # Slight expansion
                else:
                    pbone.scale = (1.0, 1.0, 1.0)
                pbone.keyframe_insert(data_path="scale", frame=frame)
    
    # Subtle head sway
    head = armature.pose.bones.get('Head')
    if head:
        for frame, rot_z in [(1, 0), (20, 0.03), (40, -0.03), (60, 0)]:
            bpy.context.scene.frame_set(frame)
            head.rotation_euler.z = rot_z
            head.keyframe_insert(data_path="rotation_euler", index=2, frame=frame)
    
    # Set interpolation to linear for smooth loop
    for fcurve in action.fcurves:
        for keyframe in fcurve.keyframe_points:
            keyframe.interpolation = 'LINEAR'
    
    print(f"Created Idle animation ({60} frames)")
    bpy.ops.object.mode_set(mode='OBJECT')


def create_walk_animation():
    """Basic quadruped walk cycle (120 frames)."""
    action = create_action("Walk", 1, 120)
    armature = get_armature()
    
    # Leg pairs: front-left + back-right move together, then front-right + back-left
    leg_pairs = [
        # (front_left, back_right)
        (['LeftArm', 'LeftForeArm', 'LeftHand'],
         ['RightUpLeg', 'RightLeg', 'RightFoot']),
        # (front_right, back_left)
        (['RightArm', 'RightForeArm', 'RightHand'],
         ['LeftUpLeg', 'LeftLeg', 'LeftFoot']),
    ]
    
    for frame in range(1, 121, 15):
        phase = (frame / 120.0) * 2 * math.pi
        
        bpy.context.scene.frame_set(frame)
        
        # Diagonal pairs move in sync
        for pair_idx, (front, back) in enumerate(leg_pairs):
            offset = 0 if pair_idx == 0 else math.pi
            
            # Hip/shoulder rotation
            if front[0] in armature.pose.bones:
                pbone = armature.pose.bones[front[0]]
                pbone.rotation_euler.x = math.sin(phase + offset) * 0.2
                pbone.keyframe_insert(data_path="rotation_euler", index=0, frame=frame)
            
            if back[0] in armature.pose.bones:
                pbone = armature.pose.bones[back[0]]
                pbone.rotation_euler.x = math.sin(phase + offset) * 0.25
                pbone.keyframe_insert(data_path="rotation_euler", index=0, frame=frame)
        
        # Body bob
        hips = armature.pose.bones.get('Hips')
        if hips:
            hips.location.z = abs(math.sin(phase * 2)) * 0.02
            hips.keyframe_insert(data_path="location", index=2, frame=frame)
    
    # Smooth interpolation
    for fcurve in action.fcurves:
        for keyframe in fcurve.keyframe_points:
            keyframe.interpolation = 'BEZIER'
    
    print(f"Created Walk animation ({120} frames)")
    bpy.ops.object.mode_set(mode='OBJECT')


def create_bark_animation():
    """Quick bark — head thrust forward + jaw open (30 frames)."""
    action = create_action("Bark", 1, 30)
    armature = get_armature()
    
    keyframes = [
        # (frame, head_x, jaw_z)
        (1, 0, 0),          # Rest
        (5, -0.05, 0),      # Pull back
        (8, 0.08, -0.3),    # Thrust forward + jaw open
        (10, 0.06, -0.25),  # Hold
        (15, 0.04, -0.2),   # Second bark
        (18, 0.08, -0.3),
        (22, 0.02, -0.1),   # Closing
        (30, 0, 0),         # Return
    ]
    
    for frame, head_x, jaw_z in keyframes:
        bpy.context.scene.frame_set(frame)
        
        head = armature.pose.bones.get('Head')
        if head:
            head.rotation_euler.x = head_x
            head.keyframe_insert(data_path="rotation_euler", index=0, frame=frame)
        
        # Jaw (if exists — Mixamo may not have one)
        jaw = armature.pose.bones.get('Jaw') or armature.pose.bones.get('mixamorig:Jaw')
        if jaw:
            jaw.rotation_euler.z = jaw_z
            jaw.keyframe_insert(data_path="rotation_euler", index=2, frame=frame)
    
    print(f"Created Bark animation ({30} frames)")
    bpy.ops.object.mode_set(mode='OBJECT')


def create_wag_animation():
    """Tail wag — side to side (40 frames, loops)."""
    action = create_action("TailWag", 1, 40)
    armature = get_armature()
    
    # Find tail bones
    tail_bones = [b.name for b in armature.data.bones if 'tail' in b.name.lower() or 'Tail' in b.name]
    
    if not tail_bones:
        # Use spine end as pseudo-tail
        tail_bones = ['Spine2']
        print("No tail bones found, using Spine2 as pseudo-tail")
    
    for frame in range(1, 41, 5):
        phase = (frame / 40.0) * 2 * math.pi
        bpy.context.scene.frame_set(frame)
        
        for i, bone_name in enumerate(tail_bones):
            pbone = armature.pose.bones.get(bone_name)
            if pbone:
                # Each tail segment wags more than the previous
                amplitude = 0.15 * (i + 1)
                pbone.rotation_euler.z = math.sin(phase + i * 0.3) * amplitude
                pbone.rotation_euler.y = math.cos(phase + i * 0.3) * amplitude * 0.3
                pbone.keyframe_insert(data_path="rotation_euler", index=2, frame=frame)
                pbone.keyframe_insert(data_path="rotation_euler", index=1, frame=frame)
    
    for fcurve in action.fcurves:
        for keyframe in fcurve.keyframe_points:
            keyframe.interpolation = 'LINEAR'
    
    print(f"Created TailWag animation ({40} frames)")
    bpy.ops.object.mode_set(mode='OBJECT')


def create_lie_down_animation():
    """Transition to lying down (45 frames)."""
    action = create_action("LieDown", 1, 45)
    armature = get_armature()
    
    keyframes = [
        (1, 0, 0, 0),        # Standing
        (10, -0.3, 0, 0),     # Lower hips
        (20, -0.6, 0.1, 0),   # Fold front legs
        (30, -0.8, 0.15, 0.05),  # Settle down
        (40, -0.9, 0.15, 0.05),  # Almost lying
        (45, -0.9, 0.15, 0.05),  # Lying down
    ]
    
    for frame, hip_y, spine_x, body_z in keyframes:
        bpy.context.scene.frame_set(frame)
        
        hips = armature.pose.bones.get('Hips')
        if hips:
            hips.location.y = hip_y
            hips.location.z = hip_y * 0.3
            hips.keyframe_insert(data_path="location", frame=frame)
        
        spine = armature.pose.bones.get('Spine')
        if spine:
            spine.rotation_euler.x = spine_x
            spine.keyframe_insert(data_path="rotation_euler", index=0, frame=frame)
    
    for fcurve in action.fcurves:
        for keyframe in fcurve.keyframe_points:
            keyframe.interpolation = 'BEZIER'
    
    print(f"Created LieDown animation ({45} frames)")
    bpy.ops.object.mode_set(mode='OBJECT')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 50)
    print("Kai Animation Creator")
    print("=" * 50)
    
    armature = get_armature()
    print(f"Armature: {armature.name}, {len(armature.data.bones)} bones")
    print()
    
    create_idle_animation()
    create_walk_animation()
    create_bark_animation()
    create_wag_animation()
    create_lie_down_animation()
    
    # List all created actions
    print()
    print("Created animations:")
    for action in bpy.data.actions:
        print(f"  - {action.name} ({int(action.frame_range[1])} frames)")
    
    print()
    print("=" * 50)
    print("DONE! Export with prepare_kai_rig_runtime.py")
    print("=" * 50)


if __name__ == "__main__":
    main()
