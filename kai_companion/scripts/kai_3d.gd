extends Node

const WS_URL := "ws://127.0.0.1:8765"
const OLLAMA_URL := "http://127.0.0.1:11434/api/chat"
const KAI_3D_MODEL_PATH := "res://assets/kai/kai-lite.glb"
const KAI_HOLOGRAM_SHADER_PATH := "res://assets/kai/kai_hologram.gdshader"
const WINDOW_SIZE := Vector2(340, 420)
const TARGET_FPS := 30
const SOCKET_RETRY_BASE := 1.6
const SOCKET_RETRY_MAX := 12.0
const SOCKET_RETRY_JITTER := 0.6
const SOCKET_POLL_INTERVAL := 0.10
const AMBIENT_UPDATE_INTERVAL := 0.20
const MAX_CHAT_HISTORY := 12
const WALK_SPEED_MIN := 110.0
const WALK_SPEED_MAX := 230.0
const WALK_PAUSE_MIN := 1.2
const WALK_PAUSE_MAX := 3.8
const DESKTOP_MARGIN := 18.0
const MODEL_YAW_OFFSET := -PI * 0.5
const ZOOMY_SPEED_MULTIPLIER := 1.45
const ZOOMY_TRIGGER_CHANCE := 0.24
const ALERT_TRIGGER_CHANCE := 0.35
const ALERT_HOLD_MIN := 0.7
const ALERT_HOLD_MAX := 1.6
const CURSOR_REACT_DISTANCE := 160.0
const INTERACTION_COOLDOWN_MIN := 2.8
const INTERACTION_COOLDOWN_MAX := 5.4

@export var ollama_model: String = "qwen3:4b-q4_K_M"
@export var use_hologram_material: bool = false

@onready var model_anchor: Node3D = $World/ModelAnchor
@onready var bubble: PanelContainer = $UI/Root/Bubble
@onready var bubble_label: Label = $UI/Root/Bubble/BubbleLabel
@onready var chat_panel: PanelContainer = $UI/Root/ChatPanel
@onready var chat_log: RichTextLabel = $UI/Root/ChatPanel/Margin/VBox/ChatLog
@onready var chat_input: LineEdit = $UI/Root/ChatPanel/Margin/VBox/InputRow/ChatInput
@onready var send_button: Button = $UI/Root/ChatPanel/Margin/VBox/InputRow/SendButton
@onready var request: HTTPRequest = $UI/Root/HTTPRequest

var _socket := WebSocketPeer.new()
var _socket_retry_at := 0.0
var _socket_retry_delay := SOCKET_RETRY_BASE
var _socket_poll_elapsed := 0.0
var _ambient_update_elapsed := 0.0
var _bubble_timeout := 0.0
var _dragging := false
var _drag_offset := Vector2.ZERO
var _request_in_flight := false
var _time := 0.0
var _state := "idle"
var _rest_timer := 0.0
var _rest_duration := 0.0
var _walk_target := Vector2.ZERO
var _walk_speed := 0.0
var _walk_pause := 0.0
var _walk_facing := 1.0
var _alert_hold := 0.0
var _interaction_cooldown := 0.0
var _cursor_world := Vector2.ZERO
var _status_text := "ready"
var _chat_history: Array[Dictionary] = []
var _model_root: Node3D
var _model_animation_player: AnimationPlayer
var _known_animations: PackedStringArray = []
var _hologram_shader: Shader

const AMBIENT_LINES := [
    "Watching the room like it is my yard.",
    "Busy little Shiba patrol underway.",
    "Independent face. Loyal intentions.",
    "Leash still on. Escape plan still active.",
]

const PET_LINES := [
    "Mrrf. Acceptable. Keep going.",
    "Tail says yes. Face says act natural.",
    "I was patrolling, but this is fine.",
]

const NOTICE_LINES := [
    "Sniff check.",
    "Something moved. Probably important.",
    "Just checking the room again.",
]

const ZOOMY_LINES := [
    "Tiny security sprint. Very serious business.",
    "Zoom check. Floor approved.",
    "Quick patrol burst. No questions.",
]

const OFFLINE_REPLY_LINES := [
    "I'm here in desktop mate mode. Ollama is asleep, but I can still hang out.",
    "The local model is offline, so I'm running as a standalone Kai companion right now.",
    "Brain link is offline for the moment. The avatar part is still here and steady.",
]


func _ready() -> void:
    _configure_desktop_window()
    _load_3d_model()
    _seed_history()
    _set_bubble_text("Kai is here.")
    chat_panel.visible = false
    request.request_completed.connect(_on_request_completed)
    send_button.pressed.connect(_send_chat_message)
    chat_input.text_submitted.connect(_on_input_submitted)
    _socket_retry_at = Time.get_unix_time_from_system() + randf_range(0.2, 0.8)
    _walk_pause = randf_range(0.5, 1.8)
    _rest_duration = randf_range(4.5, 7.5)
    _walk_target = Vector2(DisplayServer.window_get_position())


