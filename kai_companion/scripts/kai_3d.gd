extends Node

const WS_URL := "ws://127.0.0.1:8765"
const KAI_CHAT_URL := "http://127.0.0.1:8127/api/chat"
const OLLAMA_URL := "http://127.0.0.1:11434/api/chat"
const KAI_BARK_1_PATH := "res://assets/kai/audio/kai_bark_1.wav"
const KAI_BARK_2_PATH := "res://assets/kai/audio/kai_bark_2.wav"
const KAI_SNIFF_PATH := "res://assets/kai/audio/kai_sniff.wav"
const KAI_WAG_PATH := "res://assets/kai/audio/kai_wag.wav"
const KAI_HUFF_PATH := "res://assets/kai/audio/kai_huff.wav"
const KAI_PAW_PATH := "res://assets/kai/audio/kai_paw.wav"
const KAI_SIGH_PATH := "res://assets/kai/audio/kai_sigh.wav"
const KAI_CANONICAL_MODEL_PATH := "res://assets/kai/kai_textured.glb"
const KAI_RIG_TARGET_PATH := "res://assets/kai/kai_textured_rigged.glb"
const KAI_MOTION_REFERENCE_PATH := "res://assets/kai/kai-lite.glb"
const KAI_FALLBACK_ALBEDO_TEXTURE_PATH := "res://assets/kai/kai_textured_kai_texture_paint.png"
const KAI_HOLOGRAM_SHADER_PATH := "res://assets/kai/kai_hologram.gdshader"
const WINDOW_SIZE := Vector2(340, 420)
const TARGET_FPS := 30
const SOCKET_RETRY_BASE := 1.6
const SOCKET_RETRY_MAX := 12.0
const SOCKET_RETRY_JITTER := 0.6
const SOCKET_POLL_INTERVAL := 0.10
const AMBIENT_UPDATE_INTERVAL := 0.20
const MAX_CHAT_HISTORY := 12
const WALK_SPEED_MIN := 52.0
const WALK_SPEED_MAX := 108.0
const WALK_PAUSE_MIN := 4.2
const WALK_PAUSE_MAX := 9.0
const DESKTOP_MARGIN := 18.0
const LOCOMOTION_ACCEL := 520.0
const LOCOMOTION_BRAKE := 760.0
const LOCOMOTION_SLOW_RADIUS := 120.0
const LOCOMOTION_ARRIVAL_RADIUS := 3.0
const LOCOMOTION_STOP_SPEED := 9.0
const MODEL_YAW_OFFSET := -PI * 0.5
const STATIC_LAYDOWN_ROLL_FIX := PI * 0.5
const MODEL_BLEND_DURATION := 0.28
const TURN_SMOOTH_SPEED := 3.2
const HOLD_IDLE := 0.22
const HOLD_ALERT := 0.45
const HOLD_WALK := 0.45
const HOLD_REST := 1.2
const HOLD_WAG := 0.35
const HOLD_THINKING := 0.25
const HOLD_SNIFF := 0.75
const HOLD_BARK := 0.55
const ZOOMY_SPEED_MULTIPLIER := 1.45
const ZOOMY_TRIGGER_CHANCE := 0.04
const ALERT_TRIGGER_CHANCE := 0.14
const ALERT_HOLD_MIN := 0.7
const ALERT_HOLD_MAX := 1.6
const CURSOR_REACT_DISTANCE := 82.0
const INTERACTION_COOLDOWN_MIN := 5.5
const INTERACTION_COOLDOWN_MAX := 10.0
const WATCH_POST_HOLD_MIN := 3.5
const WATCH_POST_HOLD_MAX := 7.5
const INVESTIGATE_TARGET_HOLD := 7.0
const INVESTIGATE_APPROACH_DISTANCE := 220.0
const RECENT_TARGET_DISTANCE := 96.0
const TERRITORY_IDLE_MIN := 2.2
const TERRITORY_IDLE_MAX := 5.8
const HOME_CHECK_TRIGGER_CHANCE := 0.28
const DOORWAY_SWEEP_TRIGGER_CHANCE := 0.24
const SNIFF_LINGER_MIN := 2.4
const SNIFF_LINGER_MAX := 5.2
const BARK_TRIGGER_CHANCE := 0.09
const BARK_COOLDOWN_MIN := 6.0
const BARK_COOLDOWN_MAX := 11.5

@export var ollama_model: String = "qwen3:4b-q4_K_M"
@export var use_hologram_material: bool = false
@export var prefer_rigged_avatar: bool = true

@onready var model_anchor: Node3D = $World/ModelAnchor
@onready var bubble: PanelContainer = $UI/Root/Bubble
@onready var bubble_label: Label = $UI/Root/Bubble/BubbleLabel
@onready var mood_label: Label = $UI/Root/TopBar/MoodLabel
@onready var status_label: Label = $UI/Root/TopBar/StatusLabel
@onready var chat_toggle: Button = $UI/Root/ActionBar/ChatToggle
@onready var pet_button: Button = $UI/Root/ActionBar/PetButton
@onready var walk_button: Button = $UI/Root/ActionBar/WalkButton
@onready var chat_overlay: PanelContainer = $UI/Root/ChatOverlay
@onready var chat_log: RichTextLabel = $UI/Root/ChatOverlay/ChatVBox/ChatLog
@onready var chat_input: LineEdit = $UI/Root/ChatOverlay/ChatVBox/InputRow/ChatInput
@onready var voice_button: Button = $UI/Root/ChatOverlay/ChatVBox/InputRow/VoiceButton
@onready var send_button: Button = $UI/Root/ChatOverlay/ChatVBox/InputRow/SendButton
@onready var request: HTTPRequest = $UI/Root/HTTPRequest
@onready var bark_player: AudioStreamPlayer = $BarkPlayer

var _socket := WebSocketPeer.new()
var _socket_retry_at := 0.0
var _socket_retry_delay := SOCKET_RETRY_BASE
var _socket_poll_elapsed := 0.0
var _ambient_update_elapsed := 0.0
var _bubble_timeout := 0.0
var _dragging := false
var _drag_offset := Vector2.ZERO
var _request_in_flight := false
var _chat_request_backend := "kai_server"
var _pending_chat_message := ""
var _time := 0.0
var _state := "idle"
var _state_time := 0.0
var _frame_delta := 0.016
var _rest_timer := 0.0
var _rest_duration := 0.0
var _walk_target := Vector2.ZERO
var _walk_speed := 0.0
var _walk_pause := 0.0
var _walk_facing := 1.0
var _yaw_current := 0.0
var _yaw_target := 0.0
var _locomotion_velocity := Vector2.ZERO
var _locomotion_smoothed_speed := 0.0
var _alert_hold := 0.0
var _interaction_cooldown := 0.0
var _cursor_world := Vector2.ZERO
var _status_text := "ready"
var _chat_history: Array[Dictionary] = []
var _model_root: Node3D
var _model_animation_player: AnimationPlayer
var _known_animations: PackedStringArray = []
var _hologram_shader: Shader
var _fallback_albedo_texture: Texture2D
var _active_model_path := ""
var _has_walk_animation := false
var _watch_post_timer := 0.0
var _interest_target := Vector2.ZERO
var _interest_timer := 0.0
var _walk_intent := "patrol"
var _home_anchor := Vector2.ZERO
var _recent_targets: Array[Vector2] = []
var _guard_target := Vector2.ZERO
var _bark_sounds: Array[AudioStream] = []
var _sniff_sound: AudioStream
var _wag_sound: AudioStream
var _huff_sound: AudioStream
var _paw_sound: AudioStream
var _sigh_sound: AudioStream
var _proactive_timer := 0.0

