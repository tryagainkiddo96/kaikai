shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

uniform vec4 base_black : source_color = vec4(0.07, 0.07, 0.07, 1.0);
uniform vec4 tan_color : source_color = vec4(0.71, 0.54, 0.33, 1.0);
uniform vec4 cream_color : source_color = vec4(0.88, 0.82, 0.69, 1.0);
uniform vec4 nose_tint : source_color = vec4(0.05, 0.04, 0.04, 1.0);
uniform float happy_strength : hint_range(0.0, 1.0) = 0.0;
uniform float thinking_strength : hint_range(0.0, 1.0) = 0.0;

varying vec3 local_pos;
varying vec3 local_normal;

float band(float a, float b, float value) {
	return smoothstep(a, b, value);
}

void vertex() {
	local_pos = VERTEX;
	local_normal = NORMAL;
}

void fragment() {
	vec3 p = local_pos;
	vec3 n = normalize(local_normal);

	float vertical = clamp((p.y + 1.0) * 0.5, 0.0, 1.0);
	float chest = band(-0.15, 0.12, p.z) * band(-0.18, 0.18, abs(p.x)) * (1.0 - band(0.18, 0.52, p.y));
	float muzzle = band(0.2, 0.6, p.z) * (1.0 - band(0.18, 0.48, abs(p.x))) * band(0.15, 0.62, p.y);
	float underside = band(-0.2, 0.18, p.z) * (1.0 - vertical);
	float leg_tan = (1.0 - band(0.02, 0.36, p.y)) * (0.35 + band(0.18, 0.55, abs(p.x)));
	float cheek_tan = band(0.12, 0.55, p.z) * band(0.28, 0.6, abs(p.x)) * band(0.18, 0.7, p.y);
	float brow_tan = band(0.48, 0.74, p.y) * band(0.08, 0.24, abs(p.x)) * band(0.3, 0.6, p.z);
	float tail_tip = band(0.38, 0.75, p.y) * band(-0.1, 0.25, p.z) * band(0.26, 0.7, abs(p.x));
	float inner_ear = band(0.45, 0.82, p.y) * band(0.14, 0.36, abs(p.x)) * band(-0.02, 0.24, p.z);
	float nose_mask = band(0.42, 0.68, p.z) * (1.0 - band(0.06, 0.15, abs(p.x))) * band(0.12, 0.34, p.y);

	float cream_mask = clamp(max(max(chest, muzzle), max(underside * 0.85, tail_tip)), 0.0, 1.0);
	float tan_mask = clamp(max(max(leg_tan, cheek_tan), max(brow_tan, inner_ear * 0.8)), 0.0, 1.0) * (1.0 - cream_mask);

	vec3 coat = base_black.rgb;
	coat = mix(coat, tan_color.rgb, tan_mask);
	coat = mix(coat, cream_color.rgb, cream_mask);
	coat = mix(coat, nose_tint.rgb, nose_mask);

	float fur_noise = sin(p.x * 35.0) * sin(p.y * 28.0) * sin(p.z * 23.0) * 0.03;
	coat += fur_noise;

	float top_highlight = band(0.28, 0.9, dot(n, vec3(0.0, 1.0, 0.0))) * 0.08;
	float happy_glow = happy_strength * 0.05;
	coat += vec3(top_highlight + happy_glow);

	ALBEDO = clamp(coat, vec3(0.0), vec3(1.0));
	ROUGHNESS = 0.88;
	SPECULAR = 0.18;
	RIM = 0.35 + (happy_strength * 0.15);
	RIM_TINT = 0.12;
	CLEARCOAT = 0.12;
	EMISSION = vec3(0.03, 0.05, 0.06) * thinking_strength;
}
