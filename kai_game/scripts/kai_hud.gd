## Kai HUD
## Shows HP bar, ability cooldowns, and XP.
extends CanvasLayer
class_name KaiHUD

@onready var hp_bar: ProgressBar = $MarginContainer/VBoxContainer/HPBar
@onready var hp_label: Label = $MarginContainer/VBoxContainer/HPLabel
@onready var ability_container: HBoxContainer = $MarginContainer/VBoxContainer/AbilityBar

# Ability cooldown indicators
var ability_bars: Dictionary = {}

var abilities: Array[String] = ["paw_swipe", "bark_signal", "sniff_out", "paw_shield"]
var ability_labels: Dictionary = {
	"paw_swipe": "🐾 Paw",
	"bark_signal": "📢 Bark",
	"sniff_out": "👃 Sniff",
	"paw_shield": "🛡️ Shield",
}
var cooldowns: Dictionary = {
	"paw_swipe": 0.4,
	"bark_signal": 3.0,
	"sniff_out": 2.0,
	"paw_shield": 8.0,
}
var cooldown_timers: Dictionary = {}


func _ready() -> void:
	for ability in abilities:
		cooldown_timers[ability] = 0.0
		var vbox := VBoxContainer.new()

		var bar := ProgressBar.new()
		bar.min_value = 0
		bar.max_value = 100
		bar.value = 100
		bar.custom_minimum_size = Vector2(60, 8)
		bar.show_percentage = false

		var lbl := Label.new()
		lbl.text = ability_labels.get(ability, ability)
		lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		lbl.add_theme_font_size_override("font_size", 11)

		vbox.add_child(bar)
		vbox.add_child(lbl)
		ability_container.add_child(vbox)
		ability_bars[ability] = bar


func _process(delta: float) -> void:
	# Tick cooldown timers
	for ability in abilities:
		if cooldown_timers[ability] > 0:
			cooldown_timers[ability] = maxf(cooldown_timers[ability] - delta, 0.0)
			var pct := (cooldown_timers[ability] / cooldowns[ability]) * 100.0
			ability_bars[ability].value = 100.0 - pct
		else:
			ability_bars[ability].value = 100.0


func update_hp(current: int, maximum: int) -> void:
	if hp_bar:
		hp_bar.max_value = maximum
		hp_bar.value = current
	if hp_label:
		hp_label.text = "HP: %d / %d" % [current, maximum]


func on_ability_used(ability_name: String) -> void:
	if ability_name in cooldown_timers:
		cooldown_timers[ability_name] = cooldowns[ability_name]
