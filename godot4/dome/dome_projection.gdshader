shader_type spatial;
render_mode unshaded, cull_disabled, depth_test_disabled, shadows_disabled, fog_disabled;

uniform float fovx = 250.0;
uniform float subcamera_fov = 100.0;
uniform float projector_aspect = 1.6;
uniform float output_aspect = 1.6;
uniform bool front_truncated = true;
uniform bool mirror_horizontal = false;
uniform bool apply_warp = true;

uniform sampler2D Texture0 : hint_default_black, filter_linear, repeat_disable;
uniform sampler2D Texture1 : hint_default_black, filter_linear, repeat_disable;
uniform sampler2D Texture2 : hint_default_black, filter_linear, repeat_disable;
uniform sampler2D Texture3 : hint_default_black, filter_linear, repeat_disable;
uniform sampler2D Texture4 : hint_default_black, filter_linear, repeat_disable;
uniform sampler2D Texture5 : hint_default_black, filter_linear, repeat_disable;

vec3 sample_godot360(vec3 ray) {
	vec3 a = abs(ray);
	float scale = 0.5 / tan(radians(subcamera_fov * 0.5));
	vec2 center = vec2(0.5);
	if (a.z >= a.x && a.z >= a.y) {
		if (ray.z < 0.0) {
			return texture(Texture0, center + vec2(ray.x, -ray.y) * scale / a.z).rgb;
		}
		return texture(Texture5, center + vec2(-ray.x, -ray.y) * scale / a.z).rgb;
	}
	if (a.x >= a.y) {
		if (ray.x < 0.0) {
			return texture(Texture1, center + vec2(-ray.z, -ray.y) * scale / a.x).rgb;
		}
		return texture(Texture2, center + vec2(ray.z, -ray.y) * scale / a.x).rgb;
	}
	if (ray.y < 0.0) {
		return texture(Texture3, center + vec2(ray.x, ray.z) * scale / a.y).rgb;
	}
	return texture(Texture4, center + vec2(ray.x, -ray.z) * scale / a.y).rgb;
}

void vertex() {
	float viewport_aspect = VIEWPORT_SIZE.x / VIEWPORT_SIZE.y;
	vec2 fit = min(vec2(output_aspect / viewport_aspect, viewport_aspect / output_aspect), vec2(1.0));
	// Direct clip coordinates bypass Godot's projection-matrix Y correction.
	POSITION = vec4(vec2(VERTEX.x, -VERTEX.y) * fit, 1.0, 1.0);
}

void fragment() {
	// The legacy texture clamps at its edges. The fisheye itself has a circular mask.
	vec2 source_uv = clamp(UV, vec2(0.0), vec2(1.0));
	float source_height = front_truncated ? 2.0 / projector_aspect : 2.0;
	vec2 disk = vec2(2.0 * source_uv.x - 1.0, 1.0 - source_height * source_uv.y);
	if (mirror_horizontal) {
		disk.x = -disk.x;
	}
	float radius = length(disk);
	float gain = apply_warp ? COLOR.r : 1.0;
	ALBEDO = vec3(0.0);
	if (radius <= 1.0 && gain > 0.0) {
		float theta = radius * radians(fovx * 0.5);
		float radial_scale = sin(theta) / max(radius, 0.000001);
		vec3 ray = vec3(disk * radial_scale, -cos(theta));
		vec3 color = sample_godot360(ray) * gain;
		if (!OUTPUT_IS_SRGB) {
			color = mix(color / 12.92, pow((color + 0.055) / 1.055, vec3(2.4)), step(0.04045, color));
		}
		ALBEDO = color;
	}
}
