shader_type spatial;
render_mode blend_add, depth_draw_always, cull_back, unshaded;

uniform vec4 hologram_color : source_color = vec4(0.18, 0.92, 1.0, 0.24);
uniform vec4 rim_color : source_color = vec4(0.75, 0.98, 1.0, 1.0);
uniform float rim_power : hint_range(0.5, 8.0) = 3.2;
uniform float line_density : hint_range(20.0, 220.0) = 84.0;
uniform float line_strength : hint_range(0.0, 1.0) = 0.14;
uniform float flicker_strength : hint_range(0.0, 1.0) = 0.03;
uniform float pulse_speed : hint_range(0.1, 8.0) = 0.45;

varying vec3 world_pos;
varying vec3 world_normal;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	world_normal = normalize(MODEL_NORMAL_MATRIX * NORMAL);
}

void fragment() {
	vec3 view_dir = normalize(CAMERA_POSITION_WORLD - world_pos);
	float fresnel = pow(1.0 - max(dot(normalize(world_normal), view_dir), 0.0), rim_power);
	float scan = 0.5 + 0.5 * sin(world_pos.y * line_density - TIME * 6.0);
	float pulse = 0.8 + 0.2 * sin(TIME * pulse_speed);
	float flicker = 1.0 - flicker_strength + flicker_strength * (0.5 + 0.5 * sin(TIME * 14.0 + world_pos.x * 5.0));
	float alpha = (hologram_color.a + fresnel * 0.45 + scan * line_strength) * pulse * flicker;
	vec3 color = hologram_color.rgb * (0.7 + scan * 0.35) + rim_color.rgb * fresnel * 0.9;

	ALBEDO = color;
	EMISSION = color * (1.4 + fresnel * 1.2) * pulse;
	ALPHA = clamp(alpha, 0.0, 0.95);
}
