extends Node3D

@onready var player: CharacterBody3D = $Player
@onready var hud: CanvasLayer = $HUD
@onready var hint_timer: Timer = $HintTimer
@onready var bark_player: AudioStreamPlayer = $BarkAudio
@onready var treat_player: AudioStreamPlayer = $TreatAudio
@onready var quest_npc: Node = $Neighbor
@onready var quest_marker: Label3D = $Neighbor/QuestMarker
@onready var yuki: Node3D = $Yuki
@onready var saiya: Node3D = $Saiya
@onready var trash_can: Node3D = $TrashCan
@onready var park_zone: Node3D = $PocketPark
@onready var dog_park_small: Node3D = $SmallDogYard
@onready var dog_park_big: Node3D = $BigDogYard
@onready var dog_park_fence: Node3D = $DogParkFenceLine
@onready var rival_dog_a: Node3D = $RivalDogA
@onready var rival_dog_b: Node3D = $RivalDogB
@onready var rival_dog_c: Node3D = $RivalDogC
@onready var home_window_spot: Node3D = $HomeWindowSpot
@onready var breakfast_bowl: Node3D = $BreakfastBowl
@onready var leash_hook: Node3D = $LeashHook
@onready var front_door_threshold: Node3D = $FrontDoorThreshold

var _last_hint := "WASD move | Shift sprint | Space jump | E bark | Q sniff | F interact | 1-6 companion commands"
var _last_treat_count := 0
var _quest_id := "missing_lunch"
var _target_treats := 10
var _game_finished := false
var _spawn_position := Vector3(0, 1.2, 6)
var _yuki_dig_timer := 0.0
var _yuki_dig_interval := 8.0
var _saiya_sentry_pos := Vector3(10, 0, -6)
var _squirrel: Node3D = null
var _squirrel_active := false
var _squirrel_spotted := false
var _chase_active := false
var _chase_timer := 0.0
var _squirrel_respawn_timer := 6.0
var _companion_mode := "follow"
var _save_path := "user://kai_big_city_save.json"
var _day_time := 0.25
var _weather_mode := "clear"
var _discovered_landmarks: Dictionary = {}
var _memory_route_progress := 0
var _squirrel_speed := 3.0
var _gold_squirrel := false
var _bark_cooldown := 0.0
var _combo_count := 0
var _collected_pickups: Dictionary = {}
var _autosave_timer := 0.0
var _autosave_interval := 60.0
var _affinity_yuki := 0
var _affinity_saiya := 0
var _chases_won := 0
var _rare_items_found := 0
var _daily_bonus_ready := true
var _yuki_sniff_pause := 0.0
var _saiya_scan_phase := 0.0
var _yuki_flank_timer := 0.0
var _yuki_flank_cooldown := 18.0
var _yuki_flank_active := false
var _yuki_flank_returning := false
var _yuki_flank_target := Vector3.ZERO
var _fence_warrior_mode := false
var _fence_warrior_timer := 0.0
var _fence_event_cooldown := 0.0
var _fence_line_slot_yuki := Vector3.ZERO
var _fence_line_slot_saiya := Vector3.ZERO
var _fence_line_slot_kai := Vector3.ZERO
var _come_inside_active := false
var _come_inside_cooldown := 22.0
var _come_inside_timer := 0.0
var _come_inside_human: Node3D = null
var _come_inside_human_speed := 4.2
var _come_inside_catch_distance := 1.55
var _come_inside_started_near_home := false
var _come_inside_fakeout_active := false
var _come_inside_fakeout_timer := 0.0
var _come_inside_fakeout_dir := Vector3.ZERO
var _story_chapter := 0
var _fence_warrior_seen := false
var _scent_trail_root: Node3D = null
var _scent_trail_refresh := 0.0
var _scent_target_kind := "none"
var _scent_target_pos := Vector3.ZERO
var _kai_mood := "curious"
var _yuki_mood := "curious"
var _saiya_mood := "protective"
var _mood_eval_timer := 0.0
var _kai_mischief := 0.35
var _yuki_curiosity := 0.62
var _saiya_guarding := 0.68
var _last_status_text := ""
var _morning_step := 0
var _morning_complete := false
var _encounter_heat := 0.0
var _encounter_tier := "calm"
var _rival_taunt_cooldown := 0.0
var _park_reputation := 0
var _park_rep_tier := "Neutral"
var _day_recap_text := ""
var _house_root: Node3D = null
var _director_mission_active := false
var _director_mission_id := "none"
var _director_mission_timer := 0.0
var _director_mission_stage := 0
var _director_mission_cooldown := 10.0
var _director_mission_fail_timer := 0.0
var _director_mission_points := 0
var _director_missions_completed := 0
var _side_mission_text := ""
var _recent_bark_timer := 0.0

func _ready() -> void:
	randomize()
	hud.bind_player(player)
	player.barked.connect(_on_player_barked)
	player.zoomies_started.connect(_on_zoomies_started)
	player.interacted.connect(_on_player_interacted)
	player.sniff_toggled.connect(_on_sniff_toggled)
	player.collected_treats.connect(_on_treats_collected)
	if quest_npc != null and "quest_id" in quest_npc:
		_quest_id = quest_npc.quest_id
	hud.set_win_state(false)
	hud.set_recap("", false)
	hud.set_side_mission("", false)
	_update_quest_marker()
	_update_objective()
	_spawn_squirrel()
	_load_progress()
	_build_house_interior()
	_restore_pickups()
	_setup_fence_slots()
	_setup_come_inside_human()
	_ensure_scent_trail_root()
	_refresh_status_panel()
	_show_hint(_last_hint)

func _physics_process(delta: float) -> void:
	_update_world_clock(delta)
	_update_weather()
	_update_bark_cooldown(delta)
	_update_autosave(delta)
	_update_encounter_director(delta)
	_update_morning_routine_progress()
	_check_landmarks()
	_update_companions(delta)
	_update_rival_dogs(delta)
	_update_squirrel_state(delta)
	_update_dog_park_event(delta)
	_update_come_inside_event(delta)
	_update_director_missions(delta)
	_update_mood_state(delta)
	_update_sniff_trail(delta)
	_update_prompt()
	_update_objective()
	_refresh_status_panel()
	if player.global_position.y < -2.5:
		player.global_position = _spawn_position
		player.velocity = Vector3.ZERO
		_show_hint("Kai hopped back to the home block.")
	_recover_fallen_companions()
	if _chase_active and _squirrel_active:
		_update_squirrel_motion(delta)

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("reset_run"):
		_reset_run()
	if event.is_action_pressed("companion_follow"):
		_set_companion_mode("follow", "Follow")
	if event.is_action_pressed("companion_stay"):
		_set_companion_mode("stay", "Stay")
	if event.is_action_pressed("companion_sentry"):
		_set_companion_mode("sentry", "Sentry")
	if event.is_action_pressed("companion_scout"):
		_set_companion_mode("scout", "Scout")
	if event.is_action_pressed("companion_search"):
		_set_companion_mode("search", "Search")
	if event.is_action_pressed("companion_guard"):
		_set_companion_mode("guard", "Guard")
	if event.is_action_pressed("quick_save"):
		_save_progress(false)
	if event.is_action_pressed("quick_load"):
		_load_progress()
	if event.is_action_pressed("home_whistle"):
		if _story_chapter >= 3:
			_show_hint("No whistle skip. Bring Kai home the old-fashioned way.")
			return
		player.global_position = _spawn_position
		player.velocity = Vector3.ZERO
		_show_hint("Kai whistled home.")

func _set_companion_mode(mode: String, label: String) -> void:
	_companion_mode = mode
	_show_hint("Command: %s." % label)
	_refresh_status_panel()

func _on_player_barked() -> void:
	if _bark_cooldown > 0.0:
		_show_hint("Bark recharging...")
		return
	_bark_cooldown = 1.2
	_recent_bark_timer = 1.0
	_kai_mischief = clamp(_kai_mischief + 0.05, 0.0, 1.0)
	_show_hint("Woof! Kai is ready to explore.")
	if bark_player != null:
		bark_player.play()
	# Bark can stun squirrel briefly during chase.
	if _chase_active and _squirrel_active and player.global_position.distance_to(_squirrel.global_position) < 4.0:
		_squirrel_speed = max(1.3, _squirrel_speed - 0.8)
		_show_hint("Bark slowed the squirrel.")
	if _is_in_dog_park() and _fence_event_cooldown <= 0.0:
		_start_fence_warrior_mode()

func _on_zoomies_started(_duration: float) -> void:
	_show_hint("Kai got the zoomies.")

