extends CanvasLayer

@onready var treat_label: Label = $TopBar/Treats
@onready var objective_label: Label = $TopBar/Objective
@onready var status_label: Label = $TopBar/Status
@onready var side_mission_label: Label = $TopBar/SideMission
@onready var hint_label: Label = $Hint
@onready var prompt_label: Label = $Prompt
@onready var win_banner: Label = $WinBanner
@onready var recap_label: Label = $Recap

func _ready() -> void:
	# Keep text legible against bright and dark world backgrounds.
	for label in [treat_label, objective_label, status_label, side_mission_label, hint_label, prompt_label, win_banner, recap_label]:
		if label == null:
			continue
		label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
		label.add_theme_constant_override("outline_size", 3)
	treat_label.add_theme_color_override("font_color", Color(0.94, 0.89, 0.68, 1))
	objective_label.add_theme_color_override("font_color", Color(0.92, 0.95, 1, 1))
	status_label.add_theme_color_override("font_color", Color(0.78, 0.93, 0.98, 1))
	side_mission_label.add_theme_color_override("font_color", Color(1.0, 0.79, 0.45, 1))
	hint_label.add_theme_color_override("font_color", Color(0.86, 0.93, 1.0, 1))
	prompt_label.add_theme_color_override("font_color", Color(0.9, 1.0, 0.9, 1))
	recap_label.add_theme_color_override("font_color", Color(1.0, 0.98, 0.88, 1))

func bind_player(player: Node) -> void:
	if player == null:
		return
	if not player.collected_treats.is_connected(_on_treats_changed):
		player.collected_treats.connect(_on_treats_changed)
	_on_treats_changed(player.treats)

func _on_treats_changed(total: int) -> void:
	treat_label.text = "Treats: %d" % total

func set_hint(text: String) -> void:
	hint_label.text = text

func set_prompt(text: String) -> void:
	prompt_label.text = text

func set_objective(text: String) -> void:
	objective_label.text = text

func set_status(text: String) -> void:
	status_label.text = text

func set_side_mission(text: String, enabled: bool) -> void:
	side_mission_label.text = text
	side_mission_label.visible = enabled

func set_win_state(enabled: bool) -> void:
	win_banner.visible = enabled

func set_recap(text: String, enabled: bool) -> void:
	recap_label.text = text
	recap_label.visible = enabled