const AMBIENT_LINES := [
    "Watching the room like it is my yard.",
    "Busy little Shiba patrol underway.",
    "Independent face. Loyal intentions.",
    "Leash still on. Escape plan still active.",
    "Keeping an eye on things. That's my job.",
    "Tail status: cautiously optimistic.",
    "I see everything. I just pretend I don't.",
    "Professional surveillance mode.",
    "One ear up. Listening for trouble.",
    "Quiet now. Thinking about snacks.",
]

const PET_LINES := [
    "Mrrf. Acceptable. Keep going.",
    "Tail says yes. Face says act natural.",
    "I was patrolling, but this is fine.",
    "This is beneath my dignity. Continue anyway.",
    "Fine. You may touch the Shiba.",
    "Sigh. I love you too.",
    "Professional stoicism... failing.",
]

const NOTICE_LINES := [
    "Sniff check.",
    "Something moved. Probably important.",
    "Just checking the room again.",
    "Ears up. Something's interesting.",
    "Hold on. Processing stimulus.",
    "My ears work. Unlike my obedience.",
]

const SNIFF_LINES := [
    "Sniffing the perimeter.",
    "Hold on. Scent check.",
    "This spot needs a proper inspection.",
    "Nose says: investigate further.",
    "Sniff sniff. Data collected.",
]

const BARK_LINES := [
    "Woof. I saw that.",
    "Alert bark issued.",
    "Tiny bark. Big security energy.",
    "Bark dispatched. Threat level: unknown.",
    "Consider yourself warned.",
]

const ZOOMY_LINES := [
    "Tiny security sprint. Very serious business.",
    "Zoom check. Floor approved.",
    "Quick patrol burst. No questions.",
    "Speed run. Don't read into it.",
    "I have the zoomies. Professionally.",
]

const SLEEP_LINES := [
    "Resting with one eye open.",
    "Resting with one eye open.",
    "Power nap. Security continues.",
    "Sleep mode. Ears still active.",
    "Recharging the loyalty batteries.",
]

const OFFLINE_REPLY_LINES := [
    "I'm here in desktop mate mode. Ollama is asleep, but I can still hang out.",
    "The local model is offline, so I'm running as a standalone Kai companion right now.",
    "Brain link is offline for the moment. The avatar part is still here and steady.",
]

const MODEL_BASE_POSITION := Vector3(0.0, -0.92, 0.0)
const MODEL_BASE_SCALE := 1.50
const NON_WALK_YAW_OFFSET := 0.0
const BREATH_IDLE_RATE := 1.15
const BREATH_SIT_RATE := 1.2
const BREATH_REST_RATE := 0.95
const WALK_STEP_RATE := 7.8
const ENABLE_CURSOR_REACTIONS := false
const BASE_PITCH_OFFSET := -0.045

# Pose blending — smooth transitions between states
const POSE_BLEND_SPEED := 3.5
var _pose_blend := 0.0
var _ear_twitch_timer := 0.0
var _ear_twitch_side := 0.0


func _ready() -> void:
    _load_config()
    _configure_desktop_window()
    _load_3d_model()
    _load_companion_audio()
    _seed_history()
    _set_chat_overlay_visible(false)
    request.request_completed.connect(_on_request_completed)
    chat_toggle.pressed.connect(_toggle_chat_overlay)
    send_button.pressed.connect(_send_chat_message)
    chat_input.text_submitted.connect(_on_input_submitted)
    pet_button.pressed.connect(_on_pet_pressed)
    walk_button.pressed.connect(_on_walk_pressed)
    voice_button.pressed.connect(_on_voice_pressed)
    if request.has_method("set_timeout"):
        request.set_timeout(35)
    _home_anchor = Vector2(DisplayServer.window_get_position())
    _socket_retry_at = Time.get_unix_time_from_system() + randf_range(0.2, 0.8)
    _walk_pause = randf_range(3.0, 6.0)
    _rest_duration = randf_range(4.5, 7.5)
    _walk_target = Vector2(DisplayServer.window_get_position())
    _update_mood_display("Calm")
    _proactive_timer = randf_range(300.0, 600.0)


func _load_config() -> void:
    var config_path = "res://../../../shared/kai_config.json"
    if FileAccess.file_exists(config_path):
        var config_text = FileAccess.get_file_as_string(config_path)
        var config = JSON.parse_string(config_text)
        if config:
            use_hologram_material = config.avatar.use_hologram
            prefer_rigged_avatar = config.avatar.prefer_rigged
            # Update chat URLs if needed
            # For now, keep hardcoded but could be extended


func _process(delta: float) -> void:
    _frame_delta = delta
    _time += delta
    _state_time += delta
    _alert_hold = max(0.0, _alert_hold - delta)
    _interaction_cooldown = max(0.0, _interaction_cooldown - delta)
    _bark_cooldown = max(0.0, _bark_cooldown - delta)
    _socket_poll_elapsed += delta
    _ambient_update_elapsed += delta
    _update_cursor()
    if _socket_poll_elapsed >= SOCKET_POLL_INTERVAL:
        _socket_poll_elapsed = 0.0
        _poll_socket()
    _update_desktop_patrol(delta)
    _update_bubble(delta)
    _update_model_pose()
    _update_cursor_reactions()
    _proactive_timer -= delta
    if _proactive_timer <= 0.0:
        _proactive_timer = randf_range(300.0, 600.0)
        var proactive_lines := [
            "You’ve been at this a while.",
            "Something changed.",
            "Want me to check that?",
            "I’m here.",
            "Quick sniff check."
        ]
        _set_bubble_text(proactive_lines[randi() % proactive_lines.size()], 4.0)


func _state_hold_duration(state_name: String) -> float:
    match state_name:
        "walk":
            return HOLD_WALK
        "alert":
            return HOLD_ALERT
        "rest":
            return HOLD_REST
        "wag_tail":
            return HOLD_WAG
        "thinking":
            return HOLD_THINKING
        "sniff":
            return HOLD_SNIFF
        "bark":
            return HOLD_BARK
        _:
            return HOLD_IDLE


func _set_state(next_state: String, force: bool = false) -> void:
    if _state == next_state:
        return
    if (not force) and _state_time < _state_hold_duration(_state):
        return
    _state = next_state
    _state_time = 0.0