func _on_player_interacted() -> void:
	if _handle_morning_interact():
		_update_objective()
		return
	var nearby := _find_nearby_interactable()
	if nearby == null:
		_show_hint("Nothing to interact with right now.")
		return

	if nearby.is_in_group("treat") and nearby.has_method("collect"):
		nearby.collect(player)
		_show_hint("Treat collected.")
		if "pickup_id" in nearby:
			_collected_pickups[nearby.pickup_id] = true
		_combo_count += 1
		_update_objective()
		return

	if nearby.is_in_group("quest_item") and nearby.has_method("collect"):
		nearby.collect(player)
		_show_hint("You found the missing lunch bag.")
		if "pickup_id" in nearby:
			_collected_pickups[nearby.pickup_id] = true
		player.add_item("lunch_bag")
		_update_quest_marker()
		_update_objective()
		return

	if nearby.is_in_group("npc") and nearby.has_method("talk"):
		var line = nearby.talk(player)
		_show_hint(line)
		if line.find("found it") != -1:
			_affinity_saiya += 1
			_affinity_yuki += 1
		_update_quest_marker()
		_update_objective()
		return

func _handle_morning_interact() -> bool:
	if _story_chapter != 0 or _morning_complete:
		return false
	if _morning_step == 1 and breakfast_bowl != null and player.global_position.distance_to(breakfast_bowl.global_position) < 2.2:
		player.add_treats(1)
		_morning_step = 2
		_show_hint("Breakfast done. Grab the leash.")
		return true
	if _morning_step == 2 and leash_hook != null and player.global_position.distance_to(leash_hook.global_position) < 2.2:
		_morning_step = 3
		_show_hint("Leash clipped in. Head to the front door.")
		return true
	return false

func _update_morning_routine_progress() -> void:
	if _story_chapter != 0 or _morning_complete:
		return
	if _morning_step == 0 and home_window_spot != null and player.global_position.distance_to(home_window_spot.global_position) < 2.1:
		_morning_step = 1
		_show_hint("Window check done. Breakfast time.")
		return
	if _morning_step == 3 and front_door_threshold != null and player.global_position.distance_to(front_door_threshold.global_position) < 1.9:
		_morning_step = 4
		_morning_complete = true
		_kai_mischief = clamp(_kai_mischief + 0.04, 0.0, 1.0)
		_show_hint("Door open. Morning walk started.")
		return

func _morning_target_position() -> Vector3:
	if _morning_step == 0 and home_window_spot != null:
		return home_window_spot.global_position
	if _morning_step == 1 and breakfast_bowl != null:
		return breakfast_bowl.global_position
	if _morning_step == 2 and leash_hook != null:
		return leash_hook.global_position
	if front_door_threshold != null:
		return front_door_threshold.global_position
	return _spawn_position

func _find_nearby_interactable() -> Node:
	var candidates: Array[Node] = []
	for node in get_tree().get_nodes_in_group("treat"):
		candidates.append(node)
	for node in get_tree().get_nodes_in_group("npc"):
		candidates.append(node)
	for node in get_tree().get_nodes_in_group("quest_item"):
		if "collected" in node and node.collected:
			continue
		candidates.append(node)
	if candidates.is_empty():
		return null
	candidates.sort_custom(func(a: Node, b: Node) -> bool:
		return a.global_position.distance_to(player.global_position) < b.global_position.distance_to(player.global_position)
	)
	if candidates[0].global_position.distance_to(player.global_position) < 2.4:
		return candidates[0]
	return null

func _on_sniff_toggled(enabled: bool) -> void:
	for node in get_tree().get_nodes_in_group("treat"):
		if node.has_method("set_highlight"):
			node.set_highlight(enabled)
	for node in get_tree().get_nodes_in_group("quest_item"):
		if node.has_method("set_highlight"):
			node.set_highlight(enabled)
	if not enabled:
		_clear_scent_trail()
		_scent_target_kind = "none"
	else:
		_scent_trail_refresh = 0.0
	_show_hint("Sniff mode: %s" % ("on" if enabled else "off"))
	_refresh_status_panel()

func _show_hint(text: String) -> void:
	hud.set_hint(text)
	_last_hint = text
	hint_timer.start()

func _on_hint_timer_timeout() -> void:
	hud.set_hint(_last_hint)

func _on_treats_collected(total: int) -> void:
	if total > _last_treat_count and treat_player != null:
		treat_player.play()
	_last_treat_count = total
	_update_objective()

func _update_quest_marker() -> void:
	if quest_marker == null:
		return
	var completed_key := "%s_completed" % _quest_id
	var found = player.has_meta(_quest_id) and player.get_meta(_quest_id) == true
	var completed = player.has_meta(completed_key) and player.get_meta(completed_key) == true
	if completed:
		quest_marker.text = ""
	elif found:
		quest_marker.text = "?"
	else:
		quest_marker.text = "!"

func _update_objective() -> void:
	if _come_inside_active:
		hud.set_objective("Event: Evade being called inside")
		return
	if _update_story_chapter():
		return
	var completed_key := "%s_completed" % _quest_id
	var quest_complete = player.has_meta(completed_key) and player.get_meta(completed_key) == true
	var found_item = player.has_meta(_quest_id) and player.get_meta(_quest_id) == true
	var treat_goal_done = player.has_method("get") and player.get("treats") >= _target_treats

	if _game_finished:
		hud.set_objective("Day Complete: Kai's neighborhood story")
		return

	if not found_item and not quest_complete:
		hud.set_objective("Find the Store Clerk's lunch bag in the alley")
		return

	if found_item and not quest_complete:
		hud.set_objective("Return the lunch bag to the Store Clerk")
		return

	if not treat_goal_done:
		hud.set_objective("Collect %d treats (%d/%d) | Mode: %s | Y:%d S:%d" % [_target_treats, player.get("treats"), _target_treats, _companion_mode, _affinity_yuki, _affinity_saiya])
		return

	_game_finished = true
	hud.set_objective("Objective complete: Home block hero")
	hud.set_win_state(true)
	_show_hint("You did it. Kai helped everyone and owned the block.")

func _update_story_chapter() -> bool:
	if _game_finished:
		return false
	var completed_key := "%s_completed" % _quest_id
	var quest_complete = player.has_meta(completed_key) and player.get_meta(completed_key) == true
	var at_home := player.global_position.distance_to(_spawn_position) < 3.2
	var reached_street := _discovered_landmarks.has("n_tenth_st")
	var reached_park_gate := _discovered_landmarks.has("dog_park_gate")
	var reached_fence := _discovered_landmarks.has("fence_line")
	var park_memory_done := _memory_route_progress >= 4
	var won_park_activity := _chases_won > 0 or _fence_warrior_seen

	if _story_chapter == 0:
		if not _morning_complete:
			if _morning_step == 0:
				hud.set_objective("Morning: Check the window before walk time")
			elif _morning_step == 1:
				hud.set_objective("Morning: Eat breakfast")
			elif _morning_step == 2:
				hud.set_objective("Morning: Grab Kai's leash")
			else:
				hud.set_objective("Morning: Head to the front door")
			return true
		hud.set_objective("Morning: Leave home and start the N Tenth walk")
		if reached_street:
			_story_chapter = 1
			_show_hint("Chapter 2: Neighborhood walk started.")
			return _update_story_chapter()
		return true

	if _story_chapter == 1:
		hud.set_objective("Midday: Help the neighbor and reach the dog park gate")
		if quest_complete and reached_park_gate:
			_story_chapter = 2
			_show_hint("Chapter 3: Dog park saga unlocked.")
			return _update_story_chapter()
		return true

	if _story_chapter == 2:
		hud.set_objective("Dog Park: Trigger a stand-off or win a squirrel chase")
		if won_park_activity and reached_fence and park_memory_done:
			_story_chapter = 3
			_show_hint("Chapter 4: Evening return home.")
			return _update_story_chapter()
		return true

	if _story_chapter == 3:
		hud.set_objective("Evening: Bring Kai back to the home block")
		if at_home:
			_story_chapter = 4
			_game_finished = true
			_adjust_park_reputation(2, "safe return")
			hud.set_win_state(true)
			_day_recap_text = _build_day_recap()
			hud.set_recap(_day_recap_text, true)
			hud.set_objective("Day Complete: Kai's neighborhood story")
			_show_hint("Day complete. Kai made it home after a full Shiba adventure.")
		return true

	return false

func _update_prompt() -> void:
	var morning_prompt := _get_morning_prompt()
	if morning_prompt != "":
		hud.set_prompt(morning_prompt)
		return
	var nearby := _find_nearby_interactable()
	if nearby == null:
		hud.set_prompt("")
		return
	if nearby.has_method("get_prompt"):
		var prompt = nearby.get_prompt(player)
		hud.set_prompt(prompt)
		return
	hud.set_prompt("Press F: Interact")

func _get_morning_prompt() -> String:
	if _story_chapter != 0 or _morning_complete:
		return ""
	if _morning_step == 0:
		if home_window_spot != null and player.global_position.distance_to(home_window_spot.global_position) < 3.2:
			return "Morning: Check the window"
		return "Morning routine: head to the window"
	if _morning_step == 1:
		if breakfast_bowl != null and player.global_position.distance_to(breakfast_bowl.global_position) < 2.4:
			return "Press F: Eat breakfast"
		return "Morning: Go to the breakfast bowl"
	if _morning_step == 2:
		if leash_hook != null and player.global_position.distance_to(leash_hook.global_position) < 2.4:
			return "Press F: Grab leash"
		return "Morning: Move to the leash hook"
	if _morning_step == 3:
		return "Morning: Head to the front door"
	return ""

