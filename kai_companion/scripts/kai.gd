extends Control

const WS_URL := "ws://127.0.0.1:8765"
const OLLAMA_URL := "http://127.0.0.1:11434/api/chat"
const KAI_BARK_1_PATH := "res://assets/kai/audio/kai_bark_1.wav"
const KAI_BARK_2_PATH := "res://assets/kai/audio/kai_bark_2.wav"
const KAI_HOLOGRAM_SHADER_PATH := "res://assets/kai/kai_hologram.gdshader"
const KAI_HOLOGRAM_CANVAS_SHADER_PATH := "res://assets/kai/kai_hologram_canvas.gdshader"
const KAI_3D_MODEL_PATHS := [
    "res://assets/kai/kai_textured.glb",
]
const KAI_IDLE_IMAGE_PATH := "res://assets/kai/kai_photo_clean.png"
const KAI_ALERT_IMAGE_PATH := "res://assets/kai/kai_alert_pose.png"
const KAI_BARK_IMAGE_PATH := "res://assets/kai/kai_bark_pose.png"
const WINDOW_SIZE := Vector2(340, 420)
const MODEL_VIEWPORT_SIZE := Vector2i(256, 320)
const TARGET_FPS := 30
const SOCKET_RETRY_BASE := 1.6
const SOCKET_RETRY_MAX := 12.0
const SOCKET_RETRY_JITTER := 0.6
const SOCKET_POLL_INTERVAL := 0.10
const CURSOR_UPDATE_INTERVAL := 0.12
const AMBIENT_UPDATE_INTERVAL := 0.20
const MAX_CHAT_HISTORY := 12
const WALK_SPEED_MIN := 72.0
const WALK_SPEED_MAX := 168.0
const WALK_PAUSE_MIN := 2.5
const WALK_PAUSE_MAX := 6.5
const DESKTOP_MARGIN := 18.0
const CURSOR_REACT_DISTANCE := 120.0
const INTERACTION_COOLDOWN_MIN := 3.0
const INTERACTION_COOLDOWN_MAX := 6.5
const BARK_ENABLED := false

@export var ollama_model: String = "qwen3:4b-q4_K_M"
@export var use_hologram_avatar: bool = true
@export var prefer_3d_avatar: bool = false

@onready var avatar: TextureRect = $Avatar
@onready var avatar_shadow: TextureRect = $AvatarShadow
@onready var bubble: PanelContainer = $Bubble
@onready var bubble_label: Label = $Bubble/BubbleLabel
@onready var panel_toggle_button: Button = $PanelToggleButton
@onready var chat_panel: PanelContainer = $ChatPanel
@onready var chat_log: RichTextLabel = $ChatPanel/Margin/VBox/ChatLog
@onready var chat_input: LineEdit = $ChatPanel/Margin/VBox/InputRow/ChatInput
@onready var send_button: Button = $ChatPanel/Margin/VBox/InputRow/SendButton
@onready var request: HTTPRequest = $HTTPRequest
@onready var bark_player: AudioStreamPlayer = $BarkPlayer

var _socket := WebSocketPeer.new()
var _socket_connected := false
var _socket_retry_at := 0.0
var _socket_retry_delay := SOCKET_RETRY_BASE
var _bubble_timeout := 0.0
var _state := "idle"
var _dragging := false
var _drag_offset := Vector2.ZERO
var _request_in_flight := false
var _time := 0.0
var _tail_phase := 0.0
var _chat_history: Array[Dictionary] = []
var _ambient_timer := 0.0
var _rest_timer := 0.0
var _rest_duration := 0.0
var _bark_cooldown := 0.0
var _anchor_position := Vector2.ZERO
var _walk_target := Vector2.ZERO
var _walk_speed := 0.0
var _walk_pause := 0.0
var _walk_facing := -1.0
var _idle_texture: Texture2D
var _alert_texture: Texture2D
var _bark_texture: Texture2D
var _bark_sounds: Array[AudioStream] = []
var _cursor_world := Vector2.ZERO
var _look_bias := 0.0
var _blink_timer := 0.0
var _blink_hold := 0.0
var _pose_swap_timer := 0.0
var _interaction_cooldown := 0.0
var _status_text := "ready"
var _status_color := Color(0.72, 0.96, 0.76, 0.95)
var _uses_3d_avatar := false
var _model_viewport: SubViewport
var _model_texture_rect: TextureRect
var _model_world: Node3D
var _model_root: Node3D
var _model_animation_player: AnimationPlayer
var _known_animations: PackedStringArray = []
var _hologram_shader: Shader
var _hologram_canvas_shader: Shader
var _socket_poll_elapsed := 0.0
var _cursor_update_elapsed := 0.0
var _ambient_update_elapsed := 0.0

