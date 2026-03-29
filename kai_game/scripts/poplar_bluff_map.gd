## Poplar Bluff Map Loader
## Reads OSM feature data and builds the game world.
## Streets as Line2D paths, buildings as StaticBody2D collision shapes.
extends Node2D
class_name PoplarBluffMap

const FEATURES_PATH := "res://poplar_bluff_features.json"

# Visual settings
@export var street_width: float = 16.0
@export var street_color: Color = Color(0.35, 0.35, 0.38)
@export var building_color: Color = Color(0.45, 0.38, 0.30)
@export var park_color: Color = Color(0.25, 0.45, 0.20)
@export var ground_color: Color = Color(0.30, 0.42, 0.25)
@export var fence_color: Color = Color(0.55, 0.45, 0.30)

# Scale: game units per OSM meter
@export var scale_factor: float = 1.0

var features: Dictionary = {}
var street_lines: Array = []
var building_bodies: Array = []


func _ready() -> void:
	_load_features()
	_build_world()


func _load_features() -> void:
	if not FileAccess.file_exists(FEATURES_PATH):
		push_warning("Poplar Bluff features file not found: " + FEATURES_PATH)
		return
	var file := FileAccess.open(FEATURES_PATH, FileAccess.READ)
	var text := file.get_as_text()
	file.close()
	features = JSON.parse_string(text)
	if features == null:
		features = {}


func _build_world() -> void:
	if features.is_empty():
		return
	_build_ground()
	_build_streets()
	_build_buildings()
	_build_parks()
	_place_spawn()


func _build_ground() -> void:
	# Background color fill based on bounds
	var bounds = features.get("bounds", {})
	var min_x: float = bounds.get("min_x", -500) * scale_factor
	var min_y: float = bounds.get("min_y", -500) * scale_factor
	var max_x: float = bounds.get("max_x", 500) * scale_factor
	var max_y: float = bounds.get("max_y", 500) * scale_factor
	
	var bg := ColorRect.new()
	bg.color = ground_color
	bg.position = Vector2(min_x - 200, min_y - 200)
	bg.size = Vector2(max_x - min_x + 400, max_y - min_y + 400)
	bg.z_index = -10
	add_child(bg)


func _build_streets() -> void:
	for street in features.get("streets", []):
		var coords: Array = street.get("coords", [])
		if coords.size() < 2:
			continue
		
		var points := PackedVector2Array()
		for coord in coords:
			points.append(Vector2(coord[0], coord[1]) * scale_factor)
		
		# Draw street as thick line
		var line := Line2D.new()
		line.points = points
		line.width = street_width
		line.default_color = street_color
		line.begin_cap_mode = Line2D.LINE_CAP_ROUND
		line.end_cap_mode = Line2D.LINE_CAP_ROUND
		line.joint_mode = Line2D.LINE_JOINT_ROUND
		line.z_index = -5
		
		# Add street name label for named streets
		var name_label: String = street.get("name", "")
		if name_label != "":
			line.name = "Street_" + name_label
		
		add_child(line)
		street_lines.append(line)
		
		# Also draw center line (yellow dashed effect via thinner line)
		var center := Line2D.new()
		center.points = points
		center.width = 1.5
		center.default_color = Color(0.6, 0.55, 0.2, 0.4)
		center.begin_cap_mode = Line2D.LINE_CAP_ROUND
		center.end_cap_mode = Line2D.LINE_CAP_ROUND
		center.joint_mode = Line2D.LINE_JOINT_ROUND
		center.z_index = -4
		add_child(center)


func _build_buildings() -> void:
	for building in features.get("buildings", []):
		var coords: Array = building.get("coords", [])
		if coords.size() < 3:
			continue
		
		var points := PackedVector2Array()
		for coord in coords:
			points.append(Vector2(coord[0], coord[1]) * scale_factor)
		
		# Closed polygon
		if points[0] != points[-1]:
			points.append(points[0])
		
		# Static body for collision
		var body := StaticBody2D.new()
		body.collision_layer = 4  # Walls layer
		body.collision_mask = 0
		
		var shape := CollisionPolygon2D.new()
		shape.polygon = points
		body.add_child(shape)
		add_child(body)
		building_bodies.append(body)
		
		# Visual polygon
		var poly := Polygon2D.new()
		poly.polygon = points
		poly.color = building_color
		poly.z_index = -3
		add_child(poly)
		
		# Outline
		var outline := Line2D.new()
		outline.points = points
		outline.width = 1.5
		outline.default_color = Color(0.35, 0.28, 0.20)
		outline.z_index = -2
		add_child(outline)


func _build_parks() -> void:
	for park in features.get("parks", []):
		var coords: Array = park.get("coords", [])
		if coords.size() < 3:
			continue
		
		var points := PackedVector2Array()
		for coord in coords:
			points.append(Vector2(coord[0], coord[1]) * scale_factor)
		
		if points[0] != points[-1]:
			points.append(points[0])
		
		var poly := Polygon2D.new()
		poly.polygon = points
		poly.color = park_color
		poly.z_index = -6
		add_child(poly)
		
		# Park label
		var lbl := Label.new()
		var center := Vector2.ZERO
		for p in points:
			center += p
		center /= points.size()
		lbl.text = "🌳 " + park.get("name", "Park")
		lbl.position = center - Vector2(30, 8)
		lbl.add_theme_font_size_override("font_size", 12)
		lbl.modulate = Color(1, 1, 1, 0.7)
		lbl.z_index = 1
		add_child(lbl)


func _place_spawn() -> void:
	# Place player spawn near map center
	var bounds = features.get("bounds", {})
	var cx: float = ((bounds.get("min_x", 0) + bounds.get("max_x", 0)) / 2.0) * scale_factor
	var cy: float = ((bounds.get("min_y", 0) + bounds.get("max_y", 0)) / 2.0) * scale_factor
	
	# Try to find a street intersection to spawn on
	var spawn_marker := Marker2D.new()
	spawn_marker.position = Vector2(cx, cy)
	spawn_marker.name = "PlayerSpawn"
	add_child(spawn_marker)


func get_spawn_position() -> Vector2:
	var spawn := get_node_or_null("PlayerSpawn")
	if spawn:
		return spawn.position
	return Vector2.ZERO


func get_street_names() -> Array:
	var names := []
	for street in features.get("streets", []):
		var n = street.get("name", "")
		if n != "" and n not in names:
			names.append(n)
	return names