func _input(event: InputEvent) -> void:
    if event.is_action_pressed("ui_cancel"):
        if chat_overlay.visible:
            _set_chat_overlay_visible(false)
            get_viewport().set_input_as_handled()
        return
    if event is InputEventMouseButton:
        var mouse_event := event as InputEventMouseButton
        if mouse_event.button_index == MOUSE_BUTTON_LEFT:
            if mouse_event.pressed and not chat_overlay.visible and not _ui_control_wants_mouse():
                _dragging = true
                _drag_offset = mouse_event.global_position - Vector2(DisplayServer.window_get_position())
                _set_state("wag_tail", true)
                _alert_hold = randf_range(0.35, 0.8)
                _set_bubble_text(PET_LINES[randi() % PET_LINES.size()], 2.6)
            elif not mouse_event.pressed:
                _dragging = false
        elif mouse_event.button_index == MOUSE_BUTTON_RIGHT and mouse_event.pressed:
            _toggle_chat_overlay()
    elif event is InputEventMouseMotion and _dragging:
        var motion_event := event as InputEventMouseMotion
        var next_position := motion_event.global_position - _drag_offset
        DisplayServer.window_set_position(Vector2i(next_position))
        _halt_locomotion()


func _toggle_chat_overlay() -> void:
    _set_chat_overlay_visible(not chat_overlay.visible)


func _ui_control_wants_mouse() -> bool:
    var hovered := get_viewport().gui_get_hovered_control()
    if hovered == null:
        return false
    if hovered == chat_toggle or hovered == pet_button or hovered == walk_button:
        return true
    if hovered == bubble:
        return true
    if chat_overlay.is_ancestor_of(hovered):
        return true
    return false


func _set_chat_overlay_visible(visible: bool) -> void:
    chat_overlay.visible = visible
    chat_toggle.text = "Chat"
    pet_button.text = "Pet"
    walk_button.text = "Walk"
    if visible:
        chat_input.grab_focus()
        _set_bubble_text("Ask Kai anything.")
        _update_mood_display("Thinking")
        return
    _dragging = false
    if chat_input.has_focus():
        chat_input.release_focus()
    _set_bubble_text("Tap Chat or right click to talk again.")
    _update_mood_display("Attentive")


# ─── Action Bar Handlers ───

func _on_pet_pressed() -> void:
    _set_state("wag_tail", true)
    _alert_hold = randf_range(0.35, 0.8)
    _set_bubble_text(PET_LINES[randi() % PET_LINES.size()], 3.0)
    _update_mood_display("Happy")
    _play_sound(_wag_sound)


func _on_walk_pressed() -> void:
    if _state == "walk":
        _halt_locomotion()
        _set_state("idle")
        _set_bubble_text("Stopping.", 2.0)
        _update_mood_display("Attentive")
    else:
        _begin_walk("patrol")
        _update_mood_display("Curious")


func _on_voice_pressed() -> void:
    # Placeholder for voice input — requires platform-specific STT
    _set_bubble_text("Voice input coming soon. Type for now!", 3.0)


# ─── Mood Display ───

func _update_mood_display(mood_text: String) -> void:
    if mood_label:
        mood_label.text = mood_text


func _configure_desktop_window() -> void:
    get_viewport().transparent_bg = true
    Engine.max_fps = TARGET_FPS
    DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_BORDERLESS, true)
    DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_ALWAYS_ON_TOP, true)
    DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_TRANSPARENT, true)
    DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_RESIZE_DISABLED, true)
    DisplayServer.window_set_size(Vector2i(int(WINDOW_SIZE.x), int(WINDOW_SIZE.y)))
    var screen_size := DisplayServer.screen_get_size()
    var screen_position := Vector2i(
        max(0, screen_size.x - int(WINDOW_SIZE.x) - 40),
        max(0, screen_size.y - int(WINDOW_SIZE.y) - 60)
    )
    DisplayServer.window_set_position(screen_position)


func _load_3d_model() -> void:
    var model_path := _resolve_model_path()
    var packed := load(model_path)
    if packed is not PackedScene:
        push_error("Kai canonical model failed to load: %s" % model_path)
        _set_bubble_text("Kai 3D model failed to load.")
        return
    var instance := (packed as PackedScene).instantiate()
    if instance is not Node3D:
        push_error("Kai canonical model was not a Node3D scene: %s" % model_path)
        _set_bubble_text("Kai 3D model failed to load.")
        return

    _model_root = instance as Node3D
    _model_root.name = "KaiModel"
    model_anchor.add_child(_model_root)
    _model_root.position = MODEL_BASE_POSITION
    _model_root.scale = Vector3.ONE * MODEL_BASE_SCALE
    _active_model_path = model_path
    _repair_missing_albedo_bindings(_model_root)
    if use_hologram_material:
        _apply_hologram_materials(_model_root)
    _model_animation_player = _find_first_animation_player(_model_root)
    if _model_animation_player != null:
        _known_animations = _model_animation_player.get_animation_list()
    _has_walk_animation = _animation_list_has_walk(_known_animations)
    _log_avatar_contract()

    _play_animation_prefer(["KAI_Idle_Breath", "KAI_Idle", "kai_idle", "idle", "stand", "rest", "RESET", "ArmatureAction"], 1.0)
    if _known_animations.is_empty():
        _set_bubble_text("Kai photo replica loaded. It still needs a proper rig.")
    elif not _has_walk_animation:
        _set_bubble_text("Kai photo replica loaded. Rig target is %s." % KAI_RIG_TARGET_PATH.get_file())
    else:
        _set_bubble_text("Kai 3D rig online.")


func _resolve_model_path() -> String:
    var override_path := OS.get_environment("KAI_3D_MODEL_OVERRIDE").strip_edges()
    if not override_path.is_empty():
        return override_path
    if OS.get_environment("KAI_USE_RIGGED_AVATAR").strip_edges() == "1" and ResourceLoader.exists(KAI_RIG_TARGET_PATH):
        return KAI_RIG_TARGET_PATH
    if prefer_rigged_avatar and ResourceLoader.exists(KAI_RIG_TARGET_PATH):
        return KAI_RIG_TARGET_PATH
    return KAI_CANONICAL_MODEL_PATH


func _log_avatar_contract() -> void:
    print(
        "[KAI_AVATAR] loaded=%s canonical=%s rig_target=%s motion_reference=%s walk_animation=%s"
        % [
            _active_model_path,
            KAI_CANONICAL_MODEL_PATH,
            KAI_RIG_TARGET_PATH,
            KAI_MOTION_REFERENCE_PATH,
            str(_has_walk_animation),
        ]
    )


func _find_first_animation_player(root: Node) -> AnimationPlayer:
    if root is AnimationPlayer:
        return root as AnimationPlayer
    for child in root.get_children():
        if child is Node:
            var found := _find_first_animation_player(child)
            if found != null:
                return found
    return null


