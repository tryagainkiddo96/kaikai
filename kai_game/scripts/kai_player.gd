## Kai — Player Controller
## Top-down movement, attack, bark, sniff, and heal.
extends CharacterBody2D
class_name KaiPlayer

# -- Movement --
@export var speed: float = 200.0
@export var dash_speed: float = 400.0
@export var dash_duration: float = 0.15

# -- Combat --
@export var attack_damage: int = 10
@export var attack_range: float = 40.0
@export var attack_cooldown: float = 0.4

# -- Abilities --
@export var bark_radius: float = 150.0
@export var bark_stun_duration: float = 1.0
@export var bark_cooldown: float = 3.0
@export var sniff_radius: float = 200.0
@export var sniff_cooldown: float = 2.0
@export var heal_amount: int = 20
@export var heal_cooldown: float = 8.0

# -- Stats --
@export var max_hp: int = 100
var hp: int
var is_dashing: bool = false
var is_healing: bool = false
var facing: Vector2 = Vector2.DOWN

# -- Cooldown timers --
var attack_timer: float = 0.0
var bark_timer: float = 0.0
var sniff_timer: float = 0.0
var heal_timer: float = 0.0
var dash_timer: float = 0.0

# -- State --
enum State { IDLE, WALKING, ATTACKING, BARKING, SNIFFING, HEALING, DASHING, HURT }
var state: State = State.IDLE

signal hp_changed(new_hp: int, max_hp: int)
signal ability_used(ability_name: String)
signal enemy_hit(damage: int)


func _ready() -> void:
	hp = max_hp
	hp_changed.emit(hp, max_hp)


func _physics_process(delta: float) -> void:
	_tick_cooldowns(delta)
	_handle_input()
	_apply_movement(delta)
	_update_state()
	move_and_slide()


func _tick_cooldowns(delta: float) -> void:
	attack_timer = maxf(attack_timer - delta, 0.0)
	bark_timer = maxf(bark_timer - delta, 0.0)
	sniff_timer = maxf(sniff_timer - delta, 0.0)
	heal_timer = maxf(heal_timer - delta, 0.0)
	if dash_timer > 0:
		dash_timer -= delta
		if dash_timer <= 0:
			is_dashing = false


func _handle_input() -> void:
	# Abilities (can interrupt idle/walk)
	if state in [State.IDLE, State.WALKING]:
		if Input.is_action_just_pressed("attack") and attack_timer <= 0:
			_do_attack()
		elif Input.is_action_just_pressed("bark") and bark_timer <= 0:
			_do_bark()
		elif Input.is_action_just_pressed("sniff") and sniff_timer <= 0:
			_do_sniff()
		elif Input.is_action_just_pressed("heal") and heal_timer <= 0:
			_do_heal()


func _apply_movement(_delta: float) -> void:
	if state in [State.ATTACKING, State.BARKING, State.SNIFFING, State.HEALING, State.HURT]:
		velocity = Vector2.ZERO
		return

	var input_dir := Vector2.ZERO
	input_dir.x = Input.get_axis("move_left", "move_right")
	input_dir.y = Input.get_axis("move_up", "move_down")

	if input_dir.length() > 0.1:
		facing = input_dir.normalized()
		input_dir = input_dir.normalized()
		velocity = input_dir * (dash_speed if is_dashing else speed)
		state = State.WALKING if not is_dashing else State.DASHING
	else:
		velocity = Vector2.ZERO
		if state == State.WALKING or state == State.DASHING:
			state = State.IDLE


func _update_state() -> void:
	# Animations would go here — for now just update the label
	pass


# ---------------------------------------------------------------------------
# Abilities
# ---------------------------------------------------------------------------

