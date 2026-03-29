extends CharacterBody3D

signal barked
signal collected_treats(total: int)
signal interacted
signal sniff_toggled(enabled: bool)
signal zoomies_started(duration: float)

@export var walk_speed := 4.8
@export var sprint_speed := 7.2
@export var acceleration := 14.0
@export var jump_velocity := 6.2
@export var gravity := 18.0
@export var coyote_time := 0.12
@export var jump_buffer := 0.16
@export var zoomies_speed_bonus := 2.8
@export var zoomies_duration := 2.2
@export var zoomies_chance := 0.34
@export var zoomies_cooldown := 8.0

var treats := 0
var inventory: Array[String] = []
var cosmetic_harness := "red"
var sniff_mode := false
var _last_move_dir := Vector3.FORWARD
var _anim_player: AnimationPlayer = null
var _idle_anim := ""
var _move_anim := ""
var _coyote_timer := 0.0
var _jump_buffer_timer := 0.0
var _zoomies_timer := 0.0
var _zoomies_cooldown_timer := 0.0

@onready var pivot: Node3D = $Pivot
@onready var model_root: Node = $Pivot/Model
@onready var camera: Camera3D = $Pivot/SpringArm3D/Camera3D

func _ready() -> void:
	randomize()
	_try_use_textured_model()
	_anim_player = model_root.find_child("AnimationPlayer", true, false)
	if _anim_player != null:
		_idle_anim = _pick_anim(["Idle", "idle", "Idle_0", "idle_0"])
		_move_anim = _pick_anim(["Trot", "Walk", "Run", "walk", "run"])
		if _idle_anim != "":
			_anim_player.play(_idle_anim)

func _physics_process(delta: float) -> void:
	_update_jump_timers(delta)
	_update_zoomies_timers(delta)
	_process_movement(delta)
	_process_actions()
	_update_animation()
	move_and_slide()

func _update_jump_timers(delta: float) -> void:
	if is_on_floor():
		_coyote_timer = coyote_time
	else:
		_coyote_timer = max(0.0, _coyote_timer - delta)
	_jump_buffer_timer = max(0.0, _jump_buffer_timer - delta)

func _process_movement(delta: float) -> void:
	if not is_on_floor():
		velocity.y -= gravity * delta
	else:
		velocity.y = 0.0

	# Use camera-relative controls so forward always means "toward camera look direction".
	var input_vec := Input.get_vector("move_left", "move_right", "move_backward", "move_forward")
	var cam_forward := Vector3.FORWARD
	var cam_right := Vector3.RIGHT
	if camera != null:
		cam_forward = -camera.global_transform.basis.z
		cam_right = camera.global_transform.basis.x
	cam_forward.y = 0.0
	cam_right.y = 0.0
	cam_forward = cam_forward.normalized()
	cam_right = cam_right.normalized()
	var direction := (cam_right * input_vec.x) + (cam_forward * input_vec.y)
	if direction.length() > 0.01:
		direction = direction.normalized()
		_last_move_dir = direction
		var target_yaw := atan2(direction.x, direction.z)
		pivot.rotation.y = lerp_angle(pivot.rotation.y, target_yaw, 10.0 * delta)

	var speed := walk_speed
	if Input.is_action_pressed("sprint"):
		speed = sprint_speed
	if _zoomies_timer > 0.0:
		speed += zoomies_speed_bonus

	var target_velocity := direction * speed
	velocity.x = move_toward(velocity.x, target_velocity.x, acceleration * delta)
	velocity.z = move_toward(velocity.z, target_velocity.z, acceleration * delta)

	if _jump_buffer_timer > 0.0 and _coyote_timer > 0.0:
		velocity.y = jump_velocity
		_jump_buffer_timer = 0.0
		_coyote_timer = 0.0

func _process_actions() -> void:
	if Input.is_action_just_pressed("bark"):
		barked.emit()
		if _zoomies_cooldown_timer <= 0.0 and randf() < zoomies_chance:
			_zoomies_timer = zoomies_duration
			_zoomies_cooldown_timer = zoomies_cooldown
			zoomies_started.emit(zoomies_duration)
	if Input.is_action_just_pressed("jump"):
		_jump_buffer_timer = jump_buffer
	if Input.is_action_just_pressed("sniff"):
		sniff_mode = !sniff_mode
		sniff_toggled.emit(sniff_mode)
	if Input.is_action_just_pressed("interact"):
		interacted.emit()

func add_treats(amount: int) -> void:
	treats += amount
	collected_treats.emit(treats)

func add_item(item_id: String) -> void:
	if not inventory.has(item_id):
		inventory.append(item_id)

func get_last_move_dir() -> Vector3:
	return _last_move_dir

func _update_animation() -> void:
	if _anim_player == null:
		return
	var moving := Vector3(velocity.x, 0.0, velocity.z).length() > 0.2
	if moving and _move_anim != "" and _anim_player.current_animation != _move_anim:
		_anim_player.play(_move_anim)
	if not moving and _idle_anim != "" and _anim_player.current_animation != _idle_anim:
		_anim_player.play(_idle_anim)

func _pick_anim(candidates: Array[String]) -> String:
	if _anim_player == null:
		return ""
	for name in candidates:
		if _anim_player.has_animation(name):
			return name
	if _anim_player.get_animation_list().size() > 0:
		return _anim_player.get_animation_list()[0]
	return ""

func _update_zoomies_timers(delta: float) -> void:
	_zoomies_timer = max(0.0, _zoomies_timer - delta)
	_zoomies_cooldown_timer = max(0.0, _zoomies_cooldown_timer - delta)

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
		replacement.position = Vector3(0, 0.15, 0)
		replacement.scale = Vector3(0.9, 0.9, 0.9)
		model_root = replacement