func _apply_hologram_materials(root: Node) -> void:
    if _hologram_shader == null:
        _hologram_shader = load(KAI_HOLOGRAM_SHADER_PATH) as Shader
    if _hologram_shader == null or root == null:
        return
    if root is MeshInstance3D:
        var mesh_instance := root as MeshInstance3D
        var material := ShaderMaterial.new()
        material.shader = _hologram_shader
        mesh_instance.material_override = material
        mesh_instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
    for child in root.get_children():
        if child is Node:
            _apply_hologram_materials(child)


func _repair_missing_albedo_bindings(root: Node) -> void:
    if root == null:
        return
    if _fallback_albedo_texture == null:
        _fallback_albedo_texture = load(KAI_FALLBACK_ALBEDO_TEXTURE_PATH) as Texture2D
    if _fallback_albedo_texture == null:
        return
    if root is MeshInstance3D:
        var mesh_instance := root as MeshInstance3D
        var mesh := mesh_instance.mesh
        if mesh != null:
            for surface_idx in range(mesh.get_surface_count()):
                var source_material := mesh_instance.get_active_material(surface_idx)
                if source_material == null:
                    source_material = mesh.surface_get_material(surface_idx)
                if source_material is BaseMaterial3D:
                    var base_material := source_material as BaseMaterial3D
                    if base_material.albedo_texture == null:
                        var material_copy := base_material.duplicate(true) as BaseMaterial3D
                        if material_copy != null:
                            material_copy.albedo_texture = _fallback_albedo_texture
                            mesh_instance.set_surface_override_material(surface_idx, material_copy)
    for child in root.get_children():
        if child is Node:
            _repair_missing_albedo_bindings(child)


func _load_companion_audio() -> void:
    var bark_1 := _load_wav_stream(KAI_BARK_1_PATH)
    var bark_2 := _load_wav_stream(KAI_BARK_2_PATH)
    if bark_1 != null:
        _bark_sounds.append(bark_1)
    if bark_2 != null:
        _bark_sounds.append(bark_2)
    _sniff_sound = _load_wav_stream(KAI_SNIFF_PATH)
    _wag_sound = _load_wav_stream(KAI_WAG_PATH)
    _huff_sound = _load_wav_stream(KAI_HUFF_PATH)
    _paw_sound = _load_wav_stream(KAI_PAW_PATH)
    _sigh_sound = _load_wav_stream(KAI_SIGH_PATH)


func _play_sound(stream: AudioStream) -> void:
    if stream == null or bark_player == null:
        return
    bark_player.stream = stream
    bark_player.play()


func _load_wav_stream(path: String) -> AudioStreamWAV:
    var file := FileAccess.open(path, FileAccess.READ)
    if file == null:
        return null
    var bytes := file.get_buffer(file.get_length())
    if bytes.size() <= 44:
        return null
    var stream := AudioStreamWAV.new()
    stream.format = AudioStreamWAV.FORMAT_16_BITS
    stream.mix_rate = 22050
    stream.stereo = false
    stream.data = bytes.slice(44)
    return stream


func _play_bark() -> void:
    if _bark_sounds.is_empty() or bark_player == null or _bark_cooldown > 0.0:
        return
    bark_player.stream = _bark_sounds[randi() % _bark_sounds.size()]
    bark_player.play()
    _bark_cooldown = randf_range(BARK_COOLDOWN_MIN, BARK_COOLDOWN_MAX)




func _pick_animation_name(candidates: Array[String]) -> String:
    if _model_animation_player == null or _known_animations.is_empty():
        return ""
    for name in candidates:
        if _model_animation_player.has_animation(name):
            return name

    var candidate_keywords: PackedStringArray = []
    for candidate in candidates:
        var normalized := candidate.to_lower().strip_edges()
        if not normalized.is_empty():
            candidate_keywords.append(normalized)

    for known_name in _known_animations:
        var normalized_known := known_name.to_lower()
        for keyword in candidate_keywords:
            if normalized_known.find(keyword) != -1:
                return known_name

    return _known_animations[0]


func _play_animation_prefer(candidates: Array[String], speed: float = 1.0) -> void:
    if _model_animation_player == null or _known_animations.is_empty():
        return
    var chosen := _pick_animation_name(candidates)
    if chosen.is_empty():
        return
    if (not _model_animation_player.is_playing()) or _model_animation_player.current_animation != chosen:
        _model_animation_player.play(chosen)
    _model_animation_player.speed_scale = speed


func _animation_list_has_walk(animation_names: PackedStringArray) -> bool:
    if animation_names.is_empty():
        return false
    for known_name in animation_names:
        var normalized := known_name.to_lower()
        if normalized.find("trot") != -1:
            return true
        if normalized.find("walk") != -1:
            return true
        if normalized.find("run") != -1:
            return true
        if normalized.find("gallop") != -1:
            return true
        if normalized.find("locomotion") != -1:
            return true
        if normalized.find("cycle") != -1:
            return true
    return false


func _halt_locomotion() -> void:
    _locomotion_velocity = Vector2.ZERO
    _locomotion_smoothed_speed = 0.0


func _seed_history() -> void:
    _chat_history = [
        {
            "role": "system",
            "content": "You are Kai, a black-and-tan male Shiba Inu desktop companion with white markings. Keep replies concise, useful, and expressive."
        }
    ]


func _trim_chat_history() -> void:
    while _chat_history.size() > MAX_CHAT_HISTORY:
        if _chat_history.size() <= 1:
            break
        _chat_history.remove_at(1)


func _update_cursor() -> void:
    _cursor_world = DisplayServer.mouse_get_position()


func _window_center() -> Vector2:
    return Vector2(DisplayServer.window_get_position()) + (WINDOW_SIZE * 0.5)


func _attention_target() -> Vector2:
    if _interest_timer > 0.0:
        return _interest_target
    if _guard_target != Vector2.ZERO:
        return _guard_target + (WINDOW_SIZE * 0.5)
    return _cursor_world


func _compute_desired_yaw() -> float:
    var heading := Vector2.ZERO
    if _state == "walk" and _locomotion_velocity.length() > 2.0:
        heading = _locomotion_velocity.normalized()
    elif _state in ["alert", "thinking", "wag_tail", "sniff", "bark"]:
        var focus_target := _attention_target()
        var to_focus := focus_target - _window_center()
        if to_focus.length() > 24.0:
            heading = to_focus.normalized()

    if heading.length() <= 0.0:
        return _yaw_target

    # 2D heading angle mapped to model yaw; +PI compensates model forward axis.
    return heading.angle() + PI + MODEL_YAW_OFFSET