func _reset_run() -> void:
	player.global_position = _spawn_position
	player.velocity = Vector3.ZERO
	player.treats = 0
	player.inventory = []
	player.set_meta(_quest_id, false)
	player.set_meta("%s_completed" % _quest_id, false)
	_game_finished = false
	_last_treat_count = 0
	_yuki_dig_timer = 0.0
	_yuki_flank_timer = 0.0
	_yuki_flank_active = false
	_yuki_flank_returning = false
	_fence_warrior_mode = false
	_fence_warrior_timer = 0.0
	_fence_event_cooldown = 0.0
	_fence_warrior_seen = false
	_end_come_inside_event(true)
	_come_inside_cooldown = 18.0
	_squirrel_spotted = false
	_chase_active = false
	_chase_timer = 0.0
	_squirrel_respawn_timer = 3.0
	_squirrel_speed = 3.0
	_gold_squirrel = false
	_combo_count = 0
	_collected_pickups.clear()
	_discovered_landmarks.clear()
	_memory_route_progress = 0
	_story_chapter = 0
	_morning_step = 0
	_morning_complete = false
	_kai_mood = "curious"
	_yuki_mood = "curious"
	_saiya_mood = "protective"
	_kai_mischief = 0.35
	_yuki_curiosity = 0.62
	_saiya_guarding = 0.68
	_mood_eval_timer = 0.0
	_companion_mode = "follow"
	_scent_target_kind = "none"
	_scent_target_pos = Vector3.ZERO
	_last_status_text = ""
	_encounter_heat = 0.0
	_encounter_tier = "calm"
	_rival_taunt_cooldown = 0.0
	_park_reputation = 0
	_refresh_park_rep_tier()
	_day_recap_text = ""
	_director_mission_active = false
	_director_mission_id = "none"
	_director_mission_timer = 0.0
	_director_mission_stage = 0
	_director_mission_cooldown = 10.0
	_director_mission_fail_timer = 0.0
	_director_mission_points = 0
	_director_missions_completed = 0
	_side_mission_text = ""
	_recent_bark_timer = 0.0
	_clear_scent_trail()
	_set_squirrel_visible(false)
	hud.bind_player(player)
	hud.set_win_state(false)
	hud.set_recap("", false)
	hud.set_side_mission("", false)
	_restore_pickups()
	_update_quest_marker()
	_update_objective()
	_show_hint("Run reset. Explore the block again.")

func _update_companions(delta: float) -> void:
	var path_dir = player.get_last_move_dir().normalized()
	if path_dir.length() < 0.1:
		path_dir = Vector3(0, 0, -1)
	var yuki_speed := 3.3 + (_yuki_curiosity * 1.5)
	var saiya_speed := 3.7 + (_saiya_guarding * 1.6)

	if yuki != null:
		_update_yuki_flank_state(delta)
		var yuki_target := player.global_position + Vector3(-1.6, 0, 1.2)
		if _companion_mode == "stay":
			yuki_target = yuki.global_position
		elif _companion_mode == "sentry":
			yuki_target = trash_can.global_position if trash_can != null else yuki.global_position
		elif _companion_mode == "scout":
			yuki_target = player.global_position + path_dir * 4.6 + Vector3(-1.2, 0, 0.8)
		elif _companion_mode == "search":
			yuki_target = _scent_target_pos if _scent_target_kind != "none" else (trash_can.global_position if trash_can != null else yuki_target)
		elif _companion_mode == "guard":
			yuki_target = player.global_position + Vector3(-1.3, 0, 1.8)
		if _yuki_flank_active:
			yuki_target = _yuki_flank_target
		elif _yuki_flank_returning:
			yuki_target = player.global_position + Vector3(-1.0, 0, 0.9)
		if _fence_warrior_mode:
			yuki_target = _fence_line_slot_yuki
		# Shiba scavenger behavior: brief sniff pauses near interesting spots.
		_yuki_sniff_pause = max(0.0, _yuki_sniff_pause - delta)
		if _yuki_sniff_pause <= 0.0:
			_move_node_toward(yuki, yuki_target, yuki_speed, delta)
		var yuki_searching_trash := _companion_mode == "search" and trash_can != null and yuki.global_position.distance_to(trash_can.global_position) < 5.0
		var sniff_rate := 0.9 + (_yuki_curiosity * 0.8) + (1.2 if yuki_searching_trash else 0.0)
		if trash_can != null and yuki.global_position.distance_to(trash_can.global_position) < 2.1 and _yuki_sniff_pause <= 0.0 and randf() < delta * sniff_rate:
			_yuki_sniff_pause = 1.0 + randf() * 1.2
			_show_hint("Yuki is sniffing through trash.")
		_yuki_dig_timer += delta
		var dig_interval := _yuki_dig_interval
		if yuki_searching_trash:
			dig_interval = max(3.0, _yuki_dig_interval * 0.48)
		if trash_can != null and yuki.global_position.distance_to(trash_can.global_position) < 3.2 and _yuki_dig_timer >= dig_interval:
			_yuki_dig_timer = 0.0
			var found_item := _yuki_scavenge()
			_affinity_yuki += 1
			_show_hint("Yuki found: %s." % found_item)

	if saiya != null:
		var saiya_target := player.global_position + Vector3(1.8, 0, 1.1)
		if _companion_mode == "stay":
			saiya_target = saiya.global_position
		elif _companion_mode == "sentry":
			saiya_target = _saiya_sentry_pos
		elif _companion_mode == "guard":
			saiya_target = _fence_line_slot_saiya if _is_in_dog_park() else _saiya_sentry_pos
		elif _companion_mode == "scout":
			saiya_target = player.global_position + path_dir * 5.4 + Vector3(1.8, 0, -0.8)
		elif _companion_mode == "search":
			if _scent_target_kind != "none":
				saiya_target = _scent_target_pos + Vector3(0.9, 0, 0.6)
			elif _squirrel_active:
				saiya_target = _squirrel.global_position
			else:
				saiya_target = _saiya_sentry_pos
		if _squirrel_active and not _chase_active:
			# Saiya posts up and watches for movement near the park.
			if _companion_mode == "guard" or _companion_mode == "sentry":
				saiya_target = _saiya_sentry_pos
			_saiya_scan_phase += delta
			var spot_range := 8.0 + (_saiya_guarding * 3.8) + (1.4 if _companion_mode == "guard" else 0.0)
			if saiya.global_position.distance_to(_squirrel.global_position) < spot_range:
				_squirrel_spotted = true
				_start_squirrel_chase()
		if _chase_active and _squirrel_active:
			saiya_target = _squirrel.global_position
		if _fence_warrior_mode:
			saiya_target = _fence_line_slot_saiya
		if _companion_mode == "guard" and _is_in_dog_park() and _fence_event_cooldown <= 0.0 and randf() < delta * 0.32:
			_start_fence_warrior_mode()
		_move_node_toward(saiya, saiya_target, saiya_speed, delta)
		# Sentry vibe: idle scan yaw while posted.
		if not _chase_active and saiya.global_position.distance_to(_saiya_sentry_pos) < 1.1 and _companion_mode != "follow":
			saiya.rotation.y = sin(_saiya_scan_phase * 1.6) * 0.5

func _update_yuki_flank_state(delta: float) -> void:
	if _fence_warrior_mode:
		return
	if _companion_mode != "follow" and _companion_mode != "scout":
		return
	_yuki_flank_timer += delta
	if not _yuki_flank_active and not _yuki_flank_returning and _yuki_flank_timer >= _yuki_flank_cooldown and randf() < 0.04:
		_yuki_flank_active = true
		_yuki_flank_timer = 0.0
		var ahead = player.global_position + player.get_last_move_dir().normalized() * (8.0 + randf() * 6.0)
		if ahead.length() < 0.1:
			ahead = player.global_position + Vector3(0, 0, -10.0)
		_yuki_flank_target = ahead + Vector3(randf_range(-2.0, 2.0), 0, randf_range(-2.0, 2.0))
		if yuki != null:
			yuki.visible = false
		_show_hint("Yuki flanked ahead.")
		return
	if _yuki_flank_active and yuki != null:
		# Reappear at flank point and alert bark like she found something first.
		yuki.global_position = _yuki_flank_target
		yuki.visible = true
		_yuki_flank_active = false
		_yuki_flank_returning = true
		_yuki_flank_cooldown = 14.0 + randf() * 10.0
		_show_hint("Yuki looped around and barked at something up ahead.")
		if bark_player != null:
			bark_player.play()
		return
	if _yuki_flank_returning and yuki != null and yuki.global_position.distance_to(player.global_position) < 2.0:
		_yuki_flank_returning = false

	if _chase_active and _squirrel_active and yuki != null:
		_move_node_toward(yuki, _squirrel.global_position, 4.0, delta)
	if _fence_warrior_mode:
		var to_slot := _fence_line_slot_kai - player.global_position
		to_slot.y = 0.0
		if to_slot.length() > 0.6:
			player.velocity.x = move_toward(player.velocity.x, to_slot.normalized().x * 4.8, 18.0 * delta)
			player.velocity.z = move_toward(player.velocity.z, to_slot.normalized().z * 4.8, 18.0 * delta)

