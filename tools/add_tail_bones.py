"""
Add Tail Bones to Kai Rig (Blender)
Adds a 3-segment tail chain to the Mixamo rig so TailWag works.

Usage:
  1. Open the rigged Kai model in Blender
  2. Run this script
  3. Re-run create_kai_animations.py to update TailWag
  4. Re-export GLB

The tail connects to the Hips bone and extends backward.
"""

import bpy
from mathutils import Vector


def add_tail_bones():
    """Add tail bone chain to the armature."""
    
    # Get armature
    armature = None
    for obj in bpy.context.scene.objects:
        if obj.type == 'ARMATURE':
            armature = obj
            break
    
    if not armature:
        print("ERROR: No armature found")
        return
    
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='EDIT')
    
    edit_bones = armature.data.edit_bones
    
    # Check if tail already exists
    if 'Tail1' in edit_bones:
        print("Tail bones already exist, skipping")
        bpy.ops.object.mode_set(mode='OBJECT')
        return
    
    # Find the hips bone to attach tail to
    hips = edit_bones.get('Hips') or edit_bones.get('mixamorig:Hips')
    if not hips:
        print("ERROR: No Hips bone found")
        bpy.ops.object.mode_set(mode='OBJECT')
        return
    
    print(f"Attaching tail to: {hips.name}")
    
    # Tail segments (3 bones)
    # Shiba tail curls up and backward
    tail_segments = [
        {
            'name': 'Tail1',
            'head': hips.tail + Vector((0, -0.05, 0.1)),  # Behind hips, slightly up
            'tail': hips.tail + Vector((0, -0.12, 0.2)),   # Extends back and up
        },
        {
            'name': 'Tail2',
            'head': hips.tail + Vector((0, -0.12, 0.2)),
            'tail': hips.tail + Vector((0, -0.15, 0.3)),   # Curves up
        },
        {
            'name': 'Tail3',
            'head': hips.tail + Vector((0, -0.15, 0.3)),
            'tail': hips.tail + Vector((0, -0.12, 0.38)),  # Tip curls slightly forward (Shiba curl!)
        },
    ]
    
    parent = hips
    for seg in tail_segments:
        bone = edit_bones.new(seg['name'])
        bone.head = seg['head']
        bone.tail = seg['tail']
        bone.parent = parent
        bone.use_connect = (parent != hips)  # Connect to previous tail bone
        parent = bone
    
    print(f"Added {len(tail_segments)} tail bones")
    
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Verify
    print("\nTail bone chain:")
    for name in ['Tail1', 'Tail2', 'Tail3']:
        if name in armature.data.bones:
            bone = armature.data.bones[name]
            print(f"  {name}: head={bone.head_local}, tail={bone.tail_local}")
    
    return True


def add_tail_to_pose_bones():
    """Add custom shapes to tail pose bones for easier animation."""
    armature = None
    for obj in bpy.context.scene.objects:
        if obj.type == 'ARMATURE':
            armature = obj
            break
    
    if not armature:
        return
    
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')
    
    for name in ['Tail1', 'Tail2', 'Tail3']:
        if name in armature.pose.bones:
            pbone = armature.pose.bones[name]
            # Set rotation limits for natural tail movement
            pbone.lock_scale = [True, True, True]  # Don't scale tail
            pbone.lock_location = [True, True, True]  # Don't move tail (rotate only)
    
    bpy.ops.object.mode_set(mode='OBJECT')
    print("Pose bone limits set for tail")


def main():
    print("=" * 40)
    print("Adding Tail Bones to Kai Rig")
    print("=" * 40)
    
    add_tail_bones()
    add_tail_to_pose_bones()
    
    print()
    print("DONE! Re-run create_kai_animations.py to update TailWag.")
    print("Then re-export GLB for Godot.")


if __name__ == "__main__":
    main()