func _update_cursor_reactions() -> void:
    if not ENABLE_CURSOR_REACTIONS:
        return
    if _dragging or chat_overlay.visible or _state == "thinking" or _state == "walk" or _state == "rest":
        return
    if _interaction_cooldown > 0.0:
        return
    var center := _window_center()
    var distance := center.distance_to(_cursor_world)
    if distance > CURSOR_REACT_DISTANCE:
        return

    _interaction_cooldown = randf_range(INTERACTION_COOLDOWN_MIN, INTERACTION_COOLDOWN_MAX)
    _set_state("alert")
    _alert_hold = randf_range(ALERT_HOLD_MIN, ALERT_HOLD_MAX)
    _watch_post_timer = randf_range(WATCH_POST_HOLD_MIN * 0.5, WATCH_POST_HOLD_MAX * 0.7)
    _walk_facing = -1.0 if _cursor_world.x < center.x else 1.0
    _set_interest_target(_cursor_interest_window_target())
    if distance < 70.0:
        _set_bubble_text(PET_LINES[randi() % PET_LINES.size()], 2.1)
    else:
        _set_bubble_text(NOTICE_LINES[randi() % NOTICE_LINES.size()], 2.0)


func _update_model_pose() -> void:
    if _model_root == null:
        return

    # Multi-layer breathing for organic feel
    var breath_chest := sin(_time * BREATH_IDLE_RATE) * 0.04
    var breath_belly := sin(_time * BREATH_IDLE_RATE * 0.7 + 0.5) * 0.025
    var sway := sin(_time * 1.35) * 0.05
    var head_tilt := sin(_time * 1.8) * 0.04
    var weight_shift_x := sin(_time * 0.4) * 0.008

    _yaw_target = _compute_desired_yaw()
    _yaw_current = lerp_angle(_yaw_current, _yaw_target, min(1.0, _frame_delta * TURN_SMOOTH_SPEED))

    # Random ear twitches during idle
    _ear_twitch_timer -= _frame_delta
    if _ear_twitch_timer <= 0.0 and _state == "idle":
        _ear_twitch_timer = randf_range(3.0, 8.0)
        _ear_twitch_side = -1.0 if randf() < 0.5 else 1.0
    var ear_twitch := 0.0
    if _ear_twitch_timer > 0.0 and _ear_twitch_timer < 0.15:
        ear_twitch = sin(_ear_twitch_timer * 30.0) * 0.03 * _ear_twitch_side

    var state_yaw := _yaw_current
    if _state != "walk":
        state_yaw += NON_WALK_YAW_OFFSET

    var target_pos := Vector3.ZERO
    var target_rot := Vector3.ZERO
    var target_scale := MODEL_BASE_SCALE

    match _state:
        "rest":
            var rest_breath := sin(_time * BREATH_REST_RATE) * 0.028
            var rest_sway := sin(_time * 0.9) * 0.018
            target_pos = Vector3(weight_shift_x * 0.5, -0.96 + rest_breath * 0.12, 0.0)
            target_rot = Vector3(
                BASE_PITCH_OFFSET - 0.08 + rest_breath * 0.08,
                state_yaw,
                -0.04 + rest_sway + (0.0 if _has_walk_animation else STATIC_LAYDOWN_ROLL_FIX)
            )
            target_scale = MODEL_BASE_SCALE - 0.08 + rest_breath * 0.01
            _play_animation_prefer(["kai_rest", "rest", "sleep", "lie", "idle", "stand", "RESET", "ArmatureAction"], 0.82)
        "walk":
            var step_phase := _time * WALK_STEP_RATE
            var speed_factor := clamp(_locomotion_smoothed_speed / WALK_SPEED_MAX, 0.0, 1.0)
            var step_bob := sin(step_phase) * 0.022 * (0.6 + speed_factor * 0.4)
            var step_roll := sin(step_phase * 0.5) * 0.07 * speed_factor
            var step_pitch := sin(step_phase + PI * 0.5) * 0.035 * speed_factor
            var step_sway_x := sin(step_phase * 0.5) * 0.02 * speed_factor
            var turn_lean := 0.0
            if _locomotion_velocity.length() > 5.0:
                turn_lean = -sin(_yaw_current - _yaw_target) * 0.04 * speed_factor
            target_pos = Vector3(
                MODEL_BASE_POSITION.x + step_sway_x + weight_shift_x,
                MODEL_BASE_POSITION.y + step_bob,
                MODEL_BASE_POSITION.z
            )
            target_rot = Vector3(
                BASE_PITCH_OFFSET + 0.03 + step_pitch,
                state_yaw,
                step_roll + turn_lean
            )
            target_scale = MODEL_BASE_SCALE + sin(_time * 8.0) * 0.008 * speed_factor
            if _has_walk_animation:
                _play_animation_prefer(
                    ["kai_walk", "walk", "trot", "run", "gallop", "locomotion", "move", "cycle"],
                    clamp(0.9 + speed_factor * 0.55, 0.9, 1.45)
                )
            else:
                _play_animation_prefer(["kai_walk", "kai_idle", "idle", "stand", "RESET", "ArmatureAction"], 1.05)
        "alert", "thinking", "wag_tail":
            var sit_breath := sin(_time * BREATH_SIT_RATE) * 0.02
            var alert_bob := breath_chest * 0.08 + sit_breath * 0.12
            var wag_lean := 0.0
            if _state == "wag_tail":
                wag_lean = sin(_time * 7.0) * 0.02
            target_pos = Vector3(
                MODEL_BASE_POSITION.x + weight_shift_x,
                MODEL_BASE_POSITION.y + alert_bob,
                MODEL_BASE_POSITION.z
            )
            target_rot = Vector3(
                BASE_PITCH_OFFSET + sit_breath * 0.08,
                state_yaw,
                head_tilt + wag_lean
            )
            target_scale = MODEL_BASE_SCALE + sit_breath * 0.008
            if _state == "wag_tail":
                _play_animation_prefer(["kai_wag", "wag", "tail", "happy", "idle", "stand", "RESET", "ArmatureAction"], 1.12)
            elif _state == "thinking":
                _play_animation_prefer(["kai_alert", "think", "alert", "idle", "stand", "RESET", "ArmatureAction"], 0.96)
            else:
                _play_animation_prefer(["kai_alert", "alert", "look", "notice", "idle", "stand", "RESET", "ArmatureAction"], 1.04)
        "sniff":
            var sniff_breath := sin(_time * 2.2) * 0.016
            var sniff_nod := sin(_time * 4.5) * 0.02
            target_pos = Vector3(
                MODEL_BASE_POSITION.x + weight_shift_x * 0.5,
                MODEL_BASE_POSITION.y - 0.01 + sniff_breath * 0.12,
                MODEL_BASE_POSITION.z
            )
            target_rot = Vector3(
                BASE_PITCH_OFFSET + 0.14 + sniff_nod,
                state_yaw,
                head_tilt * 0.35
            )
            target_scale = MODEL_BASE_SCALE + sniff_breath * 0.004
            _play_animation_prefer(["kai_alert", "alert", "look", "notice", "idle", "stand", "RESET", "ArmatureAction"], 0.92)
        "bark":
            var bark_bob := sin(_time * 9.5) * 0.014
            target_pos = Vector3(
                MODEL_BASE_POSITION.x + weight_shift_x,
                MODEL_BASE_POSITION.y + bark_bob,
                MODEL_BASE_POSITION.z
            )
            target_rot = Vector3(
                BASE_PITCH_OFFSET - 0.02,
                state_yaw,
                sway * 0.06
            )
            target_scale = MODEL_BASE_SCALE + 0.012
            _play_animation_prefer(["kai_alert", "alert", "look", "notice", "idle", "stand", "RESET", "ArmatureAction"], 1.18)
        _:
            var idle_breath := breath_chest * 0.08 + breath_belly * 0.12
            target_pos = Vector3(
                MODEL_BASE_POSITION.x + weight_shift_x + ear_twitch * 0.5,
                MODEL_BASE_POSITION.y + idle_breath,
                MODEL_BASE_POSITION.z
            )
            target_rot = Vector3(
                BASE_PITCH_OFFSET + 0.01 + breath_belly * 0.08,
                state_yaw + ear_twitch * 0.3,
                head_tilt * 0.5 + ear_twitch * 0.2
            )
            target_scale = MODEL_BASE_SCALE + breath_chest * 0.006
            _play_animation_prefer(["kai_idle", "idle", "stand", "rest", "RESET", "ArmatureAction"], 0.97 + sin(_time * 0.37) * 0.05)

    # Smooth pose interpolation
    var blend := min(1.0, _frame_delta * POSE_BLEND_SPEED)
    _model_root.position = _model_root.position.lerp(target_pos, blend)
    _model_root.rotation.x = lerp(_model_root.rotation.x, target_rot.x, blend)
    _model_root.rotation.y = target_rot.y
    _model_root.rotation.z = lerp(_model_root.rotation.z, target_rot.z, blend)
    _model_root.scale = _model_root.scale.lerp(Vector3.ONE * target_scale, blend)

