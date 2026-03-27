from __future__ import annotations

from pathlib import Path
import math

import bpy


ROOT = Path(r"C:\Users\7nujy6xc\OneDrive\Documents\Playground\kai-ai")
ASSET_DIR = ROOT / "kai_companion" / "assets" / "kai"
REFERENCE_DIR = ASSET_DIR / "reference"
CANONICAL_MODEL_PATH = ASSET_DIR / "kai_textured.glb"
LEGACY_LINEAGE_MODEL_PATH = ASSET_DIR / "modelToUsed.glb"
TEXTURE_PATH = ASSET_DIR / "kai_texture_paint.png"
BLEND_PATH = ASSET_DIR / "kai_texture_workspace.blend"


def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items.keys() else "BLENDER_EEVEE"
    scene.render.engine = engine
    if hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = 32
        if hasattr(scene.eevee, "use_raytracing"):
            scene.eevee.use_raytracing = True
    if hasattr(scene.view_settings, "look"):
        scene.view_settings.look = "AgX - Medium High Contrast"
    if scene.world is None:
        scene.world = bpy.data.worlds.new("KaiWorld")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.03, 0.03, 0.035, 1.0)
    bg.inputs[1].default_value = 0.4


def resolve_model_path() -> Path | None:
    if CANONICAL_MODEL_PATH.exists():
        return CANONICAL_MODEL_PATH
    if LEGACY_LINEAGE_MODEL_PATH.exists():
        print("Canonical kai_textured.glb not found; falling back to legacy lineage modelToUsed.glb")
        return LEGACY_LINEAGE_MODEL_PATH
    return None


def ensure_texture_image() -> bpy.types.Image | None:
    if TEXTURE_PATH.exists():
        return bpy.data.images.load(str(TEXTURE_PATH), check_existing=True)
    print("kai_texture_paint.png is missing; preserving imported materials instead of creating a placeholder coat.")
    return None


def import_model() -> bpy.types.Object | None:
    model_path = resolve_model_path()
    if model_path is None:
        return None
    bpy.ops.import_scene.gltf(filepath=str(model_path))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not meshes:
        return None
    model = meshes[0]
    bpy.context.view_layer.objects.active = model
    bpy.ops.object.shade_smooth()
    model.rotation_euler = (math.radians(90), 0.0, math.radians(180))
    model.scale = (1.35, 1.35, 1.35)
    return model


def assign_material(model: bpy.types.Object, image: bpy.types.Image | None) -> None:
    if image is None:
        return
    material = bpy.data.materials.new(name="KaiPaintMaterial")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    for node in list(nodes):
        nodes.remove(node)

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (500, 0)

    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.location = (180, 0)
    principled.inputs["Roughness"].default_value = 0.9
    principled.inputs["Sheen Weight"].default_value = 0.15
    principled.inputs["Coat Weight"].default_value = 0.08

    image_node = nodes.new("ShaderNodeTexImage")
    image_node.location = (-220, 0)
    image_node.image = image
    image_node.interpolation = "Smart"

    links.new(image_node.outputs["Color"], principled.inputs["Base Color"])
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])

    model.data.materials.clear()
    model.data.materials.append(material)


def create_camera_and_lights() -> None:
    bpy.ops.object.camera_add(location=(0.0, -4.5, 0.55), rotation=(math.radians(82), 0.0, 0.0))
    camera = bpy.context.active_object
    camera.data.lens = 58
    bpy.context.scene.camera = camera

    bpy.ops.object.light_add(type="SUN", location=(0.0, 0.0, 4.0))
    sun = bpy.context.active_object
    sun.rotation_euler = (math.radians(35), math.radians(0), math.radians(25))
    sun.data.energy = 2.5

    bpy.ops.object.light_add(type="AREA", location=(2.4, -1.8, 1.6))
    fill = bpy.context.active_object
    fill.rotation_euler = (math.radians(65), 0.0, math.radians(55))
    fill.data.energy = 2200
    fill.data.shape = "RECTANGLE"
    fill.data.size = 3.6
    fill.data.size_y = 2.2

    bpy.ops.object.light_add(type="AREA", location=(-2.2, 1.2, 1.7))
    rim = bpy.context.active_object
    rim.rotation_euler = (math.radians(110), 0.0, math.radians(-70))
    rim.data.energy = 950
    rim.data.color = (0.78, 0.86, 1.0)
    rim.data.shape = "RECTANGLE"
    rim.data.size = 2.0
    rim.data.size_y = 2.0


def create_reference_board(name: str, image_path: Path, location: tuple[float, float, float], rotation_z: float) -> None:
    if not image_path.exists():
        return
    bpy.ops.mesh.primitive_plane_add(location=location, rotation=(math.radians(90), 0.0, math.radians(rotation_z)))
    plane = bpy.context.active_object
    plane.name = name
    plane.scale = (1.4, 1.0, 1.0)

    material = bpy.data.materials.new(name=f"{name}Mat")
    material.use_nodes = True
    material.blend_method = "BLEND"
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    for node in list(nodes):
        nodes.remove(node)

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (380, 0)

    emission = nodes.new("ShaderNodeEmission")
    emission.location = (120, 40)
    emission.inputs["Strength"].default_value = 1.0

    image_node = nodes.new("ShaderNodeTexImage")
    image_node.location = (-180, 40)
    image_node.image = bpy.data.images.load(str(image_path), check_existing=True)

    transparent = nodes.new("ShaderNodeBsdfTransparent")
    transparent.location = (120, -120)

    mix = nodes.new("ShaderNodeMixShader")
    mix.location = (250, 0)

    alpha = nodes.new("ShaderNodeMath")
    alpha.location = (-10, -120)
    alpha.operation = "GREATER_THAN"
    alpha.inputs[1].default_value = 0.02

    links.new(image_node.outputs["Color"], emission.inputs["Color"])
    links.new(image_node.outputs["Alpha"], alpha.inputs[0])
    links.new(alpha.outputs["Value"], mix.inputs["Fac"])
    links.new(transparent.outputs["BSDF"], mix.inputs[1])
    links.new(emission.outputs["Emission"], mix.inputs[2])
    links.new(mix.outputs["Shader"], output.inputs["Surface"])

    plane.data.materials.append(material)


def create_reference_rig() -> None:
    create_reference_board(
        "FrontRef",
        REFERENCE_DIR / "kai_standing.jpg",
        (0.0, 2.2, 0.5),
        180.0,
    )
    create_reference_board(
        "LoungingRef",
        REFERENCE_DIR / "kai_lounging_1.jpg",
        (-2.45, 0.0, 0.7),
        90.0,
    )
    create_reference_board(
        "TwoDogsRef",
        REFERENCE_DIR / "kai_two_dogs_left.jpg",
        (2.45, 0.0, 0.7),
        -90.0,
    )
    create_reference_board(
        "ViewerRef",
        REFERENCE_DIR / "model_reference_contact_sheet.jpg",
        (0.0, -2.65, 0.9),
        0.0,
    )


def save_scene() -> None:
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))


def main() -> None:
    reset_scene()
    image = ensure_texture_image()
    model = import_model()
    if model is not None:
        assign_material(model, image)
    create_camera_and_lights()
    create_reference_rig()
    save_scene()
    print(f"Saved Blender workspace to: {BLEND_PATH}")


if __name__ == "__main__":
    main()
