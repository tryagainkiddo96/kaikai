## Base Bug Enemy
## Wanders, chases Kai on detection, bites on contact.
extends CharacterBody2D
class_name BugEnemy

@export var speed: float = 60.0
@export var chase_speed: float = 90.0
@export var hp: int = 20
@export var damage: int = 5
@export var detection_range: float = 120.0
@export var attack_range: float = 24.0
@export var attack_cooldown: float = 1.0

enum State { WANDER, CHASE, ATTACK, STUNNED, DEAD }
var state: State = State.WANDER

var wander_dir: Vector2 = Vector2.ZERO
var wander_timer: float = 0.0
var attack_timer: float = 0.0
var stun_timer: float = 0.0
var target: Node2D = null


func _ready() -> void:
	add_to_group("enemies")
	_pick_wander_dir()


func _physics_process(delta: float) -> void:
	if state == State.DEAD:
		return

	_tick_timers(delta)
	_find_target()
	_update_behavior(delta)
	move_and_slide()


func _tick_timers(delta: float) -> void:
	attack_timer = maxf(attack_timer - delta, 0.0)
	stun_timer = maxf(stun_timer - delta, 0.0)
	wander_timer -= delta
	if stun_timer <= 0 and state == State.STUNNED:
		state = State.WANDER


func _find_target() -> void:
	if target == null:
		var players := get_tree().get_nodes_in_group("player")
		if players.size() > 0:
			target = players[0]


func _update_behavior(delta: float) -> void:
	match state:
		State.WANDER:
			_wander(delta)
		State.CHASE:
			_chase(delta)
		State.ATTACK:
			_attack(delta)
		State.STUNNED:
			velocity = Vector2.ZERO


func _wander(_delta: float) -> void:
	if wander_timer <= 0:
		_pick_wander_dir()

	velocity = wander_dir * speed

	# Switch to chase if target in range
	if target and global_position.distance_to(target.global_position) < detection_range:
		state = State.CHASE


func _chase(_delta: float) -> void:
	if target == null or not is_instance_valid(target):
		state = State.WANDER
		return

	var dist := global_position.distance_to(target.global_position)

	if dist > detection_range * 1.5:
		state = State.WANDER
		return

	if dist < attack_range:
		state = State.ATTACK
		return

	var dir := (target.global_position - global_position).normalized()
	velocity = dir * chase_speed


func _attack(_delta: float) -> void:
	velocity = Vector2.ZERO

	if attack_timer > 0:
		return

	if target and is_instance_valid(target):
		var dist := global_position.distance_to(target.global_position)
		if dist < attack_range:
			if target.has_method("take_damage"):
				target.take_damage(damage)
			attack_timer = attack_cooldown
		else:
			state = State.CHASE
	else:
		state = State.WANDER


func _pick_wander_dir() -> void:
	wander_dir = Vector2(randf_range(-1, 1), randf_range(-1, 1)).normalized()
	wander_timer = randf_range(1.0, 3.0)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

func take_damage(amount: int) -> void:
	if state == State.DEAD:
		return
	hp -= amount
	_flash_hit()
	if hp <= 0:
		_die()


func stun(duration: float) -> void:
	if state == State.DEAD:
		return
	state = State.STUNNED
	stun_timer = duration
	velocity = Vector2.ZERO


func _flash_hit() -> void:
	var tween := create_tween()
	tween.tween_property(self, "modulate", Color.RED, 0.05)
	tween.tween_property(self, "modulate", Color.WHITE, 0.1)


func _die() -> void:
	state = State.DEAD
	velocity = Vector2.ZERO
	# Shrink and disappear
	var tween := create_tween()
	tween.tween_property(self, "scale", Vector2.ZERO, 0.3)
	tween.tween_callback(queue_free)
