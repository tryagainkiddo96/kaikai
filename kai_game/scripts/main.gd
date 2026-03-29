## Main Game — Poplar Bluff
## Kai walks the real streets of Poplar Bluff, MO.
extends Node2D

@export var enemy_scene: PackedScene
@export var max_enemies: int = 6
@export var spawn_radius: float = 300.0
@export var spawn_interval: float = 4.0

var spawn_timer: float = 0.0
var kill_count: int = 0

@onready var camera: Camera2D = $Camera2D
@onready var player: KaiPlayer = $KaiPlayer
@onready var hud: CanvasLayer = $KaiHUD
@onready var map: PoplarBluffMap = $PoplarBluffMap


func _ready() -> void:
	randomize()
	player.add_to_group("player")
	
	# Place Kai on the map
	var spawn_pos := map.get_spawn_position()
	player.global_position = spawn_pos
	
	# Camera follows Kai
	camera.global_position = player.global_position
	
	# Connect HUD
	if hud.has_method("update_hp"):
		player.hp_changed.connect(hud.update_hp)
	if hud.has_method("on_ability_used"):
		player.ability_used.connect(hud.on_ability_used)
	hud.update_hp(player.hp, player.max_hp)
	
	# Location banner
	_show_location_banner("1302 N 10th St — Dog Park District\nPoplar Bluff, MO")


func _process(delta: float) -> void:
	_follow_camera(delta)
	_spawn_enemies(delta)


func _follow_camera(_delta: float) -> void:
	camera.global_position = player.global_position


func _spawn_enemies(delta: float) -> void:
	var current_enemies := get_tree().get_nodes_in_group("enemies").size()
	if current_enemies >= max_enemies:
		return

	spawn_timer -= delta
	if spawn_timer > 0:
		return

	spawn_timer = spawn_interval

	# Spawn at random position away from player, on a street
	var angle := randf() * TAU
	var dist := spawn_radius + randf_range(50, 150)
	var spawn_pos := player.global_position + Vector2.from_angle(angle) * dist

	if enemy_scene:
		var enemy := enemy_scene.instantiate() as BugEnemy
		enemy.global_position = spawn_pos
		enemy.tree_exited.connect(_on_enemy_died)
		add_child(enemy)


func _on_enemy_died() -> void:
	kill_count += 1


func _show_location_banner(text: String) -> void:
	var lbl := Label.new()
	lbl.text = text
	lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	lbl.add_theme_font_size_override("font_size", 18)
	lbl.modulate = Color(1, 0.85, 0.6, 1.0)
	lbl.position = Vector2(0, 30)
	lbl.size = Vector2(1280, 60)
	hud.add_child(lbl)
	
	# Fade out after 3 seconds
	var tween := create_tween()
	tween.tween_interval(3.0)
	tween.tween_property(lbl, "modulate:a", 0.0, 1.5)
	tween.tween_callback(lbl.queue_free)