func _update_squirrel_state(delta: float) -> void:
	if _squirrel == null:
		return

	if not _squirrel_active:
		_squirrel_respawn_timer -= delta
		if _squirrel_respawn_timer <= 0.0:
			_squirrel_respawn_timer = 12.0
			_reset_squirrel_position()
			_set_squirrel_visible(true)
		return

	if _chase_active:
		_chase_timer -= delta
		if _chase_timer <= 0.0:
			_chase_active = false
			_squirrel_spotted = false
			_set_squirrel_visible(false)
			_combo_count = 0
			_adjust_park_reputation(-1, "lost chase")
			_show_hint("The squirrel escaped. Saiya is watching for it again.")
			return
		var player_close := player.global_position.distance_to(_squirrel.global_position) < 2.5
		var yuki_close := yuki != null and yuki.global_position.distance_to(_squirrel.global_position) < 2.7
		var saiya_close := saiya != null and saiya.global_position.distance_to(_squirrel.global_position) < 2.7
		if player_close and (yuki_close or saiya_close):
			_chase_active = false
			_squirrel_spotted = false
			_set_squirrel_visible(false)
			var chase_reward = 2 + min(3, int(_combo_count / 3))
			if _gold_squirrel:
				chase_reward += 4
			player.add_treats(chase_reward)
			_affinity_saiya += 2
			_chases_won += 1
			_saiya_guarding = clamp(_saiya_guarding + 0.03, 0.0, 1.0)
			_yuki_curiosity = clamp(_yuki_curiosity + 0.02, 0.0, 1.0)
			_adjust_park_reputation(3, "clean chase")
			_show_hint("Squirrel chase won. Team Kai earned %d treats." % chase_reward)
			_combo_count = 0

func _start_squirrel_chase() -> void:
	if _chase_active:
		return
	if _come_inside_active:
		_end_come_inside_event(true)
	_kai_mischief = clamp(_kai_mischief + 0.04, 0.0, 1.0)
	_saiya_guarding = clamp(_saiya_guarding + 0.02, 0.0, 1.0)
	_encounter_heat = clamp(_encounter_heat + 0.14, 0.0, 1.0)
	_chase_active = true
	_chase_timer = 10.0
	_squirrel_speed = 3.0
	_show_hint("Saiya spotted a squirrel. Chase mini-game started.")

func _spawn_squirrel() -> void:
	_squirrel = Node3D.new()
	_squirrel.name = "Squirrel"
	add_child(_squirrel)
	var mesh_node := MeshInstance3D.new()
	var mesh := SphereMesh.new()
	mesh.radius = 0.22
	mesh.height = 0.44
	mesh_node.mesh = mesh
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.55, 0.38, 0.2, 1)
	mesh_node.set_surface_override_material(0, mat)
	_squirrel.add_child(mesh_node)
	_reset_squirrel_position()
	_set_squirrel_visible(true)

func _set_squirrel_visible(enabled: bool) -> void:
	if _squirrel == null:
		return
	_squirrel.visible = enabled
	_squirrel_active = enabled

func _reset_squirrel_position() -> void:
	if _squirrel == null:
		return
	var base := Vector3(12, 0.3, -8)
	if park_zone != null:
		base = park_zone.global_position + Vector3(0, 0.3, 0)
	var jitter := Vector3(randf_range(-2.2, 2.2), 0, randf_range(-2.2, 2.2))
	_squirrel.global_position = base + jitter
	_gold_squirrel = randf() < 0.18
	var mesh_node := _squirrel.get_child(0)
	if mesh_node is MeshInstance3D:
		var gold := Color(0.9, 0.8, 0.2, 1) if _gold_squirrel else Color(0.55, 0.38, 0.2, 1)
		var mat := StandardMaterial3D.new()
		mat.albedo_color = gold
		mesh_node.set_surface_override_material(0, mat)

func _move_node_toward(node: Node3D, target: Vector3, speed: float, delta: float) -> void:
	var to_target := target - node.global_position
	to_target.y = 0.0
	if to_target.length() < 0.05:
		return
	var next := node.global_position + to_target.normalized() * speed * delta
	next.y = node.global_position.y
	node.global_position = next
	var yaw := atan2(to_target.x, to_target.z)
	node.rotation.y = lerp_angle(node.rotation.y, yaw, 8.0 * delta)

func _setup_come_inside_human() -> void:
	if _come_inside_human != null:
		return
	_come_inside_human = Node3D.new()
	_come_inside_human.name = "ComeInsideHuman"
	add_child(_come_inside_human)
	var body := MeshInstance3D.new()
	var mesh := CapsuleMesh.new()
	mesh.radius = 0.28
	mesh.height = 1.5
	body.mesh = mesh
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.28, 0.45, 0.7, 1)
	body.set_surface_override_material(0, mat)
	body.position = Vector3(0, 1.0, 0)
	_come_inside_human.add_child(body)
	var label := Label3D.new()
	label.text = "COME HERE, KAI!"
	label.font_size = 16
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.position = Vector3(0, 2.1, 0)
	_come_inside_human.add_child(label)
	_come_inside_human.visible = false
	_come_inside_human.global_position = _spawn_position + Vector3(2.4, 0, 1.6)

func _update_come_inside_event(delta: float) -> void:
	_come_inside_cooldown = max(0.0, _come_inside_cooldown - delta)
	if _come_inside_active:
		_come_inside_timer -= delta
		_update_come_inside_fakeout(delta)
		if _come_inside_human != null:
			_move_node_toward(_come_inside_human, player.global_position, _come_inside_human_speed, delta)
			var dist := _come_inside_human.global_position.distance_to(player.global_position)
			if dist <= _come_inside_catch_distance:
				_show_hint("Caught. Kai had to come inside.")
				player.global_position = _spawn_position
				player.velocity = Vector3.ZERO
				_end_come_inside_event(true)
				return
		if _come_inside_timer <= 0.0:
			player.add_treats(1)
			_show_hint("Kai evaded long enough. Human gave up and went inside (+1 treat).")
			_end_come_inside_event(true)
		return

	if _come_inside_cooldown > 0.0:
		return
	if _story_chapter == 0 and not _morning_complete:
		return
	if _fence_warrior_mode or _chase_active:
		return
	if player.global_position.distance_to(_spawn_position) > 16.0:
		return
	var come_inside_rate := (0.06 + _kai_mischief * 0.14) * _encounter_multiplier()
	if randf() > (delta * come_inside_rate):
		return
	_start_come_inside_event()

func _start_come_inside_event() -> void:
	if _come_inside_human == null:
		return
	_come_inside_active = true
	_come_inside_timer = 13.0
	_come_inside_started_near_home = player.global_position.distance_to(_spawn_position) < 10.0
	_come_inside_fakeout_active = false
	_come_inside_fakeout_timer = 0.0
	_come_inside_fakeout_dir = Vector3.ZERO
	var spawn_offset := Vector3(-2.4, 0, 1.4)
	if player.get_last_move_dir().length() > 0.2:
		spawn_offset = -player.get_last_move_dir().normalized() * 2.8
	_come_inside_human.global_position = player.global_position + spawn_offset
	_come_inside_human.visible = true
	_show_hint("You locked eyes. 'Kai, come here!' Play keep-away until they give up.")

func _end_come_inside_event(silent: bool) -> void:
	_come_inside_active = false
	_come_inside_timer = 0.0
	_come_inside_fakeout_active = false
	_come_inside_fakeout_timer = 0.0
	_come_inside_fakeout_dir = Vector3.ZERO
	_come_inside_cooldown = 28.0 if _come_inside_started_near_home else 20.0
	_come_inside_started_near_home = false
	if _come_inside_human != null:
		_come_inside_human.visible = false
		_come_inside_human.global_position = _spawn_position + Vector3(2.4, 0, 1.6)
	if not silent:
		_show_hint("The outside game ended.")

func _update_come_inside_fakeout(delta: float) -> void:
	if _come_inside_human == null:
		return
	var to_human := _come_inside_human.global_position - player.global_position
	to_human.y = 0.0
	var dist := to_human.length()

	if _come_inside_fakeout_active:
		_come_inside_fakeout_timer -= delta
		var next := player.global_position + _come_inside_fakeout_dir * 7.4 * delta
		next.y = player.global_position.y
		player.global_position = next
		player.velocity.x = _come_inside_fakeout_dir.x * 7.2
		player.velocity.z = _come_inside_fakeout_dir.z * 7.2
		if _come_inside_fakeout_timer <= 0.0:
			_come_inside_fakeout_active = false
		return

	if dist < 2.2 or dist > 4.4:
		return
	var fakeout_chance := 0.14 + (_kai_mischief * 0.42)
	if randf() > fakeout_chance:
		return
	if to_human.length() < 0.1:
		return

	var toward_human := to_human.normalized()
	var side := Vector3(-toward_human.z, 0.0, toward_human.x)
	if randf() < 0.5:
		side = -side
	var loop_bias := (-toward_human * 0.35) + side
	if loop_bias.length() < 0.1:
		loop_bias = side

	_come_inside_fakeout_dir = loop_bias.normalized()
	_come_inside_fakeout_active = true
	_come_inside_fakeout_timer = 0.14 + randf() * (0.18 + _kai_mischief * 0.12)
	_show_hint("Kai spam-juked and looped around.")

