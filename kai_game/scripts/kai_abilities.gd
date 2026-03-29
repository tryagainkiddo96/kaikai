## Kai Spy Ability System
## Modular ability framework — plug in any spy power.
## Each ability has: cooldown, duration, active state, visual effect.
extends Node
class_name KaiAbilities

# Reference to the player
var kai: CharacterBody2D

# Ability state
var abilities: Dictionary = {}

# Signals
signal ability_activated(name: String)
signal ability_ended(name: String)
signal intel_gathered(info: Dictionary)

# Visual layer
var fx_layer: CanvasLayer


func _init(player: CharacterBody2D) -> void:
	kai = player
	_register_abilities()


func _register_abilities() -> void:
	# Each ability: {cooldown, duration, timer, active, effect_func}
	abilities = {
		"silent_paws": {
			"name": "Silent Paws",
			"key": "ability_1",
			"cooldown": 0.0,     # passive
			"duration": 0.0,
			"timer": 0.0,
			"active": false,
			"type": "passive",
			"description": "Move without sound — reduced detection radius",
		},
		"shadow_fur": {
			"name": "Shadow Fur",
			"key": "ability_2",
			"cooldown": 12.0,
			"duration": 10.0,
			"timer": 0.0,
			"active": false,
			"type": "toggle",
			"description": "Near-invisibility in darkness",
		},
		"good_boy_face": {
			"name": "Good Boy Face",
			"key": "ability_3",
			"cooldown": 20.0,
			"duration": 8.0,
			"timer": 0.0,
			"active": false,
			"type": "toggle",
			"description": "Guards ignore you — you're just a cute dog",
		},
		"deep_sniff": {
			"name": "Deep Sniff",
			"key": "ability_4",
			"cooldown": 5.0,
			"duration": 1.5,
			"timer": 0.0,
			"active": false,
			"type": "action",
			"description": "Gather intel from objects, people, locations",
		},
		"smoke_roll": {
			"name": "Smoke Roll",
			"key": "ability_5",
			"cooldown": 15.0,
			"duration": 0.0,
			"timer": 0.0,
			"active": false,
			"type": "instant",
			"description": "Break line of sight with smoke burst",
		},
		"paw_cloner": {
			"name": "Paw Print Cloner",
			"key": "ability_6",
			"cooldown": 10.0,
			"duration": 0.8,
			"timer": 0.0,
			"active": false,
			"type": "action",
			"description": "Clone fingerprints and keycard data",
		},
		"fox_walk": {
			"name": "Fox Walk",
			"key": "ultimate",
			"cooldown": 60.0,
			"duration": 15.0,
			"timer": 0.0,
			"active": false,
			"type": "ultimate",
			"description": "Total undetectability — ghost mode",
		},
		"bone_decoy": {
			"name": "Bone Decoy",
			"key": "ability_7",
			"cooldown": 30.0,
			"duration": 12.0,
			"timer": 0.0,
			"active": false,
			"type": "deployable",
			"description": "Distract all nearby enemies with a bone",
		},
	}


func _process(delta: float) -> void:
	for ability_name in abilities:
		var ab = abilities[ability_name]
		if ab["timer"] > 0:
			ab["timer"] = maxf(ab["timer"] - delta, 0.0)
		
		# Auto-end timed abilities
		if ab["active"] and ab["duration"] > 0 and ab["timer"] <= 0:
			_deactivate(ability_name)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

func activate(ability_name: String) -> bool:
	"""Try to activate an ability. Returns true if successful."""
	if ability_name not in abilities:
		return false
	
	var ab = abilities[ability_name]
	
	# Check cooldown
	if ab["timer"] > 0:
		return false
	
	# Check if already active (toggle off)
	if ab["active"] and ab["type"] == "toggle":
		_deactivate(ability_name)
		return true
	
	# Activate
	ab["active"] = true
	if ab["cooldown"] > 0:
		ab["timer"] = ab["cooldown"]
	if ab["duration"] > 0:
		ab["timer"] = ab["duration"]  # timer tracks remaining duration when active
	
	ability_activated.emit(ability_name)
	_apply_effect(ability_name)
	return true


func _deactivate(ability_name: String) -> void:
	var ab = abilities[ability_name]
	ab["active"] = false
	# Start cooldown after deactivation
	if ab["cooldown"] > 0:
		ab["timer"] = ab["cooldown"]
	ability_ended.emit(ability_name)
	_remove_effect(ability_name)


func is_active(ability_name: String) -> bool:
	return abilities.get(ability_name, {}).get("active", false)


func get_cooldown(ability_name: String) -> float:
	return abilities.get(ability_name, {}).get("timer", 0.0)


func get_all_status() -> Dictionary:
	var status := {}
	for name in abilities:
		var ab = abilities[name]
		status[name] = {
			"active": ab["active"],
			"ready": ab["timer"] <= 0,
			"cooldown_remaining": ab["timer"],
			"type": ab["type"],
			"description": ab["description"],
		}
	return status


