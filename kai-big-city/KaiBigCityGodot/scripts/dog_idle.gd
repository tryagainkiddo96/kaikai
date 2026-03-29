extends Node3D

@export var bob_speed := 1.8
@export var bob_amount := 0.03
@export var sway_speed := 1.6
@export var sway_amount := 0.06

var _base_position := Vector3.ZERO
var _time := 0.0

func _ready() -> void:
	_base_position = position

func _process(delta: float) -> void:
	_time += delta
	position.y = _base_position.y + sin(_time * bob_speed) * bob_amount
	rotation.y = sin(_time * sway_speed) * sway_amount