func _update_squirrel_motion(delta: float) -> void:
	if _squirrel == null:
		return
	var run_dir := (_squirrel.global_position - player.global_position).normalized()
	run_dir.y = 0
	if run_dir.length() < 0.1:
		run_dir = Vector3(randf_range(-1, 1), 0, randf_range(-1, 1)).normalized()
	_squirrel.global_position += run_dir * _squirrel_speed * delta
	_squirrel_speed = min(5.2, _squirrel_speed + 0.05 * delta)

func _yuki_scavenge() -> String:
	var roll := randi() % 100
	if roll < 55:
		player.add_treats(1)
		_yuki_curiosity = clamp(_yuki_curiosity + 0.01, 0.0, 1.0)
		return "treat"
	if roll < 80:
		player.add_item("shiny_tag")
		_yuki_curiosity = clamp(_yuki_curiosity + 0.015, 0.0, 1.0)
		return "shiny tag"
	if roll < 93:
		player.add_item("squeaky_toy")
		_yuki_curiosity = clamp(_yuki_curiosity + 0.02, 0.0, 1.0)
		return "squeaky toy"
	player.add_item("rare_charm")
	player.add_treats(1)
	_rare_items_found += 1
	_yuki_curiosity = clamp(_yuki_curiosity + 0.03, 0.0, 1.0)
	return "rare charm"

func _save_progress(silent: bool = false) -> void:
	var save := {
		"treats": player.treats,
		"inventory": player.inventory,
		"quest_found": player.has_meta(_quest_id) and player.get_meta(_quest_id) == true,
		"quest_completed": player.has_meta("%s_completed" % _quest_id) and player.get_meta("%s_completed" % _quest_id) == true,
		"companion_mode": _companion_mode,
		"discoveries": _discovered_landmarks,
		"weather": _weather_mode,
		"collected_pickups": _collected_pickups,
		"affinity_yuki": _affinity_yuki,
		"affinity_saiya": _affinity_saiya,
		"chases_won": _chases_won,
		"rare_items_found": _rare_items_found,
		"memory_route_progress": _memory_route_progress,
		"story_chapter": _story_chapter,
		"fence_warrior_seen": _fence_warrior_seen,
		"morning_step": _morning_step,
		"morning_complete": _morning_complete,
		"kai_mood": _kai_mood,
		"yuki_mood": _yuki_mood,
		"saiya_mood": _saiya_mood,
		"kai_mischief": _kai_mischief,
		"yuki_curiosity": _yuki_curiosity,
		"saiya_guarding": _saiya_guarding,
		"encounter_heat": _encounter_heat,
		"encounter_tier": _encounter_tier,
		"park_reputation": _park_reputation,
		"day_recap_text": _day_recap_text,
		"director_mission_points": _director_mission_points,
		"director_missions_completed": _director_missions_completed,
		"director_mission_cooldown": _director_mission_cooldown,
	}
	var file := FileAccess.open(_save_path, FileAccess.WRITE)
	if file == null:
		if not silent:
			_show_hint("Save failed.")
		return
	file.store_string(JSON.stringify(save))
	if not silent:
		_show_hint("Progress saved.")

func _load_progress() -> void:
	_game_finished = false
	if not FileAccess.file_exists(_save_path):
		return
	var file := FileAccess.open(_save_path, FileAccess.READ)
	if file == null:
		return
	var raw := file.get_as_text()
	var parsed = JSON.parse_string(raw)
	if typeof(parsed) != TYPE_DICTIONARY:
		return
	player.treats = int(parsed.get("treats", 0))
	player.inventory = parsed.get("inventory", [])
	player.set_meta(_quest_id, bool(parsed.get("quest_found", false)))
	player.set_meta("%s_completed" % _quest_id, bool(parsed.get("quest_completed", false)))
	_companion_mode = String(parsed.get("companion_mode", "follow"))
	_discovered_landmarks = parsed.get("discoveries", {})
	_weather_mode = String(parsed.get("weather", "clear"))
	_collected_pickups = parsed.get("collected_pickups", {})
	if typeof(_collected_pickups) != TYPE_DICTIONARY:
		_collected_pickups = {}
	_affinity_yuki = int(parsed.get("affinity_yuki", 0))
	_affinity_saiya = int(parsed.get("affinity_saiya", 0))
	_chases_won = int(parsed.get("chases_won", 0))
	_rare_items_found = int(parsed.get("rare_items_found", 0))
	_memory_route_progress = int(parsed.get("memory_route_progress", 0))
	_story_chapter = int(parsed.get("story_chapter", 0))
	_fence_warrior_seen = bool(parsed.get("fence_warrior_seen", false))
	_morning_step = int(parsed.get("morning_step", 0))
	_morning_complete = bool(parsed.get("morning_complete", _story_chapter > 0))
	_game_finished = _story_chapter >= 4
	_kai_mood = String(parsed.get("kai_mood", "curious"))
	_yuki_mood = String(parsed.get("yuki_mood", "curious"))
	_saiya_mood = String(parsed.get("saiya_mood", "protective"))
	_kai_mischief = clamp(float(parsed.get("kai_mischief", 0.35)), 0.0, 1.0)
	_yuki_curiosity = clamp(float(parsed.get("yuki_curiosity", 0.62)), 0.0, 1.0)
	_saiya_guarding = clamp(float(parsed.get("saiya_guarding", 0.68)), 0.0, 1.0)
	_encounter_heat = clamp(float(parsed.get("encounter_heat", 0.0)), 0.0, 1.0)
	_encounter_tier = String(parsed.get("encounter_tier", "calm"))
	_park_reputation = int(parsed.get("park_reputation", 0))
	_day_recap_text = String(parsed.get("day_recap_text", ""))
	_director_mission_points = int(parsed.get("director_mission_points", 0))
	_director_missions_completed = int(parsed.get("director_missions_completed", 0))
	_director_mission_cooldown = max(0.0, float(parsed.get("director_mission_cooldown", 8.0)))
	_director_mission_active = false
	_director_mission_id = "none"
	_director_mission_timer = 0.0
	_director_mission_stage = 0
	_side_mission_text = ""
	_recent_bark_timer = 0.0
	_refresh_park_rep_tier()
	_fence_warrior_mode = false
	_fence_warrior_timer = 0.0
	_squirrel_spotted = false
	_chase_active = false
	_chase_timer = 0.0
	_end_come_inside_event(true)
	_scent_target_kind = "none"
	_scent_target_pos = Vector3.ZERO
	_last_status_text = ""
	_clear_scent_trail()
	hud.bind_player(player)
	hud.set_win_state(_game_finished)
	_restore_pickups()
	_update_quest_marker()
	_update_objective()
	hud.set_recap(_day_recap_text, _game_finished and _day_recap_text != "")
	hud.set_side_mission("", false)
	_refresh_status_panel()
	_show_hint("Progress loaded.")

func _update_world_clock(delta: float) -> void:
	_day_time += delta * 0.01
	if _day_time > 1.0:
		_day_time = 0.0
	var sun := $Sun
	if sun != null:
		sun.rotation.x = lerp(-1.0, -0.2, _day_time)
		sun.light_energy = lerp(0.5, 1.4, 1.0 - abs(_day_time - 0.5) * 1.8)

func _update_weather() -> void:
	if _day_time > 0.78 and _weather_mode != "night":
		_weather_mode = "night"
	elif _day_time <= 0.78 and _weather_mode != "clear":
		_weather_mode = "clear"
	if _day_time < 0.06 and _daily_bonus_ready:
		player.add_treats(1)
		_daily_bonus_ready = false
		_show_hint("Daily neighborhood bonus: +1 treat")
	if _day_time > 0.2:
		_daily_bonus_ready = true

func _update_encounter_director(delta: float) -> void:
	var target_heat := 0.08
	if _story_chapter >= 1:
		target_heat += 0.12
	if _story_chapter >= 2:
		target_heat += 0.14
	if _is_in_dog_park():
		target_heat += 0.18
	if _companion_mode == "guard" or _companion_mode == "scout":
		target_heat += 0.08
	if _chase_active or _fence_warrior_mode or _come_inside_active:
		target_heat += 0.3
	_encounter_heat = clamp(lerpf(_encounter_heat, target_heat, min(1.0, delta * 1.6)), 0.0, 1.0)
	if _encounter_heat < 0.25:
		_encounter_tier = "calm"
	elif _encounter_heat < 0.5:
		_encounter_tier = "active"
	elif _encounter_heat < 0.75:
		_encounter_tier = "hot"
	else:
		_encounter_tier = "chaos"