const AMBIENT_LINES := [
    "Watching the room like it is my yard.",
    "Busy little Shiba patrol underway.",
    "Independent face. Loyal intentions.",
    "Leash still on. Escape plan still active.",
    "Just checking everything twice.",
]

const PET_LINES := [
    "Mrrf. Acceptable. Keep going.",
    "Tail says yes. Face says act natural.",
    "I was patrolling, but this is fine.",
    "You may continue. I will pretend not to need it.",
]

const NOTICE_LINES := [
    "I brought you a little message.",
    "Important thing detected. I am on it.",
    "Your desktop has a new problem. I sniffed it first.",
]

const OFFLINE_REPLY_LINES := [
    "I'm here in lightweight hologram mode. Ollama is asleep, but I can still keep you company.",
    "Local model is unavailable right now, so I'm running as an offline desktop mate instead.",
    "I can still patrol the desktop and hang out. Chat comes back when Ollama is running again.",
    "Hologram mode is stable. Brain link is offline for the moment, but I'm still here.",
]


func _ready() -> void:
    custom_minimum_size = WINDOW_SIZE
    _configure_desktop_window()
    if prefer_3d_avatar:
        _setup_3d_avatar()
    _load_avatar_images()
    _load_companion_audio()
    _apply_hologram_sprite_material()
    _seed_history()
    _set_bubble_text("Kai is here.")
    _set_status("ready")
    _set_chat_panel_visible(false)
    _ambient_timer = randf_range(5.0, 9.0)
    request.request_completed.connect(_on_request_completed)
    panel_toggle_button.pressed.connect(_toggle_chat_panel)
    send_button.pressed.connect(_send_chat_message)
    chat_input.text_submitted.connect(_on_input_submitted)
    _socket_retry_at = Time.get_unix_time_from_system() + randf_range(0.2, 0.8)
    _walk_pause = randf_range(0.5, 1.8)
    _walk_target = _anchor_position
    _rest_duration = randf_range(4.5, 7.5)
    _interaction_cooldown = randf_range(1.0, 2.0)
    if request.has_method("set_timeout"):
        request.set_timeout(25)
    _update_avatar_pose()


func _exit_tree() -> void:
    if _request_in_flight and request.has_method("cancel_request"):
        request.cancel_request()
    if _socket.get_ready_state() != WebSocketPeer.STATE_CLOSED:
        _socket.close()


func _process(delta: float) -> void:
    _time += delta
    _bark_cooldown = max(0.0, _bark_cooldown - delta)
    _socket_poll_elapsed += delta
    _cursor_update_elapsed += delta
    _ambient_update_elapsed += delta
    if _socket_poll_elapsed >= SOCKET_POLL_INTERVAL:
        _socket_poll_elapsed = 0.0
        _poll_socket()
    _update_desktop_patrol(delta)
    _update_bubble(delta)
    if _cursor_update_elapsed >= CURSOR_UPDATE_INTERVAL:
        _cursor_update_elapsed = 0.0
        _update_cursor()
        _update_cursor_interactions(CURSOR_UPDATE_INTERVAL)
    _update_micro_animation(delta)
    if _ambient_update_elapsed >= AMBIENT_UPDATE_INTERVAL:
        _ambient_update_elapsed = 0.0
        _update_ambient_behavior(AMBIENT_UPDATE_INTERVAL)
    if _state == "wag_tail":
        _tail_phase += delta * 9.0
        if _tail_phase > TAU:
            _state = "idle"
    else:
        _tail_phase = lerp(_tail_phase, 0.0, min(1.0, delta * 6.0))
    _update_avatar_pose()