func _process(delta: float) -> void:
    _time += delta
    _alert_hold = max(0.0, _alert_hold - delta)
    _interaction_cooldown = max(0.0, _interaction_cooldown - delta)
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
    if _ambient_update_elapsed >= AMBIENT_UPDATE_INTERVAL:
        _ambient_update_elapsed = 0.0
        _update_ambient_behavior(AMBIENT_UPDATE_INTERVAL)


func _input(event: InputEvent) -> void:
    if event is InputEventMouseButton:
        var mouse_event := event as InputEventMouseButton
        if mouse_event.button_index == MOUSE_BUTTON_LEFT:
            if mouse_event.pressed and not chat_panel.visible:
                _dragging = true
                _drag_offset = mouse_event.global_position - Vector2(DisplayServer.window_get_position())
                _state = "wag_tail"
                _alert_hold = randf_range(0.35, 0.8)
                _set_bubble_text(PET_LINES[randi() % PET_LINES.size()], 2.6)
            elif not mouse_event.pressed:
                _dragging = false
        elif mouse_event.button_index == MOUSE_BUTTON_RIGHT and mouse_event.pressed:
            chat_panel.visible = not chat_panel.visible
            if chat_panel.visible:
                chat_input.grab_focus()
                _set_bubble_text("Ask Kai anything.")
            else:
                _set_bubble_text("Right click to chat again.")
    elif event is InputEventMouseMotion and _dragging:
        var motion_event := event as InputEventMouseMotion
        var next_position := motion_event.global_position - _drag_offset
        DisplayServer.window_set_position(Vector2i(next_position))


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
    var packed := load(KAI_3D_MODEL_PATH)
    if packed is not PackedScene:
        _set_bubble_text("Kai 3D model failed to load.")
        return
    var instance := (packed as PackedScene).instantiate()
    if instance is not Node3D:
        _set_bubble_text("Kai 3D scene is invalid.")
        return
    _model_root = instance as Node3D
    _model_root.name = "KaiModel"
    model_anchor.add_child(_model_root)
    _model_root.position = Vector3(0.0, -1.0, 0.0)
    _model_root.scale = Vector3.ONE * 1.72
    if use_hologram_material:
        _apply_hologram_materials(_model_root)
    _model_animation_player = _find_first_animation_player(_model_root)
    if _model_animation_player != null:
        _known_animations = _model_animation_player.get_animation_list()
    _play_animation_prefer(["idle", "Idle", "RESET", "ArmatureAction"])


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


func _play_animation_prefer(candidates: Array[String]) -> void:
    if _model_animation_player == null or _known_animations.is_empty():
        return
    for name in candidates:
        if _model_animation_player.has_animation(name):
            _model_animation_player.play(name)
            return
    _model_animation_player.play(_known_animations[0])


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


func _update_cursor_reactions() -> void:
    if _dragging or chat_panel.visible or _state == "thinking" or _state == "walk" or _state == "rest":
        return
    if _interaction_cooldown > 0.0:
        return
    var center := _window_center()
    var distance := center.distance_to(_cursor_world)
    if distance > CURSOR_REACT_DISTANCE:
        return

    _interaction_cooldown = randf_range(INTERACTION_COOLDOWN_MIN, INTERACTION_COOLDOWN_MAX)
    _state = "alert"
    _alert_hold = randf_range(ALERT_HOLD_MIN, ALERT_HOLD_MAX)
    _walk_facing = -1.0 if _cursor_world.x < center.x else 1.0
    if distance < 90.0:
        _set_bubble_text(PET_LINES[randi() % PET_LINES.size()], 2.1)
    else:
        _set_bubble_text(NOTICE_LINES[randi() % NOTICE_LINES.size()], 2.0)


func _update_model_pose() -> void:
    if _model_root == null:
        return
    var bob := sin(_time * 2.0) * 0.04
    var sway := sin(_time * 1.35) * 0.05
    var head_tilt := sin(_time * 1.8) * 0.04
    _model_root.rotation.y = (0.0 if _walk_facing < 0.0 else PI) + MODEL_YAW_OFFSET
    _model_root.rotation.z = sway * 0.18

    match _state:
        "rest":
            _model_root.position = Vector3(0.0, -1.1, 0.0)
            _model_root.rotation.x = -0.18
            _model_root.rotation.z = -0.04
            _model_root.scale = Vector3.ONE * 1.62
        "walk":
            _model_root.position = Vector3(0.0, -0.96 + bob * 0.42, 0.0)
            _model_root.rotation.x = 0.08
            _model_root.rotation.z = sway * 0.24
            _model_root.scale = Vector3.ONE * (1.72 + sin(_time * 8.0) * 0.02)
            _play_animation_prefer(["trot", "Walk", "walk", "Run"])
            if _model_animation_player != null:
                _model_animation_player.speed_scale = max(0.85, _walk_speed / WALK_SPEED_MAX)
        "alert", "thinking", "wag_tail":
            _model_root.position = Vector3(0.0, -1.0 + bob * 0.2, 0.0)
            _model_root.rotation.x = -0.04
            _model_root.rotation.z = head_tilt
            _model_root.scale = Vector3.ONE * 1.7
            _play_animation_prefer(["idle", "Idle", "RESET", "ArmatureAction"])
        _:
            _model_root.position = Vector3(0.0, -1.0 + bob * 0.18, 0.0)
            _model_root.rotation.x = -0.02
            _model_root.rotation.z = head_tilt * 0.5
            _model_root.scale = Vector3.ONE * 1.68
            _play_animation_prefer(["idle", "Idle", "RESET", "ArmatureAction"])


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
    _set_bubble_text("Patrolling the desktop.", 2.6)