func _encounter_multiplier() -> float:
	if _encounter_tier == "calm":
		return 0.7
	if _encounter_tier == "active":
		return 1.0
	if _encounter_tier == "hot":
		return 1.25
	return 1.55

func _refresh_park_rep_tier() -> void:
	if _park_reputation >= 25:
		_park_rep_tier = "Friendly"
	elif _park_reputation <= -35:
		_park_rep_tier = "Rival"
	elif _park_reputation < -10:
		_park_rep_tier = "Tense"
	else:
		_park_rep_tier = "Neutral"

func _adjust_park_reputation(amount: int, reason: String = "") -> void:
	var previous_tier := _park_rep_tier
	_park_reputation = clamp(_park_reputation + amount, -100, 100)
	_refresh_park_rep_tier()
	if previous_tier != _park_rep_tier and reason != "":
		_show_hint("Dog park mood shifted to %s (%s)." % [_park_rep_tier, reason])

func _update_rival_dogs(delta: float) -> void:
	_rival_taunt_cooldown = max(0.0, _rival_taunt_cooldown - delta)
	if rival_dog_a == null or rival_dog_b == null or rival_dog_c == null:
		return
	var center := dog_park_fence.global_position if dog_park_fence != null else Vector3(22, 0, -8)
	if _is_in_dog_park() and (_park_rep_tier == "Tense" or _park_rep_tier == "Rival"):
		_move_node_toward(rival_dog_a, center + Vector3(5.2, 0, -2.2), 2.9, delta)
		_move_node_toward(rival_dog_b, center + Vector3(5.6, 0, 0.1), 2.7, delta)
		_move_node_toward(rival_dog_c, center + Vector3(5.3, 0, 2.3), 2.8, delta)
		if _rival_taunt_cooldown <= 0.0 and player.global_position.distance_to(center) < 10.0:
			_rival_taunt_cooldown = 5.0 + randf() * 4.0
			if bark_player != null:
				bark_player.play()
			_show_hint("Fence-line pressure is building.")
	else:
		_move_node_toward(rival_dog_a, Vector3(26.8, 0.0, -10.6), 2.1, delta)
		_move_node_toward(rival_dog_b, Vector3(27.2, 0.0, -7.8), 2.1, delta)
		_move_node_toward(rival_dog_c, Vector3(26.9, 0.0, -5.4), 2.1, delta)

func _build_house_interior() -> void:
	if _house_root != null:
		return
	_house_root = Node3D.new()
	_house_root.name = "HouseInterior"
	add_child(_house_root)

	var floor_color := Color(0.23, 0.2, 0.18, 1)
	var wall_color := Color(0.7, 0.66, 0.62, 1)
	var trim_color := Color(0.3, 0.28, 0.26, 1)

	_add_box_static(_house_root, "Floor", Vector3(0, -0.12, 10.4), Vector3(8.6, 0.24, 7.2), floor_color)
	_add_box_static(_house_root, "Ceiling", Vector3(0, 2.76, 10.4), Vector3(8.6, 0.18, 7.2), trim_color)
	_add_box_static(_house_root, "WallLeft", Vector3(-4.28, 1.32, 10.4), Vector3(0.25, 2.64, 7.2), wall_color)
	_add_box_static(_house_root, "WallRight", Vector3(4.28, 1.32, 10.4), Vector3(0.25, 2.64, 7.2), wall_color)
	_add_box_static(_house_root, "WallBack", Vector3(0, 1.32, 13.92), Vector3(8.6, 2.64, 0.25), wall_color)
	_add_box_static(_house_root, "WallFrontLeft", Vector3(-2.75, 1.32, 6.85), Vector3(3.1, 2.64, 0.25), wall_color)
	_add_box_static(_house_root, "WallFrontRight", Vector3(2.75, 1.32, 6.85), Vector3(3.1, 2.64, 0.25), wall_color)
	_add_box_static(_house_root, "WallFrontTop", Vector3(0, 2.35, 6.85), Vector3(2.1, 0.58, 0.25), wall_color)

	_add_box_static(_house_root, "CouchBase", Vector3(-2.25, 0.45, 11.9), Vector3(2.4, 0.5, 1.0), Color(0.44, 0.32, 0.3, 1))
	_add_box_static(_house_root, "CouchBack", Vector3(-2.25, 0.95, 12.32), Vector3(2.4, 0.55, 0.26), Color(0.42, 0.3, 0.28, 1))
	_add_box_static(_house_root, "CoffeeTable", Vector3(0.15, 0.35, 10.75), Vector3(1.35, 0.34, 0.8), Color(0.34, 0.24, 0.18, 1))
	_add_box_static(_house_root, "Counter", Vector3(2.8, 0.55, 12.55), Vector3(1.4, 0.9, 0.7), Color(0.55, 0.54, 0.56, 1))
	_add_box_static(_house_root, "Bed", Vector3(2.2, 0.5, 9.45), Vector3(2.1, 0.6, 1.4), Color(0.4, 0.48, 0.6, 1))
	_add_box_decor(_house_root, "Rug", Vector3(-0.1, 0.02, 10.55), Vector3(3.5, 0.04, 2.0), Color(0.7, 0.25, 0.25, 1))
	_add_box_decor(_house_root, "PhotoWall", Vector3(0, 1.65, 13.74), Vector3(2.8, 1.2, 0.04), Color(0.86, 0.82, 0.78, 1))

func _recover_fallen_companions() -> void:
	if yuki != null and yuki.global_position.y < -2.5:
		yuki.global_position = player.global_position + Vector3(-1.2, 0.0, 1.0)
	if saiya != null and saiya.global_position.y < -2.5:
		saiya.global_position = player.global_position + Vector3(1.2, 0.0, 1.0)
	if rival_dog_a != null and rival_dog_a.global_position.y < -2.5:
		rival_dog_a.global_position = Vector3(26.8, 0.0, -10.6)
	if rival_dog_b != null and rival_dog_b.global_position.y < -2.5:
		rival_dog_b.global_position = Vector3(27.2, 0.0, -7.8)
	if rival_dog_c != null and rival_dog_c.global_position.y < -2.5:
		rival_dog_c.global_position = Vector3(26.9, 0.0, -5.4)

func _add_box_static(parent: Node3D, name: String, pos: Vector3, size: Vector3, color: Color) -> StaticBody3D:
	var body := StaticBody3D.new()
	body.name = name
	body.position = pos
	parent.add_child(body)
	var shape := BoxShape3D.new()
	shape.size = size
	var collision := CollisionShape3D.new()
	collision.shape = shape
	body.add_child(collision)
	var mesh := BoxMesh.new()
	mesh.size = size
	var mesh_instance := MeshInstance3D.new()
	mesh_instance.mesh = mesh
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.roughness = 0.72
	mesh_instance.set_surface_override_material(0, mat)
	body.add_child(mesh_instance)
	return body

func _add_box_decor(parent: Node3D, name: String, pos: Vector3, size: Vector3, color: Color) -> MeshInstance3D:
	var mesh := BoxMesh.new()
	mesh.size = size
	var mesh_instance := MeshInstance3D.new()
	mesh_instance.name = name
	mesh_instance.position = pos
	mesh_instance.mesh = mesh
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.roughness = 0.7
	mesh_instance.set_surface_override_material(0, mat)
	parent.add_child(mesh_instance)
	return mesh_instance

func _update_director_missions(delta: float) -> void:
	_recent_bark_timer = max(0.0, _recent_bark_timer - delta)
	if hud == null or not hud.has_method("set_side_mission"):
		return
	if _game_finished or _story_chapter < 2:
		_director_mission_active = false
		_director_mission_id = "none"
		_side_mission_text = ""
		hud.set_side_mission("", false)
		return

	if _director_mission_active:
		_tick_director_mission(delta)
		return

	_director_mission_cooldown = max(0.0, _director_mission_cooldown - delta)
	if _director_mission_cooldown > 0.0:
		hud.set_side_mission("", false)
		return

	var start_rate := (0.04 + _encounter_heat * 0.12) * _encounter_multiplier()
	if randf() < delta * start_rate:
		_start_director_mission()
		if not _director_mission_active:
			hud.set_side_mission("", false)
	else:
		hud.set_side_mission("", false)