func _do_attack() -> void:
	state = State.ATTACKING
	attack_timer = attack_cooldown
	ability_used.emit("paw_swipe")

	# Find enemies in attack range
	var space := get_world_2d().direct_space_state
	var query := PhysicsShapeQueryParameters2D.new()
	var circle := CircleShape2D.new()
	circle.radius = attack_range
	query.shape = circle
	query.transform = Transform2D(0, global_position + facing * attack_range * 0.5)
	query.collision_mask = 2  # Enemies layer

	var results := space.intersect_shape(query)
	for hit in results:
		var collider = hit["collider"]
		if collider.has_method("take_damage"):
			collider.take_damage(attack_damage)
			enemy_hit.emit(attack_damage)

	await get_tree().create_timer(0.2).timeout
	if state == State.ATTACKING:
		state = State.IDLE


func _do_bark() -> void:
	state = State.BARKING
	bark_timer = bark_cooldown
	ability_used.emit("bark_signal")

	# Stun enemies in radius
	for body in _get_enemies_in_radius(bark_radius):
		if body.has_method("stun"):
			body.stun(bark_stun_duration)

	# Visual feedback
	_spawn_bark_effect()

	await get_tree().create_timer(0.3).timeout
	if state == State.BARKING:
		state = State.IDLE


func _do_sniff() -> void:
	state = State.SNIFFING
	sniff_timer = sniff_cooldown
	ability_used.emit("sniff_out")

	# Reveal hidden items / secrets in radius
	for body in _get_bodies_in_radius(sniff_radius):
		if body.has_method("reveal"):
			body.reveal()

	await get_tree().create_timer(0.5).timeout
	if state == State.SNIFFING:
		state = State.IDLE


func _do_heal() -> void:
	state = State.HEALING
	heal_timer = heal_cooldown
	ability_used.emit("paw_shield")
	is_healing = true

	# Heal over 1 second
	var heal_steps := 4
	var heal_per_step := heal_amount / heal_steps
	for i in heal_steps:
		hp = mini(hp + heal_per_step, max_hp)
		hp_changed.emit(hp, max_hp)
		await get_tree().create_timer(0.25).timeout

	is_healing = false
	if state == State.HEALING:
		state = State.IDLE


# ---------------------------------------------------------------------------
# Damage
# ---------------------------------------------------------------------------

func take_damage(amount: int) -> void:
	if is_healing:
		return  # Paw Shield absorbs one hit
	hp = maxi(hp - amount, 0)
	hp_changed.emit(hp, max_hp)
	state = State.HURT
	velocity = Vector2.ZERO

	if hp <= 0:
		_die()
		return

	await get_tree().create_timer(0.3).timeout
	if state == State.HURT:
		state = State.IDLE


func _die() -> void:
	# Death sequence — for now just reset HP
	hp = max_hp
	hp_changed.emit(hp, max_hp)
	state = State.IDLE
	global_position = Vector2(640, 360)  # Reset to center


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

func _get_enemies_in_radius(radius: float) -> Array:
	var enemies: Array = []
	for body in get_tree().get_nodes_in_group("enemies"):
		if global_position.distance_to(body.global_position) <= radius:
			enemies.append(body)
	return enemies


func _get_bodies_in_radius(radius: float) -> Array:
	var bodies: Array = []
	for body in get_tree().get_nodes_in_group("interactables"):
		if global_position.distance_to(body.global_position) <= radius:
			bodies.append(body)
	return bodies


func _spawn_bark_effect() -> void:
	# Simple visual — expanding circle
	var circle := Sprite2D.new()
	var img := Image.create(64, 64, false, Image.FORMAT_RGBA8)
	for x in 64:
		for y in 64:
			var dist := Vector2(x - 32, y - 32).length()
			if abs(dist - 28) < 3:
				img.set_pixel(x, y, Color(1.0, 0.75, 0.4, 0.8))
			else:
				img.set_pixel(x, y, Color.TRANSPARENT)
	var tex := ImageTexture.create_from_image(img)
	circle.texture = tex
	circle.global_position = global_position
	circle.scale = Vector2.ZERO
	get_parent().add_child(circle)

	var tween := create_tween()
	tween.tween_property(circle, "scale", Vector2(bark_radius / 32, bark_radius / 32), 0.3)
	tween.parallel().tween_property(circle, "modulate:a", 0.0, 0.3)
	tween.tween_callback(circle.queue_free)
