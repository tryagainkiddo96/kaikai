## Kai — Player Controller
## Top-down movement, spy abilities, stealth mechanics.
extends CharacterBody2D
class_name KaiPlayer

# -- Movement --
@export var speed: float = 200.0
@export var sneak_speed: float = 100.0
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
var is_sneaking: bool = false
var facing: Vector2 = Vector2.DOWN

# -- Spy state --
var stealth_modifier: float = 1.0
var social_stealth: bool = false
var invulnerable: bool = false

# -- Cooldown timers --
var attack_timer: float = 0.0
var bark_timer: float = 0.0
var sniff_timer: float = 0.0
var heal_timer: float = 0.0
var dash_timer: float = 0.0

# -- State --
enum State { IDLE, WALKING, SNEAKING, ATTACKING, BARKING, SNIFFING, HEALING, DASHING, HURT, GHOST }
var state: State = State.IDLE

# -- Spy abilities system --
var spy_abilities: KaiAbilities

signal hp_changed(new_hp: int, max_hp: int)
signal ability_used(ability_name: String)
signal enemy_hit(damage: int)


func _ready() -> void:
	hp = max_hp
	add_to_group("player")
	hp_changed.emit(hp, max_hp)
	
	# Initialize spy abilities
	spy_abilities = KaiAbilities.new(self)
	spy_abilities.ability_activated.connect(_on_spy_ability_activated)
	spy_abilities.ability_ended.connect(_on_spy_ability_ended)
	add_child(spy_abilities)


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
	# Sneak toggle (hold shift)
	is_sneaking = Input.is_action_pressed("sneak") if InputMap.has_action("sneak") else false
	
	# Spy abilities (number keys 1-7 + ultimate)
	if spy_abilities:
		if Input.is_action_just_pressed("spy_1"):
			spy_abilities.activate("silent_paws")
		elif Input.is_action_just_pressed("spy_2"):
			spy_abilities.activate("shadow_fur")
		elif Input.is_action_just_pressed("spy_3"):
			spy_abilities.activate("good_boy_face")
		elif Input.is_action_just_pressed("spy_4"):
			spy_abilities.activate("deep_sniff")
		elif Input.is_action_just_pressed("spy_5"):
			spy_abilities.activate("smoke_roll")
		elif Input.is_action_just_pressed("spy_6"):
			spy_abilities.activate("paw_cloner")
		elif Input.is_action_just_pressed("spy_7"):
			spy_abilities.activate("bone_decoy")
		elif Input.is_action_just_pressed("spy_ultimate"):
			spy_abilities.activate("fox_walk")

	# Combat abilities (can interrupt idle/walk)
	if state in [State.IDLE, State.WALKING, State.SNEAKING]:
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
		
		var move_speed := speed
		if is_sneaking:
			move_speed = sneak_speed
		elif is_dashing:
			move_speed = dash_speed
		
		# Fox walk = ghost speed
		if spy_abilities and spy_abilities.is_active("fox_walk"):
			move_speed = speed * 1.2
		
		velocity = input_dir * move_speed
		
		if is_sneaking and not is_dashing:
			state = State.SNEAKING
		elif not is_dashing:
			state = State.WALKING
		else:
			state = State.DASHING
	else:
		velocity = Vector2.ZERO
		if state in [State.WALKING, State.DASHING, State.SNEAKING]:
			state = State.IDLE


func _update_state() -> void:
	pass


# ---------------------------------------------------------------------------
# Spy ability callbacks
# ---------------------------------------------------------------------------

func _on_spy_ability_activated(ability_name: String) -> void:
	match ability_name:
		"shadow_fur":
			state = State.GHOST
		"fox_walk":
			state = State.GHOST
	ability_used.emit(ability_name)


func _on_spy_ability_ended(ability_name: String) -> void:
	if state == State.GHOST:
		state = State.IDLE


# ---------------------------------------------------------------------------
# Spy state setters (called by KaiAbilities)
# ---------------------------------------------------------------------------

func set_stealth_modifier(value: float) -> void:
	stealth_modifier = value

func set_social_stealth(value: bool) -> void:
	social_stealth = value

func set_invulnerable(value: bool) -> void:
	invulnerable = value


# ---------------------------------------------------------------------------
# Combat abilities (same as before)
# ---------------------------------------------------------------------------

func _do_attack() -> void:
	state = State.ATTACKING
	attack_timer = attack_cooldown
	ability_used.emit("paw_swipe")

	var space := get_world_2d().direct_space_state
	var query := PhysicsShapeQueryParameters2D.new()
	var circle := CircleShape2D.new()
	circle.radius = attack_range
	query.shape = circle
	query.transform = Transform2D(0, global_position + facing * attack_range * 0.5)
	query.collision_mask = 2

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

	for body in _get_enemies_in_radius(bark_radius):
		if body.has_method("stun"):
			body.stun(bark_stun_duration)
	_spawn_bark_effect()

	await get_tree().create_timer(0.3).timeout
	if state == State.BARKING:
		state = State.IDLE


func _do_sniff() -> void:
	state = State.SNIFFING
	sniff_timer = sniff_cooldown
	ability_used.emit("sniff_out")

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
	if invulnerable:
		return
	if is_healing:
		return
	# Good Boy Face — enemies "pet" instead of attack
	if social_stealth:
		return
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
	hp = max_hp
	hp_changed.emit(hp, max_hp)
	state = State.IDLE
	global_position = Vector2(0, 0)


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