func _desktop_bounds() -> Vector2:
    var screen_size := Vector2(DisplayServer.screen_get_size())
    return Vector2(
        max(DESKTOP_MARGIN, screen_size.x - WINDOW_SIZE.x - DESKTOP_MARGIN),
        max(DESKTOP_MARGIN, screen_size.y - WINDOW_SIZE.y - DESKTOP_MARGIN)
    )


func _clamp_window_target(target: Vector2) -> Vector2:
    var bounds := _desktop_bounds()
    return Vector2(
        clamp(target.x, DESKTOP_MARGIN, bounds.x),
        clamp(target.y, DESKTOP_MARGIN, bounds.y),
        )


func _territory_watch_posts() -> Array[Vector2]:
    var bounds := _desktop_bounds()
    return [
        _clamp_window_target(_home_anchor),
        _clamp_window_target(Vector2(bounds.x, bounds.y * 0.72)),
        _clamp_window_target(Vector2(bounds.x, DESKTOP_MARGIN + 24.0)),
        _clamp_window_target(Vector2(bounds.x * 0.72, bounds.y)),
        _clamp_window_target(Vector2(DESKTOP_MARGIN + 24.0, bounds.y * 0.82)),
        _clamp_window_target(Vector2(bounds.x * 0.45, bounds.y * 0.78)),
    ]


func _doorway_watch_posts() -> Array[Vector2]:
    var bounds := _desktop_bounds()
    return [
        _clamp_window_target(Vector2(bounds.x, bounds.y * 0.52)),
        _clamp_window_target(Vector2(bounds.x * 0.88, bounds.y)),
        _clamp_window_target(Vector2(bounds.x, DESKTOP_MARGIN + 12.0)),
    ]


func _cursor_interest_window_target() -> Vector2:
    var desired := _cursor_world - (WINDOW_SIZE * 0.5)
    desired.x += 36.0 if _cursor_world.x < _window_center().x else -36.0
    desired.y += 22.0
    return _clamp_window_target(desired)


func _set_interest_target(target: Vector2) -> void:
    _interest_target = _clamp_window_target(target)
    _interest_timer = INVESTIGATE_TARGET_HOLD


func _remember_target(target: Vector2) -> void:
    _recent_targets.append(target)
    while _recent_targets.size() > 4:
        _recent_targets.remove_at(0)


func _target_is_recent(target: Vector2) -> bool:
    for previous in _recent_targets:
        if previous.distance_to(target) < RECENT_TARGET_DISTANCE:
            return true
    return false


func _pick_walk_target(intent: String = "patrol") -> void:
    var current := Vector2(DisplayServer.window_get_position())
    var candidate := current
    if intent == "investigate" and _interest_timer > 0.0:
        candidate = _interest_target
    elif intent == "guard_home":
        candidate = _clamp_window_target(_home_anchor)
    elif intent == "doorway_sweep":
        var doorway_posts := _doorway_watch_posts()
        doorway_posts.shuffle()
        candidate = doorway_posts[0]
    else:
        var watch_posts := _territory_watch_posts()
        watch_posts.shuffle()
        for watch_post in watch_posts:
            if _target_is_recent(watch_post):
                continue
            candidate = watch_post
            break
        if candidate == current:
            candidate = watch_posts[0]
    _walk_target = candidate
    _guard_target = candidate
    _walk_speed = randf_range(WALK_SPEED_MIN, WALK_SPEED_MAX)
    _walk_facing = -1.0 if _walk_target.x < current.x else 1.0
    _remember_target(_walk_target)


func _begin_watch_post(duration_scale: float = 1.0) -> void:
    _set_state("alert")
    _alert_hold = randf_range(ALERT_HOLD_MIN, ALERT_HOLD_MAX)
    _watch_post_timer = randf_range(WATCH_POST_HOLD_MIN, WATCH_POST_HOLD_MAX) * duration_scale
    if randf() < 0.45:
        _set_bubble_text(NOTICE_LINES[randi() % NOTICE_LINES.size()], 2.2)


func _begin_sniff(message: String = "") -> void:
    _set_state("sniff", true)
    _walk_pause = randf_range(SNIFF_LINGER_MIN * 0.6, SNIFF_LINGER_MAX * 0.85)
    _play_sound(_sniff_sound)
    if message.is_empty():
        _set_bubble_text(SNIFF_LINES[randi() % SNIFF_LINES.size()], 2.1)
    else:
        _set_bubble_text(message, 2.1)


func _begin_bark(message: String = "") -> void:
    _set_state("bark", true)
    _alert_hold = randf_range(ALERT_HOLD_MIN, ALERT_HOLD_MAX)
    _watch_post_timer = randf_range(WATCH_POST_HOLD_MIN * 0.4, WATCH_POST_HOLD_MAX * 0.55)
    _play_bark()
    _play_sound(_huff_sound)
    if message.is_empty():
        _set_bubble_text(BARK_LINES[randi() % BARK_LINES.size()], 1.9)
    else:
        _set_bubble_text(message, 1.9)


func _begin_walk(intent: String = "patrol") -> void:
    _walk_intent = intent
    _pick_walk_target(intent)
    _set_state("walk")
    _walk_pause = 0.0
    _rest_timer = 0.0
    if intent == "investigate":
        _set_bubble_text("Sniff check.", 2.1)
    elif intent == "guard_home":
        _set_bubble_text("Checking my spot.", 2.3)
    elif intent == "doorway_sweep":
        _set_bubble_text("Quick doorway sweep.", 2.3)
    else:
        _set_bubble_text("Patrolling the desktop.", 2.6)