func _start_director_mission() -> void:
	var in_park := _is_in_dog_park()
	var near_fence := false
	if dog_park_fence != null:
		near_fence = player.global_position.distance_to(dog_park_fence.global_position) < 11.0
	var near_patrol_path := player.global_position.distance_to(Vector3(13.0, 0.0, -5.0)) < 16.0 or near_fence

	# Do not start missions in contexts that cannot be completed.
	if not in_park and not near_patrol_path:
		_director_mission_active = false
		_director_mission_id = "none"
		_director_mission_cooldown = 4.0
		return

	_director_mission_active = true
	_director_mission_stage = 0
	_director_mission_timer = 0.0
	_director_mission_fail_timer = 30.0

	if _park_rep_tier == "Tense" or _park_rep_tier == "Rival":
		_director_mission_id = "peace_walk"
		_director_mission_timer = 18.0
		_director_mission_fail_timer = 36.0
		_show_hint("Director mission: Peace Walk. Stay calm in the park and do not bark.")
	elif _encounter_tier == "hot" or _encounter_tier == "chaos":
		_director_mission_id = "sentry_hold"
		_director_mission_timer = 14.0
		_director_mission_fail_timer = 30.0
		_show_hint("Director mission: Sentry Hold. Set Guard mode and hold the fence line.")
	else:
		_director_mission_id = "patrol_loop"
		_director_mission_fail_timer = 38.0
		_show_hint("Director mission: Patrol Loop. Hit Park Edge then Fence Line.")

func _tick_director_mission(delta: float) -> void:
	_director_mission_fail_timer = max(0.0, _director_mission_fail_timer - delta)
	if _director_mission_fail_timer <= 0.0:
		_fail_director_mission("timed out")
		return

	if _director_mission_id == "peace_walk":
		if _recent_bark_timer > 0.0:
			_fail_director_mission("barked during peace walk")
			return
		if _is_in_dog_park():
			_director_mission_timer -= delta
		_side_mission_text = "Side Mission: Peace Walk %ds (no bark) | Fail in %ds" % [max(0, int(ceil(_director_mission_timer))), max(0, int(ceil(_director_mission_fail_timer)))]
		hud.set_side_mission(_side_mission_text, true)
		if _director_mission_timer <= 0.0:
			_complete_director_mission("peace walk")
		return

	if _director_mission_id == "sentry_hold":
		var fence := dog_park_fence.global_position if dog_park_fence != null else Vector3(22, 0, -8)
		var holding := _companion_mode == "guard" and _is_in_dog_park() and player.global_position.distance_to(fence) < 10.5
		if holding:
			_director_mission_timer -= delta
		_side_mission_text = "Side Mission: Sentry Hold %ds (Guard near fence) | Fail in %ds" % [max(0, int(ceil(_director_mission_timer))), max(0, int(ceil(_director_mission_fail_timer)))]
		hud.set_side_mission(_side_mission_text, true)
		if _director_mission_timer <= 0.0:
			_complete_director_mission("sentry hold")
		return

	if _director_mission_id == "patrol_loop":
		var park_edge := Vector3(13.0, 0.0, -5.0)
		var fence_line := dog_park_fence.global_position if dog_park_fence != null else Vector3(22, 0.0, -8.0)
		if _director_mission_stage == 0:
			_side_mission_text = "Side Mission: Patrol Loop 1/2 (Park Edge) | Fail in %ds" % [max(0, int(ceil(_director_mission_fail_timer)))]
			if player.global_position.distance_to(park_edge) < 2.8:
				_director_mission_stage = 1
				_show_hint("Patrol checkpoint 1 complete. Push to Fence Line.")
		else:
			_side_mission_text = "Side Mission: Patrol Loop 2/2 (Fence Line) | Fail in %ds" % [max(0, int(ceil(_director_mission_fail_timer)))]
			if player.global_position.distance_to(fence_line) < 2.8:
				_complete_director_mission("patrol loop")
				return
		hud.set_side_mission(_side_mission_text, true)
		return

	_fail_director_mission("unknown mission state")

func _complete_director_mission(name: String) -> void:
	_director_mission_active = false
	_director_mission_id = "none"
	_director_mission_timer = 0.0
	_director_mission_fail_timer = 0.0
	_director_mission_stage = 0
	_director_mission_cooldown = 22.0
	_director_missions_completed += 1
	_director_mission_points += 5
	player.add_treats(2)
	_adjust_park_reputation(4, "director " + name)
	_side_mission_text = ""
	hud.set_side_mission("", false)
	_show_hint("Director mission complete: %s (+2 treats, +rep)." % name.capitalize())

func _fail_director_mission(reason: String) -> void:
	_director_mission_active = false
	_director_mission_id = "none"
	_director_mission_timer = 0.0
	_director_mission_fail_timer = 0.0
	_director_mission_stage = 0
	_director_mission_cooldown = 15.0
	_director_mission_points = max(0, _director_mission_points - 1)
	_adjust_park_reputation(-2, "director fail")
	_side_mission_text = ""
	hud.set_side_mission("", false)
	_show_hint("Director mission failed: %s." % reason.capitalize())

func _check_landmarks() -> void:
	var marks := {
		"home_block": _spawn_position,
		"n_tenth_st": Vector3(0, 0.0, 8.6),
		"maple_crossing": Vector3(-8.5, 0.0, 1.8),
		"storefront_corner": Vector3(8, 0.0, 0),
		"park_edge": Vector3(13.0, 0.0, -5.0),
		"dog_park_gate": Vector3(22, 0.0, -2.6),
		"fence_line": dog_park_fence.global_position if dog_park_fence != null else Vector3(22, 0.0, -8),
		"park": park_zone.global_position if park_zone != null else Vector3.ZERO,
		"roof": Vector3(6, 3.4, -14)
	}
	var landmark_names := {
		"home_block": "Home Block",
		"n_tenth_st": "N Tenth St",
		"maple_crossing": "Maple Crossing",
		"storefront_corner": "Storefront Corner",
		"park_edge": "Park Edge",
		"dog_park_gate": "Dog Park Gate",
		"fence_line": "Fence Line",
		"park": "Pocket Park",
		"roof": "Rooftop Route"
	}
	for key in marks.keys():
		if _discovered_landmarks.has(key):
			continue
		if player.global_position.distance_to(marks[key]) < 2.8:
			_discovered_landmarks[key] = true
			player.add_treats(1)
			_show_hint("Landmark discovered: %s (+1 treat)" % String(landmark_names.get(key, key)))
			_update_memory_route_progress(key)

func _update_memory_route_progress(_key: String) -> void:
	var previous := _memory_route_progress
	var progress := 0
	if _discovered_landmarks.has("n_tenth_st"):
		progress = 1
		if _discovered_landmarks.has("storefront_corner"):
			progress = 2
			if _discovered_landmarks.has("dog_park_gate"):
				progress = 3
				if _discovered_landmarks.has("fence_line"):
					progress = 4

	_memory_route_progress = progress
	if previous < 1 and progress >= 1:
		_show_hint("Route memory: N Tenth St locked in.")
	if previous < 2 and progress >= 2:
		_show_hint("Route memory: turned at the storefront corner.")
	if previous < 3 and progress >= 3:
		_show_hint("Route memory: reached the Poplar Bluff dog park.")
	if previous < 4 and progress >= 4:
		_affinity_yuki += 1
		_affinity_saiya += 1
		player.add_treats(2)
		_show_hint("Memory route complete. Kai, Yuki, and Saiya rallied to the fence line (+2 treats).")

func _update_mood_state(delta: float) -> void:
	_mood_eval_timer += delta
	if _mood_eval_timer < 0.35:
		return
	_mood_eval_timer = 0.0

	var kai_target := 0.24
	if _come_inside_active or _chase_active:
		kai_target += 0.38
	if _fence_warrior_mode:
		kai_target += 0.34
	if _companion_mode == "scout":
		kai_target += 0.2
	_kai_mischief = clamp(lerpf(_kai_mischief, kai_target, 0.24), 0.0, 1.0)
	if _kai_mischief > 0.72:
		_kai_mood = "chaotic"
	elif _kai_mischief > 0.43:
		_kai_mood = "curious"
	else:
		_kai_mood = "calm"

	var yuki_target := 0.44
	if _companion_mode == "search":
		yuki_target += 0.22
	if player.sniff_mode:
		yuki_target += 0.11
	if trash_can != null and yuki != null and yuki.global_position.distance_to(trash_can.global_position) < 3.5:
		yuki_target += 0.16
	_yuki_curiosity = clamp(lerpf(_yuki_curiosity, yuki_target, 0.22), 0.0, 1.0)
	if _yuki_curiosity > 0.7:
		_yuki_mood = "curious"
	elif _yuki_curiosity > 0.45:
		_yuki_mood = "focused"
	else:
		_yuki_mood = "calm"

	var saiya_target := 0.46
	if _companion_mode == "guard" or _companion_mode == "sentry":
		saiya_target += 0.18
	if _is_in_dog_park():
		saiya_target += 0.12
	if _fence_warrior_mode or _chase_active:
		saiya_target += 0.2
	_saiya_guarding = clamp(lerpf(_saiya_guarding, saiya_target, 0.23), 0.0, 1.0)
	if _saiya_guarding > 0.73:
		_saiya_mood = "protective"
	elif _saiya_guarding > 0.47:
		_saiya_mood = "focused"
	else:
		_saiya_mood = "calm"

