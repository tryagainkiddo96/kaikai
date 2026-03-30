from __future__ import annotations

from pathlib import Path
import re

import bpy


ROOT = Path(r"C:\Users\7nujy6xc\OneDrive\Documents\Playground\kai-ai")
ASSET_DIR = ROOT / "kai_companion" / "assets" / "kai"
RIGGED_SOURCE_PATH = ASSET_DIR / "kai_mixamo_rigged_source.fbx"
BAKED_ALBEDO_PATH = ASSET_DIR / "kai_baked_albedo.png"
PAINT_TEXTURE_PATH = ASSET_DIR / "kai_texture_paint.png"
PHOTO_TEXTURE_PATH = ASSET_DIR / "kai_photo_clean.png"
OUTPUT_PATH = ASSET_DIR / "kai_textured_rigged.glb"


def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_rigged_source() -> None:
    if not RIGGED_SOURCE_PATH.exists():
        raise FileNotFoundError(
            f"Missing Mixamo source: {RIGGED_SOURCE_PATH}\n"
            "Save the downloaded Mixamo FBX in kai_companion/assets/kai/ before running this script."
        )
    bpy.ops.import_scene.fbx(filepath=str(RIGGED_SOURCE_PATH), automatic_bone_orientation=True)


def find_primary_armature() -> bpy.types.Object:
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    if not armatures:
        raise RuntimeError("No armature was imported from the Mixamo FBX.")
    return max(armatures, key=lambda obj: len(obj.data.bones))


def find_meshes() -> list[bpy.types.Object]:
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not meshes:
        raise RuntimeError("No mesh objects were imported from the Mixamo FBX.")
    return meshes


def clean_name(name: str) -> str:
    name = name.replace("mixamorig:", "")
    name = name.replace("mixamorig_", "")
    name = re.sub(r"[^A-Za-z0-9_]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "Bone"


def clean_bone_names(armature: bpy.types.Object, meshes: list[bpy.types.Object]) -> None:
    rename_map: dict[str, str] = {}
    used_names: set[str] = set()
    for bone in armature.data.bones:
        new_name = clean_name(bone.name)
        base_name = new_name
        suffix = 1
        while new_name in used_names:
            suffix += 1
            new_name = f"{base_name}_{suffix}"
        used_names.add(new_name)
        rename_map[bone.name] = new_name

    for bone in armature.data.bones:
        old_name = bone.name
        bone.name = rename_map[old_name]

    for mesh in meshes:
        for group in mesh.vertex_groups:
            if group.name in rename_map:
                group.name = rename_map[group.name]


def validate_bones(armature: bpy.types.Object) -> None:
    bone_names = [bone.name.lower() for bone in armature.data.bones]
    if len(bone_names) < 12:
        raise RuntimeError(
            f"Mixamo armature looks incomplete: only found {len(bone_names)} bones."
        )

    recommended_groups = {
        "root_or_hips": ("hip", "pelvis", "root"),
        "spine": ("spine",),
        "head": ("head", "neck"),
        "front_leg_left": ("leftarm", "leftshoulder", "leftfore"),
        "front_leg_right": ("rightarm", "rightshoulder", "rightfore"),
        "hind_leg_left": ("leftupleg", "leftleg", "leftfoot"),
        "hind_leg_right": ("rightupleg", "rightleg", "rightfoot"),
    }
    missing = [
        label
        for label, tokens in recommended_groups.items()
        if not any(token in bone_name for token in tokens for bone_name in bone_names)
    ]
    if missing:
        print(f"Warning: some expected rig groups were not found: {', '.join(missing)}")


def choose_texture_path() -> Path:
    for candidate in (BAKED_ALBEDO_PATH, PAINT_TEXTURE_PATH, PHOTO_TEXTURE_PATH):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"No Kai texture found. Expected one of: {BAKED_ALBEDO_PATH.name}, "
        f"{PAINT_TEXTURE_PATH.name}, {PHOTO_TEXTURE_PATH.name}"
    )


def apply_texture(meshes: list[bpy.types.Object], armature: bpy.types.Object) -> None:
    image = bpy.data.images.load(str(choose_texture_path()), check_existing=True)
    image.file_format = "PNG"

    material = bpy.data.materials.get("KaiRiggedMaterial")
    if material is None:
        material = bpy.data.materials.new(name="KaiRiggedMaterial")
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
        modifier = next((mod for mod in mesh.modifiers if mod.type == "ARMATURE"), None)
        if modifier is None:
            modifier = mesh.modifiers.new(name="KaiArmature", type="ARMATURE")
        modifier.object = armature


def normalize_scene_objects(armature: bpy.types.Object, meshes: list[bpy.types.Object]) -> None:
    armature.name = "KaiArmature"
    armature.data.name = "KaiArmatureData"
    for index, mesh in enumerate(meshes, start=1):
        mesh.name = "KaiMesh" if index == 1 else f"KaiMesh_{index}"


def export_rigged_glb() -> None:
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
    import_rigged_source()
    armature = find_primary_armature()
    meshes = find_meshes()
    clean_bone_names(armature, meshes)
    validate_bones(armature)
    normalize_scene_objects(armature, meshes)
    apply_texture(meshes, armature)
    export_rigged_glb()
    print(f"Rigged Kai GLB exported to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
