shader_type canvas_item;

uniform vec4 hologram_color : source_color = vec4(0.2, 0.9, 1.0, 1.0);
uniform float black_cutoff : hint_range(0.0, 0.3) = 0.05;
uniform float alpha_strength : hint_range(0.0, 2.0) = 1.1;
uniform float scanline_strength : hint_range(0.0, 1.0) = 0.12;
uniform float flicker_strength : hint_range(0.0, 1.0) = 0.04;

void fragment() {
	vec4 src = texture(TEXTURE, UV);
	if (src.a <= 0.01) {
		COLOR = vec4(0.0, 0.0, 0.0, 0.0);
	} else {
		float brightness = max(max(src.r, src.g), src.b);
		float mask = smoothstep(black_cutoff, black_cutoff + 0.08, brightness) * src.a;
		float scan = 0.82 + sin(UV.y * 420.0 - TIME * 4.0) * scanline_strength;
		float flicker = 1.0 - flicker_strength + flicker_strength * (0.5 + 0.5 * sin(TIME * 11.0 + UV.y * 35.0));
		vec3 tinted = hologram_color.rgb * (0.45 + brightness * 0.9) * scan * flicker;
		COLOR = vec4(tinted, clamp(mask * (0.35 + brightness * 0.65) * alpha_strength, 0.0, 0.9));
	}
}