# ---------------------------------------------------------------------------
# Effect application
# ---------------------------------------------------------------------------

func _apply_effect(ability_name: String) -> void:
	match ability_name:
		"silent_paws":
			_effect_silent_paws(true)
		"shadow_fur":
			_effect_shadow_fur(true)
		"good_boy_face":
			_effect_good_boy_face(true)
		"deep_sniff":
			_effect_deep_sniff()
		"smoke_roll":
			_effect_smoke_roll()
		"paw_cloner":
			_effect_paw_cloner()
		"fox_walk":
			_effect_fox_walk(true)
		"bone_decoy":
			_effect_bone_decoy()


func _remove_effect(ability_name: String) -> void:
	match ability_name:
		"silent_paws":
			_effect_silent_paws(false)
		"shadow_fur":
			_effect_shadow_fur(false)
		"good_boy_face":
			_effect_good_boy_face(false)
		"fox_walk":
			_effect_fox_walk(false)


# ---------------------------------------------------------------------------
# Individual effects
# ---------------------------------------------------------------------------

func _effect_silent_paws(enable: bool) -> void:
	# Reduce enemy detection radius
	if kai.has_method("set_stealth_modifier"):
		kai.set_stealth_modifier(0.3 if enable else 1.0)
	# Visual: subtle outline change
	if enable:
		kai.modulate = kai.modulate.darkened(0.15)
	else:
		kai.modulate = kai.modulate.lightened(0.15)


func _effect_shadow_fur(enable: bool) -> void:
	# Near-invisibility
	var tween := kai.create_tween()
	if enable:
		tween.tween_property(kai, "modulate:a", 0.25, 0.5)
		kai.collision_layer = 0  # Untargetable
	else:
		tween.tween_property(kai, "modulate:a", 1.0, 0.5)
		kai.collision_layer = 1  # Targetable again


func _effect_good_boy_face(enable: bool) -> void:
	# Enemies don't attack — they "pet" instead
	if kai.has_method("set_social_stealth"):
		kai.set_social_stealth(enable)
	# Visual: hearts float up from nearby enemies
	if enable:
		_spawn_heart_particles()


func _effect_deep_sniff() -> void:
	# Scan area for intel
	var intel: Dictionary = {
		"enemies_nearby": 0,
		"nearest_enemy_dist": 9999.0,
		"items_found": [],
		"exits": [],
		"traps": [],
	}
	
	# Count enemies
	for enemy in kai.get_tree().get_nodes_in_group("enemies"):
		if kai.is_instance_valid(enemy):
			var dist = kai.global_position.distance_to(enemy.global_position)
			intel["enemies_nearby"] += 1
			if dist < intel["nearest_enemy_dist"]:
				intel["nearest_enemy_dist"] = dist
	
	# Find interactables
	for item in kai.get_tree().get_nodes_in_group("interactables"):
		if kai.is_instance_valid(item):
			var dist = kai.global_position.distance_to(item.global_position)
			if dist < 200:
				intel["items_found"].append({
					"type": item.get("item_type", "unknown"),
					"distance": dist,
				})
	
	intel_gathered.emit(intel)
	
	# Visual: expanding sniff ring
	_spawn_sniff_ring()


func _effect_smoke_roll() -> void:
	# Break enemy line of sight
	for enemy in kai.get_tree().get_nodes_in_group("enemies"):
		if kai.is_instance_valid(enemy):
			var dist = kai.global_position.distance_to(enemy.global_position)
			if dist < 200:
				if enemy.has_method("lose_target"):
					enemy.lose_target()
				elif enemy.has("state"):
					enemy.state = 0  # Back to wander
	
	# Visual: smoke burst
	_spawn_smoke_burst()
	
	# Brief invulnerability
	if kai.has_method("set_invulnerable"):
		kai.set_invulnerable(true)
		await kai.get_tree().create_timer(0.5).timeout
		kai.set_invulnerable(false)


func _effect_paw_cloner() -> void:
	# Scan nearby door/terminal for access
	var intel := {"cloned": false, "target": ""}
	for item in kai.get_tree().get_nodes_in_group("keycard_targets"):
		if kai.is_instance_valid(item):
			var dist = kai.global_position.distance_to(item.global_position)
			if dist < 40:
				intel["cloned"] = true
				intel["target"] = item.get("access_name", "Unknown Access Point")
				if item.has_method("grant_access"):
					item.grant_access()
				break
	
	intel_gathered.emit(intel)
	_spawn_scan_effect()


func _effect_fox_walk(enable: bool) -> void:
	# Total ghost mode
	var tween := kai.create_tween()
	if enable:
		tween.tween_property(kai, "modulate:a", 0.15, 0.3)
		kai.collision_layer = 0
		kai.collision_mask = 0  # Walk through everything
		if kai.has_method("set_stealth_modifier"):
			kai.set_stealth_modifier(0.0)
	else:
		tween.tween_property(kai, "modulate:a", 1.0, 0.5)
		kai.collision_layer = 1
		kai.collision_mask = 12
		if kai.has_method("set_stealth_modifier"):
			kai.set_stealth_modifier(1.0)