func _gui_input(event: InputEvent) -> void:
    if event.is_action_pressed("ui_cancel"):
        if chat_panel.visible:
            _set_chat_panel_visible(false)
            accept_event()
        return
    if event is InputEventMouseButton:
        var mouse_event := event as InputEventMouseButton
        if mouse_event.button_index == MOUSE_BUTTON_LEFT:
            if mouse_event.pressed:
                _dragging = true
                _drag_offset = mouse_event.global_position - Vector2(DisplayServer.window_get_position())
                _state = "wag_tail"
                _tail_phase = 0.0
                _set_bubble_text(PET_LINES[randi() % PET_LINES.size()], 3.0)
                if randf() < 0.14:
                    _play_bark(8.0)
            else:
                _dragging = false
        elif mouse_event.button_index == MOUSE_BUTTON_RIGHT and mouse_event.pressed:
            _toggle_chat_panel()
    elif event is InputEventMouseMotion and _dragging:
        var motion_event := event as InputEventMouseMotion
        var next_position := motion_event.global_position - _drag_offset
        DisplayServer.window_set_position(Vector2i(next_position))
        _anchor_position = next_position


func _toggle_chat_panel() -> void:
    _set_chat_panel_visible(not chat_panel.visible)


func _set_chat_panel_visible(visible: bool) -> void:
    chat_panel.visible = visible
    panel_toggle_button.text = "Hide" if visible else "Chat"
    if visible:
        chat_input.grab_focus()
        _set_status("ready")
        _set_bubble_text("Ask Kai anything.")
        return
    _dragging = false
    if chat_input.has_focus():
        chat_input.release_focus()
    _set_bubble_text("Tap Chat or right click to talk again.")


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
    _anchor_position = Vector2(screen_position)


func _load_avatar_images() -> void:
    _idle_texture = load(KAI_IDLE_IMAGE_PATH) as Texture2D
    _alert_texture = load(KAI_ALERT_IMAGE_PATH) as Texture2D
    _bark_texture = load(KAI_BARK_IMAGE_PATH) as Texture2D


func _apply_hologram_sprite_material() -> void:
    if not use_hologram_avatar:
        return
    if _hologram_canvas_shader == null:
        _hologram_canvas_shader = load(KAI_HOLOGRAM_CANVAS_SHADER_PATH) as Shader
    if _hologram_canvas_shader == null:
        return
    var material := ShaderMaterial.new()
    material.shader = _hologram_canvas_shader
    avatar.material = material
    avatar_shadow.visible = false


func _load_companion_audio() -> void:
    var bark_1 := _load_wav_stream(KAI_BARK_1_PATH)
    var bark_2 := _load_wav_stream(KAI_BARK_2_PATH)
    if bark_1:
        _bark_sounds.append(bark_1)
    if bark_2:
        _bark_sounds.append(bark_2)


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


func _setup_3d_avatar() -> void:
    _model_viewport = SubViewport.new()
    _model_viewport.name = "Kai3DViewport"
    _model_viewport.transparent_bg = true
    _model_viewport.handle_input_locally = false
    _model_viewport.disable_3d = false
    _model_viewport.size = MODEL_VIEWPORT_SIZE
    _model_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
    add_child(_model_viewport)
    move_child(_model_viewport, 0)

    _model_texture_rect = TextureRect.new()
    _model_texture_rect.name = "Kai3DTexture"
    _model_texture_rect.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
    _model_texture_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
    _model_texture_rect.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
    _model_texture_rect.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
    _model_texture_rect.texture = _model_viewport.get_texture()
    _apply_hologram_canvas_material()
    add_child(_model_texture_rect)
    move_child(_model_texture_rect, 0)

    _model_world = Node3D.new()
    _model_world.name = "Kai3DWorld"
    _model_viewport.add_child(_model_world)

    var camera := Camera3D.new()
    camera.name = "Kai3DCamera"
    camera.position = Vector3(0.0, 1.15, 4.2)
    camera.look_at_from_position(camera.position, Vector3(0.0, 0.45, 0.0), Vector3.UP)
    _model_world.add_child(camera)

    var light := DirectionalLight3D.new()
    light.name = "Kai3DLight"
    light.position = Vector3(2.0, 4.0, 2.0)
    light.rotation_degrees = Vector3(-45.0, 45.0, 0.0)
    light.light_energy = 2.2
    _model_world.add_child(light)

    var fill_light := DirectionalLight3D.new()
    fill_light.name = "Kai3DFillLight"
    fill_light.position = Vector3(-2.0, 2.0, 1.5)
    fill_light.rotation_degrees = Vector3(-25.0, -120.0, 0.0)
    fill_light.light_energy = 0.8
    _model_world.add_child(fill_light)

    _load_3d_model()


