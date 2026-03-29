extends Area3D

@export var dog_name := "Yuki"
@export var message := "Woof!"
@export var tint_color := Color(0.95, 0.6, 0.25)

@onready var model_root: Node = $Model

func _ready() -> void:
	add_to_group("npc")
	_try_use_textured_model()
	_apply_tint()

func talk(_player: Node = null) -> String:
	return "%s: %s" % [dog_name, message]

func get_prompt(_player: Node = null) -> String:
	return "Press F: Talk to %s" % dog_name

func _apply_tint() -> void:
	if model_root == null:
		return
	_apply_to_meshes(model_root, tint_color)

func _apply_to_meshes(node: Node, tint: Color) -> void:
	if node is MeshInstance3D:
		var mesh_node := node as MeshInstance3D
		var mat := StandardMaterial3D.new()
		mat.albedo_color = tint
		mat.roughness = 0.58
		mesh_node.set_surface_override_material(0, mat)
	for child in node.get_children():
		_apply_to_meshes(child, tint)

func _try_use_textured_model() -> void:
	if not ResourceLoader.exists("res://assets/kai/kai_textured.glb"):
		return
	var textured := load("res://assets/kai/kai_textured.glb")
	if textured == null:
		return
	if textured is PackedScene:
		var replacement: Node = textured.instantiate()
		if replacement == null:
			return
		var parent := model_root.get_parent()
		parent.remove_child(model_root)
		model_root.queue_free()
		parent.add_child(replacement)
		replacement.name = "Model"
		replacement.position = Vector3(0, 0.05, 0)
		replacement.scale = Vector3(0.9, 0.9, 0.9)
		model_root = replacement