func _effect_bone_decoy() -> void:
	# Plant a bone that distracts enemies
	var bone := Sprite2D.new()
	var img := Image.create(16, 16, false, Image.FORMAT_RGBA8)
	# Draw a tiny bone shape
	for x in 16:
		for y in 16:
			var in_shaft = x >= 4 and x <= 11 and y >= 6 and y <= 9
			var in_knob_l = x >= 1 and x <= 4 and (y >= 4 and y <= 11)
			var in_knob_r = x >= 11 and x <= 14 and (y >= 4 and y <= 11)
			if in_shaft or in_knob_l or in_knob_r:
				img.set_pixel(x, y, Color(0.95, 0.92, 0.85))
			else:
				img.set_pixel(x, y, Color.TRANSPARENT)
	var tex := ImageTexture.create_from_image(img)
	bone.texture = tex
	bone.global_position = kai.global_position
	bone.z_index = 1
	kai.get_parent().add_child(bone)
	
	# Distract nearby enemies
	for enemy in kai.get_tree().get_nodes_in_group("enemies"):
		if kai.is_instance_valid(enemy):
			var dist = kai.global_position.distance_to(enemy.global_position)
			if dist < 300:
				if enemy.has_method("set_target"):
					enemy.set_target(bone)
				elif enemy.has("target"):
					enemy.target = bone
	
	# Bone disappears after duration
	var timer := kai.get_tree().create_timer(abilities["bone_decoy"]["duration"])
	timer.timeout.connect(bone.queue_free)


# ---------------------------------------------------------------------------
# Visual effects
# ---------------------------------------------------------------------------

func _spawn_sniff_ring() -> void:
	var ring := Sprite2D.new()
	var img := Image.create(128, 128, false, Image.FORMAT_RGBA8)
	for x in 128:
		for y in 128:
			var dist := Vector2(x - 64, y - 64).length()
			if abs(dist - 56) < 4:
				img.set_pixel(x, y, Color(1.0, 0.85, 0.4, 0.7))
			elif abs(dist - 40) < 2:
				img.set_pixel(x, y, Color(1.0, 0.7, 0.3, 0.4))
			else:
				img.set_pixel(x, y, Color.TRANSPARENT)
	ring.texture = ImageTexture.create_from_image(img)
	ring.global_position = kai.global_position
	ring.scale = Vector2.ZERO
	kai.get_parent().add_child(ring)
	
	var tween := kai.create_tween()
	tween.tween_property(ring, "scale", Vector2(3.0, 3.0), 1.5)
	tween.parallel().tween_property(ring, "modulate:a", 0.0, 1.5)
	tween.tween_callback(ring.queue_free)


func _spawn_smoke_burst() -> void:
	for i in 12:
		var puff := Sprite2D.new()
		var img := Image.create(24, 24, false, Image.FORMAT_RGBA8)
		for x in 24:
			for y in 24:
				var dist := Vector2(x - 12, y - 12).length()
				if dist < 10:
					var a := 0.6 * (1.0 - dist / 10.0)
					img.set_pixel(x, y, Color(0.7, 0.7, 0.7, a))
				else:
					img.set_pixel(x, y, Color.TRANSPARENT)
		puff.texture = ImageTexture.create_from_image(img)
		puff.global_position = kai.global_position
		kai.get_parent().add_child(puff)
		
		var angle := randf() * TAU
		var dist := randf_range(30, 80)
		var target := kai.global_position + Vector2.from_angle(angle) * dist
		
		var tween := kai.create_tween()
		tween.tween_property(puff, "global_position", target, 0.8)
		tween.parallel().tween_property(puff, "modulate:a", 0.0, 1.2)
		tween.tween_callback(puff.queue_free)


func _spawn_heart_particles() -> void:
	for i in 5:
		var heart := Label.new()
		heart.text = "❤️"
		heart.add_theme_font_size_override("font_size", randi_range(12, 20))
		heart.global_position = kai.global_position + Vector2(randf_range(-20, 20), randf_range(-10, 10))
		kai.get_parent().add_child(heart)
		
		var tween := kai.create_tween()
		tween.tween_property(heart, "global_position:y", heart.global_position.y - 40, 1.5)
		tween.parallel().tween_property(heart, "modulate:a", 0.0, 1.5)
		tween.tween_callback(heart.queue_free)


func _spawn_scan_effect() -> void:
	var scan := ColorRect.new()
	scan.color = Color(0.2, 0.8, 1.0, 0.3)
	scan.size = Vector2(40, 2)
	scan.global_position = kai.global_position + Vector2(-20, -5)
	kai.get_parent().add_child(scan)
	
	var tween := kai.create_tween()
	tween.tween_property(scan, "size:x", 40, 0.3)
	tween.tween_property(scan, "modulate:a", 0.0, 0.4)
	tween.tween_callback(scan.queue_free)