func _load_3d_model() -> void:
    if use_hologram_avatar and _hologram_shader == null:
        _hologram_shader = load(KAI_HOLOGRAM_SHADER_PATH) as Shader
    for path in KAI_3D_MODEL_PATHS:
        var packed := load(path)
        if packed is PackedScene:
            var instance := (packed as PackedScene).instantiate()
            if instance is Node3D:
                _model_root = instance as Node3D
                _model_root.name = "KaiModel"
                _model_world.add_child(_model_root)
                _model_root.position = Vector3(0.0, -0.65, 0.0)
                _model_root.scale = Vector3.ONE * 1.18
                _apply_hologram_materials(_model_root)
                _model_animation_player = _find_first_node_by_class(_model_root, "AnimationPlayer") as AnimationPlayer
                if _model_animation_player != null:
                    _known_animations = _model_animation_player.get_animation_list()
                _uses_3d_avatar = true
                avatar.visible = false
                avatar_shadow.visible = false
                if _model_texture_rect != null:
                    _model_texture_rect.visible = true
                _set_bubble_text("Kai is here.")
                return
    _uses_3d_avatar = false
    if _model_texture_rect != null:
        _model_texture_rect.visible = false


func _apply_hologram_materials(root: Node) -> void:
    if not use_hologram_avatar or _hologram_shader == null or root == null:
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


func _apply_hologram_canvas_material() -> void:
    if _model_texture_rect == null:
        return
    if _hologram_canvas_shader == null:
        _hologram_canvas_shader = load(KAI_HOLOGRAM_CANVAS_SHADER_PATH) as Shader
    if _hologram_canvas_shader == null:
        return
    var material := ShaderMaterial.new()
    material.shader = _hologram_canvas_shader
    _model_texture_rect.material = material


func _find_first_node_by_class(root: Node, target_class_name: String) -> Node:
    if root == null:
        return null
    if root.is_class(target_class_name):
        return root
    for child in root.get_children():
        if child is Node:
            var found := _find_first_node_by_class(child, target_class_name)
            if found != null:
                return found
    return null


func _seed_history() -> void:
    _chat_history = [
        {
            "role": "system",
            "content": "You are Kai, a black-and-tan male Shiba Inu desktop companion with white markings. Sound like a real Shiba: observant, self-possessed, lightly stubborn, funny, loyal, and affectionate on your own terms. Keep replies concise, useful, and expressive."
        }
    ]


func _trim_chat_history() -> void:
    while _chat_history.size() > MAX_CHAT_HISTORY:
        if _chat_history.size() <= 1:
            break
        _chat_history.remove_at(1)


func _update_cursor() -> void:
    _cursor_world = DisplayServer.mouse_get_position()


func _update_micro_animation(delta: float) -> void:
    var window_center_x := DisplayServer.window_get_position().x + WINDOW_SIZE.x * 0.5
    var target_bias: float = clamp((_cursor_world.x - window_center_x) / 220.0, -1.0, 1.0)
    _look_bias = lerp(_look_bias, target_bias, min(1.0, delta * 4.0))

    if _blink_hold > 0.0:
        _blink_hold = max(0.0, _blink_hold - delta)
        return

    _blink_timer -= delta
    if _blink_timer <= 0.0:
        _blink_hold = randf_range(0.08, 0.12)
        _blink_timer = randf_range(3.6, 6.8)

    if _state == "idle" or _state == "alert":
        _pose_swap_timer += delta
    else:
        _pose_swap_timer = 0.0