func _begin_zoomy() -> void:
    _pick_walk_target()
    _walk_speed *= ZOOMY_SPEED_MULTIPLIER
    _state = "walk"
    _walk_pause = 0.0
    _rest_timer = 0.0
    _set_bubble_text(ZOOMY_LINES[randi() % ZOOMY_LINES.size()], 2.2)


func _settle_after_walk() -> void:
    _walk_pause = randf_range(WALK_PAUSE_MIN, WALK_PAUSE_MAX)
    _rest_timer = 0.0
    _state = "idle" if randf() < 0.55 else "alert"
    if _state == "alert":
        _alert_hold = randf_range(ALERT_HOLD_MIN, ALERT_HOLD_MAX)
    if randf() < 0.5:
        _set_bubble_text(AMBIENT_LINES[randi() % AMBIENT_LINES.size()], 2.8)


func _update_desktop_patrol(delta: float) -> void:
    if _dragging or chat_panel.visible:
        return
    if _state == "rest":
        if _rest_timer >= _rest_duration:
            _state = "idle"
            _walk_pause = randf_range(0.6, 2.0)
        return
    if _state == "alert" and _alert_hold > 0.0:
        return
    if _state == "walk":
        var current := Vector2(DisplayServer.window_get_position())
        var next_position := current.move_toward(_walk_target, _walk_speed * delta)
        var screen_limit := _desktop_bounds()
        next_position.x = clamp(next_position.x, DESKTOP_MARGIN, screen_limit.x)
        next_position.y = clamp(next_position.y, DESKTOP_MARGIN, screen_limit.y)
        DisplayServer.window_set_position(Vector2i(next_position))
        if abs(next_position.x - current.x) > 0.1:
            _walk_facing = 1.0 if next_position.x > current.x else -1.0
        if next_position.distance_to(_walk_target) < 2.0:
            _settle_after_walk()
        return
    if _walk_pause > 0.0:
        _walk_pause = max(0.0, _walk_pause - delta)
        return
    if _state == "thinking":
        return
    if randf() < ZOOMY_TRIGGER_CHANCE:
        _begin_zoomy()
    elif randf() < 0.72:
        _begin_walk()
    else:
        _state = "idle" if randf() < 0.5 else "alert"
        if _state == "alert":
            _alert_hold = randf_range(ALERT_HOLD_MIN, ALERT_HOLD_MAX)
        _walk_pause = randf_range(WALK_PAUSE_MIN, WALK_PAUSE_MAX)


func _update_ambient_behavior(delta: float) -> void:
    if chat_panel.visible or _state == "thinking" or _dragging:
        return
    _rest_timer += delta
    if _state == "walk":
        return
    if _rest_timer > 18.0 and randf() < 0.22:
        _state = "rest"
        _rest_timer = 0.0
        _walk_pause = 0.0
        _rest_duration = randf_range(4.5, 8.5)
        _set_bubble_text("Taking a dramatic little Shiba break.", 3.0)
        return
    if randf() < ALERT_TRIGGER_CHANCE:
        _state = "alert"
        _alert_hold = randf_range(ALERT_HOLD_MIN, ALERT_HOLD_MAX)
        _set_bubble_text(NOTICE_LINES[randi() % NOTICE_LINES.size()], 2.4)


func _set_bubble_text(text: String, duration: float = 5.0) -> void:
    bubble.visible = true
    bubble_label.text = text
    _bubble_timeout = duration


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
    if result != HTTPRequest.RESULT_SUCCESS or response_code != 200:
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
    _set_bubble_text(content.left(54))


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
            _state = "thinking"
            _set_bubble_text("Focused and alert.")
        "kai_wag_tail":
            _state = "wag_tail"
            _set_bubble_text("Happy and a little proud.")
        "kai_sleep":
            _state = "rest"
            _set_bubble_text("Resting with one eye open.")
        "kai_walk":
            _state = "alert"
            _set_bubble_text("On patrol.")
        "kai_notice":
            _state = "alert"
            var notice_text := str(parsed_payload.get("text", "")).strip_edges()
            if notice_text.is_empty():
                notice_text = "I brought you a little message."
            _set_bubble_text(notice_text, 4.0)
        _:
            pass