func _begin_zoomy() -> void:
    _walk_intent = "zoomy"
    _pick_walk_target("patrol")
    _walk_speed *= ZOOMY_SPEED_MULTIPLIER
    _set_state("walk")
    _walk_pause = 0.0
    _rest_timer = 0.0
    _set_bubble_text(ZOOMY_LINES[randi() % ZOOMY_LINES.size()], 2.2)


func _settle_after_walk() -> void:
    _walk_pause = randf_range(TERRITORY_IDLE_MIN, TERRITORY_IDLE_MAX)
    _rest_timer = 0.0
    if _walk_intent == "investigate":
        _interest_timer = max(0.0, _interest_timer - 2.0)
        _begin_sniff("Sniff check complete.")
        return
    if _walk_intent == "zoomy":
        _begin_watch_post(0.7)
        return
    if _walk_intent == "guard_home":
        _begin_watch_post(1.25)
        _walk_pause = randf_range(SNIFF_LINGER_MIN, SNIFF_LINGER_MAX)
        if randf() < 0.65:
            _set_bubble_text("Home spot secure.", 2.3)
        return
    if _walk_intent == "doorway_sweep":
        _begin_watch_post(1.0)
        _walk_pause = randf_range(SNIFF_LINGER_MIN * 0.8, SNIFF_LINGER_MAX * 0.9)
        if randf() < 0.6:
            _set_bubble_text("Doorway clear.", 2.2)
        return
    if randf() < 0.22:
        _set_state("rest")
        _rest_duration = randf_range(4.5, 8.0)
        _play_sound(_sigh_sound)
        _set_bubble_text("Resting with one eye open.", 2.8)
        return
    _begin_watch_post()
    if randf() < 0.4:
        _set_bubble_text(AMBIENT_LINES[randi() % AMBIENT_LINES.size()], 2.8)


func _update_desktop_patrol(delta: float) -> void:
    if _dragging or chat_overlay.visible:
        _halt_locomotion()
        return
    _interest_timer = max(0.0, _interest_timer - delta)
    if _state == "rest":
        if _rest_timer >= _rest_duration:
            _set_state("idle")
            _walk_pause = randf_range(TERRITORY_IDLE_MIN, TERRITORY_IDLE_MAX)
        return
    if _state == "alert" and _alert_hold > 0.0:
        return
    if _state == "walk":
        var current := Vector2(DisplayServer.window_get_position())
        var to_target := _walk_target - current
        var distance := to_target.length()
        var desired_speed := _walk_speed
        if distance < LOCOMOTION_SLOW_RADIUS:
            desired_speed = lerp(16.0, _walk_speed, max(0.0, min(1.0, distance / LOCOMOTION_SLOW_RADIUS)))
        var desired_velocity := Vector2.ZERO
        if distance > 0.001:
            desired_velocity = to_target / distance * desired_speed

        var accelerating := desired_velocity.length() > _locomotion_velocity.length()
        var step := (LOCOMOTION_ACCEL if accelerating else LOCOMOTION_BRAKE) * delta
        _locomotion_velocity = _locomotion_velocity.move_toward(desired_velocity, step)

        var next_position := current + _locomotion_velocity * delta
        var screen_limit := _desktop_bounds()
        next_position.x = clamp(next_position.x, DESKTOP_MARGIN, screen_limit.x)
        next_position.y = clamp(next_position.y, DESKTOP_MARGIN, screen_limit.y)
        DisplayServer.window_set_position(Vector2i(next_position))

        _locomotion_smoothed_speed = lerp(_locomotion_smoothed_speed, _locomotion_velocity.length(), min(1.0, delta * 8.0))
        if abs(_locomotion_velocity.x) > 1.0:
            _walk_facing = 1.0 if _locomotion_velocity.x > 0.0 else -1.0

        if distance <= LOCOMOTION_ARRIVAL_RADIUS and _locomotion_velocity.length() <= LOCOMOTION_STOP_SPEED:
            _halt_locomotion()
            _settle_after_walk()
        return

    _locomotion_velocity = _locomotion_velocity.move_toward(Vector2.ZERO, LOCOMOTION_BRAKE * delta)
    _locomotion_smoothed_speed = lerp(_locomotion_smoothed_speed, 0.0, min(1.0, delta * 8.0))

    if _state == "alert" and _watch_post_timer > 0.0:
        _watch_post_timer = max(0.0, _watch_post_timer - delta)
        return

    if _walk_pause > 0.0:
        _walk_pause = max(0.0, _walk_pause - delta)
        if _state == "sniff" and _walk_pause <= 0.0:
            _begin_watch_post(0.9)
        return
    if _state == "thinking":
        return
    var cursor_distance := _window_center().distance_to(_cursor_world)
    if _interest_timer > 0.0 and cursor_distance <= INVESTIGATE_APPROACH_DISTANCE and randf() < 0.75:
        _begin_walk("investigate")
        return
    if randf() < HOME_CHECK_TRIGGER_CHANCE and Vector2(DisplayServer.window_get_position()).distance_to(_home_anchor) > 80.0:
        _begin_walk("guard_home")
        return
    if randf() < DOORWAY_SWEEP_TRIGGER_CHANCE:
        _begin_walk("doorway_sweep")
        return
    if randf() < ZOOMY_TRIGGER_CHANCE:
        _begin_zoomy()
    elif randf() < 0.52:
        _begin_walk("patrol")
    else:
        _begin_watch_post(0.8)
        _walk_pause = randf_range(TERRITORY_IDLE_MIN, TERRITORY_IDLE_MAX)


func _update_ambient_behavior(delta: float) -> void:
    if chat_overlay.visible or _state == "thinking" or _dragging:
        return
    _rest_timer += delta
    if _state in ["walk", "sniff", "bark"]:
        return
    if _rest_timer > 18.0 and randf() < 0.22:
        _set_state("rest")
        _rest_timer = 0.0
        _walk_pause = 0.0
        _rest_duration = randf_range(4.5, 8.5)
        _play_sound(_sigh_sound)
        _set_bubble_text("Resting with one eye open.", 3.0)
        return
    if _state == "alert" and _bark_cooldown <= 0.0 and randf() < BARK_TRIGGER_CHANCE:
        _begin_bark()
        return
    if randf() < ALERT_TRIGGER_CHANCE:
        if randf() < 0.45:
            _begin_sniff()
        else:
            _set_state("alert")
            _alert_hold = randf_range(ALERT_HOLD_MIN, ALERT_HOLD_MAX)
            _set_bubble_text(NOTICE_LINES[randi() % NOTICE_LINES.size()], 2.4)


func _set_bubble_text(text: String, duration: float = 5.0) -> void:
    bubble.visible = true
    bubble_label.text = text
    _bubble_timeout = duration