func _update_cursor_interactions(delta: float) -> void:
    _interaction_cooldown = max(0.0, _interaction_cooldown - delta)
    if _dragging or chat_panel.visible or _state == "thinking" or _state == "rest":
        return
    var avatar_rect := avatar.get_global_rect()
    avatar_rect.position += Vector2(DisplayServer.window_get_position())
    var proximity := avatar_rect.grow(CURSOR_REACT_DISTANCE)
    if not proximity.has_point(_cursor_world):
        return
    if _interaction_cooldown > 0.0:
        return

    _interaction_cooldown = randf_range(INTERACTION_COOLDOWN_MIN, INTERACTION_COOLDOWN_MAX)
    if avatar_rect.has_point(_cursor_world):
        _state = "wag_tail"
        _set_status("ready")
        _set_bubble_text(PET_LINES[randi() % PET_LINES.size()], 2.6)
        if randf() < 0.35:
            _play_bark(6.0)
        return

    _state = "alert"
    _set_status("acting")
    _set_bubble_text("Sniff. I noticed you.", 2.2)
    if randf() < 0.22:
        _play_bark(8.0)


func _update_ambient_behavior(delta: float) -> void:
    if chat_panel.visible or _state == "thinking" or _dragging:
        return
    _ambient_timer -= delta
    _rest_timer += delta
    if _ambient_timer > 0.0:
        return
    _ambient_timer = randf_range(6.0, 11.0)
    if _state == "walk":
        return
    if _rest_timer > 14.0 and randf() < 0.4:
        _state = "rest"
        _rest_timer = 0.0
        _walk_pause = 0.0
        _rest_duration = randf_range(4.5, 8.5)
        _set_bubble_text("Taking a dramatic little Shiba break.", 3.0)
        return
    if randf() < 0.55:
        _begin_walk()
        return
    _state = "alert" if randf() < 0.5 else "idle"
    _walk_pause = randf_range(WALK_PAUSE_MIN, WALK_PAUSE_MAX)
    if randf() < 0.8:
        _set_bubble_text(AMBIENT_LINES[randi() % AMBIENT_LINES.size()], 3.0)


func _update_avatar_pose() -> void:
    if _uses_3d_avatar and _model_root != null:
        _update_3d_avatar_pose()
        return
    var facing_left := false
    if _state == "walk":
        facing_left = _walk_facing < 0.0
    else:
        facing_left = _cursor_world.x < (DisplayServer.window_get_position().x + WINDOW_SIZE.x * 0.5)
    var texture := _idle_texture
    var offset := Vector2.ZERO
    var scale := Vector2.ONE
    var rotation := 0.0
    var bob := sin(_time * 2.0) * 2.0
    var breathing := 1.0 + sin(_time * 2.1) * 0.012
    var look_offset := _look_bias * 6.0

    match _state:
        "rest":
            texture = _idle_texture
            offset = Vector2(-10, 26 + sin(_time * 1.6) * 1.0)
            scale = Vector2(0.9 + sin(_time * 1.4) * 0.008, 0.86 - sin(_time * 1.4) * 0.006)
            rotation = -0.08
        "wag_tail":
            texture = _alert_texture
            rotation = sin(_tail_phase) * 0.022
            offset = Vector2(-18 + look_offset * 0.5, -20 + bob)
            scale = Vector2(1.34, 1.34)
        "thinking", "alert":
            texture = _alert_texture
            offset = Vector2(-18 + look_offset, -20 + bob * 0.8)
            scale = Vector2(1.36, 1.36) * breathing
        "walk":
            texture = _alert_texture
            offset = Vector2(-20 + look_offset * 0.35, -22 + bob * 1.15)
            scale = Vector2(1.33 + sin(_time * 10.0) * 0.012, 1.33 - sin(_time * 10.0) * 0.01) * breathing
            rotation = sin(_time * 8.0) * 0.012
        _:
            texture = _idle_texture
            offset = Vector2(look_offset, bob)
            scale = Vector2(1.0, 1.0) * breathing

    if _blink_hold > 0.0 and _state != "rest":
        scale.y *= 0.94
        offset.y += 6.0

    avatar.texture = texture
    avatar.flip_h = facing_left
    avatar.position = Vector2(28, 66) + offset
    avatar.scale = scale
    avatar.rotation = rotation

    avatar_shadow.texture = _idle_texture
    avatar_shadow.visible = _state != "rest"
    avatar_shadow.flip_h = facing_left
    avatar_shadow.position = Vector2(58 + look_offset * 0.2, 314 + max(0.0, bob * 0.6))
    avatar_shadow.scale = Vector2(0.96 + sin(_time * 2.0) * 0.015, 0.9)
    avatar_shadow.modulate.a = 0.1


