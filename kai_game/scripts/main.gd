## Main Game Scene
## Spawns Kai, enemies, and manages the level.
extends Node2D

@export var enemy_scene: PackedScene
@export var max_enemies: int = 8
@export var spawn_radius: float = 400.0
@export var spawn_interval: float = 3.0

var spawn_timer: float = 0.0
var kill_count: int = 0

@onready var player: KaiPlayer = $KaiPlayer
@onready var hud: KaiHUD = $KaiHUD


func _ready() -> void:
	randomize()
	player.add_to_group("player")
	player.hp_changed.connect(hud.update_hp)
	player.ability_used.connect(hud.on_ability_used)
	hud.update_hp(player.hp, player.max_hp)


func _process(delta: float) -> void:
	_spawn_enemies(delta)


func _spawn_enemies(delta: float) -> void:
	var current_enemies := get_tree().get_nodes_in_group("enemies").size()
	if current_enemies >= max_enemies:
		return

	spawn_timer -= delta
	if spawn_timer > 0:
		return

	spawn_timer = spawn_interval

	# Spawn at random position away from player
	var angle := randf() * TAU
	var dist := spawn_radius + randf_range(0, 100)
	var spawn_pos := player.global_position + Vector2.from_angle(angle) * dist

	if enemy_scene:
		var enemy := enemy_scene.instantiate() as BugEnemy
		enemy.global_position = spawn_pos
		enemy.tree_exited.connect(_on_enemy_died)
		add_child(enemy)


func _on_enemy_died() -> void:
	kill_count += 1
