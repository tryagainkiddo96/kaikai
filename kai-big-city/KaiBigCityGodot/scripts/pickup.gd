extends Area3D

@export var treat_value := 1
@export var is_quest_item := false
@export var quest_id := "missing_lunch"
@export var pickup_id := ""

var collected := false

@onready var glow: OmniLight3D = $Glow
@onready var collision: CollisionShape3D = $CollisionShape3D

func _ready() -> void:
	if pickup_id == "":
		pickup_id = name
	if is_quest_item:
		add_to_group("quest_item")
	else:
		add_to_group("treat")

func collect(player: Node) -> void:
	if collected:
		return
	collected = true
	visible = false
	monitoring = false
	if collision != null:
		collision.disabled = true
	if is_quest_item:
		if player.has_method("set_meta"):
			player.set_meta(quest_id, true)
		return

	if player.has_method("add_treats"):
		player.add_treats(treat_value)

func set_highlight(enabled: bool) -> void:
	if glow == null:
		return
	glow.light_energy = 3.0 if enabled and not collected else 0.0

func get_prompt(_player: Node = null) -> String:
	if collected:
		return ""
	if is_quest_item:
		return "Press F: Pick up lunch bag"
	return "Press F: Collect treat (+%d)" % treat_value

func reset_pickup() -> void:
	set_collected_state(false)

func set_collected_state(value: bool) -> void:
	collected = value
	visible = not value
	monitoring = not value
	if collision != null:
		collision.disabled = value
	set_highlight(false)