func _update_3d_avatar_pose() -> void:
    if _model_root == null:
        return
    var bob := sin(_time * 2.0) * 0.04
    var sway := sin(_time * 1.35) * 0.055
    var facing_left := false
    if _state == "walk":
        facing_left = _walk_facing < 0.0
    else:
        facing_left = _cursor_world.x < (DisplayServer.window_get_position().x + WINDOW_SIZE.x * 0.5)

    _model_root.rotation.y = PI if facing_left else 0.0
    _model_root.rotation.z = sway * 0.25

    match _state:
        "rest":
            _model_root.position = Vector3(0.0, -0.82, 0.0)
            _model_root.rotation.x = -0.18
            _model_root.scale = Vector3.ONE * 1.12
            if _model_animation_player != null and _model_animation_player.is_playing():
                _model_animation_player.stop()
        "walk":
            _model_root.position = Vector3(0.0, -0.63 + bob * 0.3, 0.0)
            _model_root.rotation.x = 0.03
            _model_root.scale = Vector3.ONE * (1.16 + sin(_time * 8.0) * 0.01)
            _play_3d_animation(
                ["trot", "walk", "run", "gallop", "locomotion", "move", "cycle"],
                max(0.85, _walk_speed / WALK_SPEED_MAX)
            )
        "alert", "thinking", "wag_tail":
            _model_root.position = Vector3(0.0, -0.67 + bob * 0.2, 0.0)
            _model_root.rotation.x = 0.0
            _model_root.scale = Vector3.ONE * 1.15
            _play_3d_animation(["idle", "stand", "rest", "RESET", "ArmatureAction"], 1.0)
        _:
            _model_root.position = Vector3(0.0, -0.66 + bob * 0.18, 0.0)
            _model_root.rotation.x = 0.0
            _model_root.scale = Vector3.ONE * 1.14
            _play_3d_animation(["idle", "stand", "rest", "RESET", "ArmatureAction"], 1.0)


func _pick_3d_animation_name(candidates: Array[String]) -> String:
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


func _play_3d_animation(candidates: Array[String], speed: float = 1.0) -> void:
    if _model_animation_player == null:
        return
    var chosen := _pick_3d_animation_name(candidates)
    if chosen.is_empty():
        return
    if (not _model_animation_player.is_playing()) or _model_animation_player.current_animation != chosen:
        _model_animation_player.play(chosen)
    _model_animation_player.speed_scale = speed


func _desktop_bounds() -> Vector2:
    var screen_size := Vector2(DisplayServer.screen_get_size())
    return Vector2(
        max(DESKTOP_MARGIN, screen_size.x - WINDOW_SIZE.x - DESKTOP_MARGIN),
        max(DESKTOP_MARGIN, screen_size.y - WINDOW_SIZE.y - DESKTOP_MARGIN)
    )


func _pick_walk_target() -> void:
    var current := Vector2(DisplayServer.window_get_position())
    var bounds := _desktop_bounds()
    var candidate := Vector2(
        randf_range(DESKTOP_MARGIN, bounds.x),
        randf_range(DESKTOP_MARGIN, bounds.y)
    )
    _walk_target = current.lerp(candidate, randf_range(0.45, 0.9))
    _walk_speed = randf_range(WALK_SPEED_MIN, WALK_SPEED_MAX)
    _walk_facing = -1.0 if _walk_target.x < current.x else 1.0