func _refresh_status_panel() -> void:
	if hud == null or not hud.has_method("set_status"):
		return
	if _come_inside_active:
		var event_status := "Event: Keep-away active | Kai:%s | Catch radius: %.1fm" % [_kai_mood, _come_inside_catch_distance]
		if event_status != _last_status_text:
			_last_status_text = event_status
			hud.set_status(event_status)
		return
	var mode_name := _companion_mode.capitalize()
	var sniff_text := "off"
	if player.sniff_mode:
		sniff_text = _scent_target_kind.capitalize() if _scent_target_kind != "none" else "active"
	var morning_text := ""
	if _story_chapter == 0 and not _morning_complete:
		morning_text = " | Morning:%d/4" % [min(4, _morning_step + 1)]
	var status := "Cmd:%s | Kai:%s | Yuki:%s | Saiya:%s | Sniff:%s | Park:%s | Tempo:%s | Ops:%d%s | Keys 1-6" % [mode_name, _kai_mood, _yuki_mood, _saiya_mood, sniff_text, _park_rep_tier, _encounter_tier.capitalize(), _director_mission_points, morning_text]
	if status == _last_status_text:
		return
	_last_status_text = status
	hud.set_status(status)

func _build_day_recap() -> String:
	var recap := "DAY RECAP\n"
	recap += "Chapter: %d complete\n" % [_story_chapter]
	recap += "Treats: %d\n" % [player.treats]
	recap += "Squirrel chases won: %d\n" % [_chases_won]
	recap += "Rare finds: %d\n" % [_rare_items_found]
	recap += "Dog park reputation: %s (%d)\n" % [_park_rep_tier, _park_reputation]
	recap += "Director ops: %d complete / %d points\n" % [_director_missions_completed, _director_mission_points]
	recap += "Companion affinity: Yuki %d / Saiya %d" % [_affinity_yuki, _affinity_saiya]
	return recap

func _ensure_scent_trail_root() -> void:
	if _scent_trail_root != null:
		return
	_scent_trail_root = Node3D.new()
	_scent_trail_root.name = "ScentTrail"
	add_child(_scent_trail_root)

func _update_sniff_trail(delta: float) -> void:
	_ensure_scent_trail_root()
	if not player.sniff_mode:
		_clear_scent_trail()
		_scent_target_kind = "none"
		return
	_scent_trail_refresh -= delta
	if _scent_trail_refresh > 0.0:
		return
	_scent_trail_refresh = 0.15
	var picked := _pick_scent_target()
	_scent_target_kind = String(picked.get("kind", "none"))
	_scent_target_pos = picked.get("pos", Vector3.ZERO)
	if _scent_target_kind == "none":
		_clear_scent_trail()
		return
	_render_scent_trail(_scent_target_pos, _scent_target_kind)

func _pick_scent_target() -> Dictionary:
	if _story_chapter == 0 and not _morning_complete:
		return {"kind": "home", "pos": _morning_target_position()}

	var completed_key := "%s_completed" % _quest_id
	var quest_complete = player.has_meta(completed_key) and player.get_meta(completed_key) == true
	var found_item = player.has_meta(_quest_id) and player.get_meta(_quest_id) == true
	if not found_item and not quest_complete:
		var best_item: Node3D = null
		var best_dist := INF
		for node in get_tree().get_nodes_in_group("quest_item"):
			if "collected" in node and node.collected:
				continue
			if node is Node3D:
				var dist := player.global_position.distance_to(node.global_position)
				if dist < best_dist:
					best_dist = dist
					best_item = node as Node3D
		if best_item != null:
			return {"kind": "quest", "pos": best_item.global_position}

	if _companion_mode == "search" and trash_can != null:
		return {"kind": "trash", "pos": trash_can.global_position}

	if _story_chapter >= 3:
		return {"kind": "home", "pos": _spawn_position}

	if _story_chapter == 2 and _squirrel_active and _squirrel != null:
		return {"kind": "squirrel", "pos": _squirrel.global_position}

	var best_treat: Node3D = null
	var best_dist_treat := INF
	for node in get_tree().get_nodes_in_group("treat"):
		if "collected" in node and node.collected:
			continue
		if node is Node3D:
			var dist_treat := player.global_position.distance_to(node.global_position)
			if dist_treat < best_dist_treat:
				best_dist_treat = dist_treat
				best_treat = node as Node3D
	if best_treat != null:
		return {"kind": "treat", "pos": best_treat.global_position}

	return {"kind": "none", "pos": Vector3.ZERO}

func _clear_scent_trail() -> void:
	if _scent_trail_root == null:
		return
	for child in _scent_trail_root.get_children():
		_scent_trail_root.remove_child(child)
		child.queue_free()

func _render_scent_trail(target_pos: Vector3, scent_kind: String) -> void:
	if _scent_trail_root == null:
		return
	_clear_scent_trail()
	var marker_color := _scent_color(scent_kind)
	var marker_count := 7
	for i in range(marker_count):
		var t := float(i + 1) / float(marker_count + 1)
		var marker := MeshInstance3D.new()
		var mesh := SphereMesh.new()
		mesh.radius = 0.11
		mesh.height = 0.22
		marker.mesh = mesh
		var mat := StandardMaterial3D.new()
		mat.albedo_color = marker_color
		mat.emission_enabled = true
		mat.emission = marker_color * 0.45
		marker.set_surface_override_material(0, mat)
		var pos := player.global_position.lerp(target_pos, t)
		pos.y = 0.24 + sin(float(i) * 0.7) * 0.06
		marker.global_position = pos
		_scent_trail_root.add_child(marker)

func _scent_color(kind: String) -> Color:
	if kind == "quest":
		return Color(0.92, 0.75, 0.18, 1)
	if kind == "home":
		return Color(0.4, 0.82, 0.95, 1)
	if kind == "squirrel":
		return Color(0.95, 0.5, 0.2, 1)
	if kind == "trash":
		return Color(0.44, 0.86, 0.44, 1)
	return Color(0.78, 0.42, 0.94, 1)

func _update_bark_cooldown(delta: float) -> void:
	_bark_cooldown = max(0.0, _bark_cooldown - delta)

func _restore_pickups() -> void:
	for node in get_tree().get_nodes_in_group("treat"):
		if node.has_method("reset_pickup"):
			node.reset_pickup()
			if "pickup_id" in node and _collected_pickups.has(node.pickup_id) and node.has_method("set_collected_state"):
				node.set_collected_state(true)
	for node in get_tree().get_nodes_in_group("quest_item"):
		if node.has_method("reset_pickup"):
			node.reset_pickup()
			if "pickup_id" in node and _collected_pickups.has(node.pickup_id) and node.has_method("set_collected_state"):
				node.set_collected_state(true)

func _update_autosave(delta: float) -> void:
	_autosave_timer += delta
	if _autosave_timer >= _autosave_interval:
		_autosave_timer = 0.0
		_save_progress(true)

func _setup_fence_slots() -> void:
	if dog_park_fence == null:
		return
	var base := dog_park_fence.global_position
	_fence_line_slot_yuki = base + Vector3(-0.8, 0, -2.6)
	_fence_line_slot_kai = base + Vector3(-0.8, 0, 0.0)
	_fence_line_slot_saiya = base + Vector3(-0.8, 0, 2.6)

func _is_in_dog_park() -> bool:
	if dog_park_small == null and dog_park_big == null:
		return false
	var in_small := dog_park_small != null and player.global_position.distance_to(dog_park_small.global_position) < 9.5
	var in_big := dog_park_big != null and player.global_position.distance_to(dog_park_big.global_position) < 9.5
	var in_fence_lane := dog_park_fence != null and player.global_position.distance_to(dog_park_fence.global_position) < 7.0
	return in_small or in_big or in_fence_lane

func _start_fence_warrior_mode() -> void:
	_fence_warrior_mode = true
	_fence_warrior_seen = true
	_saiya_guarding = clamp(_saiya_guarding + 0.04, 0.0, 1.0)
	_kai_mischief = clamp(_kai_mischief + 0.03, 0.0, 1.0)
	_encounter_heat = clamp(_encounter_heat + 0.16, 0.0, 1.0)
	_adjust_park_reputation(-4, "fence clash")
	_fence_warrior_timer = 7.5
	_fence_event_cooldown = 22.0
	_show_hint("Fence warrior mode. Everyone rushed the fence line.")
	if bark_player != null:
		bark_player.play()
	_update_objective()

func _update_dog_park_event(delta: float) -> void:
	_fence_event_cooldown = max(0.0, _fence_event_cooldown - delta)
	var rep_pressure = clamp(float(-_park_reputation) / 100.0, 0.0, 1.0)
	var fence_rate = (0.14 + rep_pressure * 0.2) * _encounter_multiplier()
	if _is_in_dog_park() and _fence_event_cooldown <= 0.0 and randf() < delta * fence_rate:
		_start_fence_warrior_mode()
	if not _fence_warrior_mode:
		return
	_fence_warrior_timer -= delta
	if int(_fence_warrior_timer * 10.0) % 17 == 0 and bark_player != null:
		bark_player.play()
	if _fence_warrior_timer <= 0.0:
		_fence_warrior_mode = false
		_adjust_park_reputation(1, "cooldown")
		_show_hint("Fence warrior stand-off cooled down. Back to patrol.")