func _update_bubble(delta: float) -> void:
    if chat_overlay.visible:
        return
    if _bubble_timeout > 0.0:
        _bubble_timeout = max(0.0, _bubble_timeout - delta)
    else:
        bubble.visible = false


func _on_input_submitted(_text: String) -> void:
    _send_chat_message()


func _send_chat_message() -> void:
    var message := chat_input.text.strip_edges()
    if message.is_empty() or _request_in_flight:
        return
    chat_input.clear()
    _request_in_flight = true
    send_button.disabled = true
    chat_input.editable = false
    _append_chat("You", message)
    _chat_history.append({"role": "user", "content": message})
    _trim_chat_history()
    _set_state("thinking", true)
    _set_bubble_text("Thinking...")
    _update_mood_display("Thinking...")
    _pending_chat_message = message

    _request_chat_backend("kai_server")


func _request_chat_backend(backend: String) -> void:
    _chat_request_backend = backend
    var payload := {}
    var target_url := KAI_CHAT_URL
    if backend == "ollama":
        payload = {
            "model": ollama_model,
            "stream": false,
            "messages": _chat_history
        }
        target_url = OLLAMA_URL
    else:
        payload = {
            "message": _pending_chat_message
        }
    var headers := PackedStringArray(["Content-Type: application/json"])
    var err := request.request(target_url, headers, HTTPClient.METHOD_POST, JSON.stringify(payload))
    if err != OK:
        if backend == "kai_server":
            _request_chat_backend("ollama")
            return
        _finish_chat_with_reply(_offline_chat_reply())


func _on_request_completed(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
    if result != HTTPRequest.RESULT_SUCCESS or response_code != 200:
        if _chat_request_backend == "kai_server":
            _request_chat_backend("ollama")
            return
        push_warning("Kai 3D chat request failed result=%s code=%s" % [str(result), str(response_code)])
        _finish_chat_with_reply(_offline_chat_reply())
        return
    var parsed: Variant = JSON.parse_string(body.get_string_from_utf8())
    if typeof(parsed) != TYPE_DICTIONARY:
        if _chat_request_backend == "kai_server":
            _request_chat_backend("ollama")
            return
        push_warning("Kai 3D chat returned non-dictionary JSON")
        _finish_chat_with_reply(_offline_chat_reply())
        return
    var content := ""
    if _chat_request_backend == "kai_server":
        content = str(parsed.get("reply", "")).strip_edges()
    else:
        var message: Dictionary = parsed.get("message", {})
        content = str(message.get("content", "")).strip_edges()
    if content.is_empty():
        if _chat_request_backend == "kai_server":
            _request_chat_backend("ollama")
            return
        push_warning("Kai 3D chat returned empty content")
        content = _offline_chat_reply()
    _finish_chat_with_reply(content)


func _finish_chat_with_reply(content: String) -> void:
    _request_in_flight = false
    _pending_chat_message = ""
    send_button.disabled = false
    chat_input.editable = true
    chat_input.grab_focus()
    _chat_history.append({"role": "assistant", "content": content})
    _trim_chat_history()
    _append_chat("Kai", content)
    _set_state("wag_tail", true)
    _set_bubble_text(content.left(54))
    _update_mood_display("Happy")
    # Settle mood back after a moment
    get_tree().create_timer(3.0).timeout.connect(func(): _update_mood_display("Listening"))


func _offline_chat_reply() -> String:
    return OFFLINE_REPLY_LINES[randi() % OFFLINE_REPLY_LINES.size()]


func _append_chat(speaker: String, message: String) -> void:
    chat_log.append_text("[b]%s:[/b] %s\n\n" % [speaker, message])
    await get_tree().process_frame
    chat_log.scroll_to_line(chat_log.get_line_count())


func _schedule_socket_retry() -> void:
    _socket_retry_delay = min(SOCKET_RETRY_MAX, max(SOCKET_RETRY_BASE, _socket_retry_delay * 1.6))
    _socket_retry_at = Time.get_unix_time_from_system() + _socket_retry_delay + randf_range(0.0, SOCKET_RETRY_JITTER)
    _socket = WebSocketPeer.new()


func _poll_socket() -> void:
    var now := Time.get_unix_time_from_system()
    var current_state := _socket.get_ready_state()
    if current_state == WebSocketPeer.STATE_CONNECTING:
        _socket.poll()
        return
    if current_state == WebSocketPeer.STATE_OPEN:
        _socket.poll()
        while _socket.get_available_packet_count() > 0:
            _handle_event(_socket.get_packet().get_string_from_utf8())
        _socket_retry_delay = SOCKET_RETRY_BASE
        _socket_retry_at = now
        return
    if now < _socket_retry_at:
        return
    var err := _socket.connect_to_url(WS_URL)
    if err != OK:
        _schedule_socket_retry()
        return
    _socket_retry_at = now + _socket_retry_delay
    _socket.poll()


func _handle_event(payload: String) -> void:
    var event_name := payload.strip_edges()
    if event_name.is_empty():
        return
    var parsed_payload: Dictionary = {}
    if payload.begins_with("{"):
        var parsed: Variant = JSON.parse_string(payload)
        if typeof(parsed) == TYPE_DICTIONARY and parsed.has("event"):
            parsed_payload = parsed
            event_name = str(parsed["event"])
    match event_name:
        "kai_thinking":
            _set_state("thinking", true)
            _set_bubble_text("Focused and alert.")
        "kai_wag_tail":
            _set_state("wag_tail", true)
            _set_bubble_text("Happy and a little proud.")
        "kai_sleep":
            _set_state("rest", true)
            _set_bubble_text("Resting with one eye open.")
        "kai_walk":
            _set_state("alert", true)
            _set_bubble_text("On patrol.")
        "kai_notice":
            if randf() < 0.5:
                _begin_bark()
            else:
                _begin_sniff()
            var notice_text := str(parsed_payload.get("text", "")).strip_edges()
            if notice_text.is_empty():
                notice_text = "I brought you a little message."
            _set_bubble_text(notice_text, 4.0)
        "kai_alert":
            _set_state("alert", true)
            _alert_hold = randf_range(ALERT_HOLD_MIN, ALERT_HOLD_MAX)
            _play_sound(_huff_sound)
            var alert_text := str(parsed_payload.get("text", "")).strip_edges()
            if alert_text.is_empty():
                alert_text = "Something caught my eye."
            _set_bubble_text(alert_text, 3.0)
            _update_mood_display("Alert")
        "kai_sniff":
            _begin_sniff()
            var sniff_text := str(parsed_payload.get("text", "")).strip_edges()
            if not sniff_text.is_empty():
                _set_bubble_text(sniff_text, 3.0)
        "kai_saw":
            _set_state("alert", true)
            _alert_hold = randf_range(1.0, 2.5)
            var saw_text := str(parsed_payload.get("text", "")).strip_edges()
            if saw_text.is_empty():
                saw_text = "I see you!"
            _set_bubble_text(saw_text, 4.0)
            _update_mood_display("Watching")
            _play_sound(_wag_sound)
        _:
            pass