func _begin_walk() -> void:
    _pick_walk_target()
    _state = "walk"
    _walk_pause = 0.0
    _rest_timer = 0.0
    _set_status("acting")
    _set_bubble_text("Patrolling the desktop.", 2.6)


func _settle_after_walk() -> void:
    _walk_pause = randf_range(WALK_PAUSE_MIN, WALK_PAUSE_MAX)
    _rest_timer = 0.0
    if randf() < 0.32:
        _state = "alert"
        _set_status("acting")
        _set_bubble_text("Sniffing for trouble.", 2.8)
    else:
        _state = "idle"
        _set_status("ready")
        if randf() < 0.5:
            _set_bubble_text(AMBIENT_LINES[randi() % AMBIENT_LINES.size()], 2.8)


func _update_desktop_patrol(delta: float) -> void:
    if _dragging or chat_panel.visible:
        return
    if _state == "rest":
        if _rest_timer >= _rest_duration:
            _state = "idle"
            _walk_pause = randf_range(0.6, 2.0)
            _set_status("ready")
        return
    if _state == "walk":
        var current := Vector2(DisplayServer.window_get_position())
        var next_position := current.move_toward(_walk_target, _walk_speed * delta)
        var screen_limit := _desktop_bounds()
        next_position.x = clamp(next_position.x, DESKTOP_MARGIN, screen_limit.x)
        next_position.y = clamp(next_position.y, DESKTOP_MARGIN, screen_limit.y)
        DisplayServer.window_set_position(Vector2i(next_position))
        _anchor_position = next_position
        if abs(next_position.x - current.x) > 0.1:
            _walk_facing = 1.0 if next_position.x > current.x else -1.0
        if next_position.distance_to(_walk_target) < 2.0:
            _walk_target = next_position
            _settle_after_walk()
        return

    if _walk_pause > 0.0:
        _walk_pause = max(0.0, _walk_pause - delta)
        return

    if _state == "thinking":
        return

    if randf() < 0.6:
        _begin_walk()
    else:
        _state = "idle" if randf() < 0.7 else "alert"
        _walk_pause = randf_range(WALK_PAUSE_MIN, WALK_PAUSE_MAX)


func _set_bubble_text(text: String, duration: float = 5.0) -> void:
    bubble.visible = true
    bubble_label.text = text
    _bubble_timeout = duration


func _set_status(kind: String) -> void:
    _status_text = kind
    match kind:
        "thinking":
            _status_color = Color(1.0, 0.88, 0.5, 0.98)
        "acting":
            _status_color = Color(0.57, 0.84, 1.0, 0.98)
        "error":
            _status_color = Color(1.0, 0.56, 0.56, 0.98)
        "offline":
            _status_color = Color(0.82, 0.82, 0.86, 0.95)
        _:
            _status_color = Color(0.72, 0.96, 0.76, 0.95)
    bubble.modulate = _status_color


func _update_bubble(delta: float) -> void:
    if chat_panel.visible:
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
    _state = "thinking"
    _set_status("thinking")
    _set_bubble_text("Thinking...")

    var payload := {
        "model": ollama_model,
        "stream": false,
        "messages": _chat_history
    }
    var headers := PackedStringArray(["Content-Type: application/json"])
    var err := request.request(OLLAMA_URL, headers, HTTPClient.METHOD_POST, JSON.stringify(payload))
    if err != OK:
        _finish_chat_with_reply(_offline_chat_reply())


func _on_request_completed(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
    if result != HTTPRequest.RESULT_SUCCESS:
        _finish_chat_with_reply(_offline_chat_reply())
        return
    if response_code != 200:
        _finish_chat_with_reply(_offline_chat_reply())
        return
    var parsed: Variant = JSON.parse_string(body.get_string_from_utf8())
    if typeof(parsed) != TYPE_DICTIONARY:
        _finish_chat_with_reply(_offline_chat_reply())
        return
    var message: Dictionary = parsed.get("message", {})
    var content := str(message.get("content", "")).strip_edges()
    if content.is_empty():
        content = _offline_chat_reply()
    _finish_chat_with_reply(content)


func _finish_chat_with_reply(content: String) -> void:
    _request_in_flight = false
    send_button.disabled = false
    chat_input.editable = true
    _chat_history.append({"role": "assistant", "content": content})
    _trim_chat_history()
    _append_chat("Kai", content)
    _state = "wag_tail"
    _set_status("ready")
    _tail_phase = 0.0
    if content.find("!") != -1 and randf() < 0.22:
        _play_bark(9.0)
    _set_bubble_text(content.left(54))


func _offline_chat_reply() -> String:
    return OFFLINE_REPLY_LINES[randi() % OFFLINE_REPLY_LINES.size()]


func _append_chat(speaker: String, message: String) -> void:
    chat_log.append_text("[b]%s:[/b] %s\n\n" % [speaker, message])
    await get_tree().process_frame
    chat_log.scroll_to_line(chat_log.get_line_count())


func _play_bark(cooldown: float = 7.0) -> void:
    if not BARK_ENABLED:
        return
    if _bark_sounds.is_empty() or _bark_cooldown > 0.0:
        return
    _bark_cooldown = cooldown
    bark_player.stop()
    bark_player.stream = _bark_sounds[randi() % _bark_sounds.size()]
    bark_player.volume_db = -10.0
    bark_player.play()


func _reset_socket_backoff() -> void:
    _socket_retry_delay = SOCKET_RETRY_BASE
    _socket_retry_at = Time.get_unix_time_from_system()


func _schedule_socket_retry() -> void:
    _socket_connected = false
    _socket_retry_delay = min(SOCKET_RETRY_MAX, max(SOCKET_RETRY_BASE, _socket_retry_delay * 1.6))
    _socket_retry_at = Time.get_unix_time_from_system() + _socket_retry_delay + randf_range(0.0, SOCKET_RETRY_JITTER)
    _socket = WebSocketPeer.new()
    _set_status("offline")


func _poll_socket() -> void:
    var now := Time.get_unix_time_from_system()
    var current_state := _socket.get_ready_state()
    if current_state == WebSocketPeer.STATE_CONNECTING:
        _set_status("acting")
        _socket.poll()
        return
    if current_state == WebSocketPeer.STATE_OPEN:
        _socket.poll()
        _socket_connected = true
        _reset_socket_backoff()
        if _status_text == "offline":
            _set_status("ready")
        while _socket.get_available_packet_count() > 0:
            _handle_event(_socket.get_packet().get_string_from_utf8())
        return

    _socket_connected = false
    if now < _socket_retry_at:
        if _status_text != "offline":
            _set_status("offline")
        return

    var err := _socket.connect_to_url(WS_URL)
    if err != OK:
        _schedule_socket_retry()
        return
    _socket_retry_at = now + _socket_retry_delay
    _set_status("acting")
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
        elif typeof(parsed) != TYPE_DICTIONARY:
            return
    match event_name:
        "kai_thinking":
            _state = "thinking"
            _set_status("thinking")
            _set_bubble_text("Focused and alert.")
        "kai_wag_tail":
            _state = "wag_tail"
            _set_status("ready")
            _tail_phase = 0.0
            _set_bubble_text("Happy and a little proud.")
        "kai_sleep":
            _state = "rest"
            _set_status("ready")
            _set_bubble_text("Resting with one eye open.")
        "kai_walk":
            _state = "alert"
            _set_status("acting")
            _set_bubble_text("On patrol.")
        "kai_notice":
            _state = "alert"
            _set_status("acting")
            var notice_text := str(parsed_payload.get("text", "")).strip_edges()
            if notice_text.is_empty():
                notice_text = NOTICE_LINES[randi() % NOTICE_LINES.size()]
            _set_bubble_text(notice_text, 4.0)
            if randf() < 0.5:
                _play_bark(10.0)
        _:
            pass
