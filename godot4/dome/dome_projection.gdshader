shader_type spatial;
render_mode unshaded, cull_disabled, depth_test_disabled, shadows_disabled, fog_disabled;

uniform float fovx = 250.0;
uniform float subcamera_fov = 100.0;
uniform float projector_aspect = 1.6;
uniform float output_aspect = 1.6;
uniform bool front_truncated = true;
uniform bool mirror_horizontal = false;
uniform bool apply_warp = true;
uniform bool cut_sphere = false;
uniform vec3 eye_offset_in_radii = vec3(0.0);
uniform bool calibration_target = false;
uniform vec2 calibration_angles_deg = vec2(0.0);

// Both cut planes are 35 degrees past the corresponding hemisphere boundary.
const float CUT_SPHERE_LIMIT = 0.57357644; // sin(35 degrees)
const float CUT_SPHERE_EDGE_TOLERANCE = 0.000001;

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

float crosshair(vec2 distance_deg, float half_length, float half_width) {
	vec2 strokes = 1.0 - smoothstep(vec2(half_width), vec2(half_width + 0.18), distance_deg);
	vec2 ends = 1.0 - smoothstep(vec2(half_length), vec2(half_length + 0.18), distance_deg);
	return max(strokes.x * ends.y, strokes.y * ends.x);
}

vec3 sample_calibration_target(vec3 ray) {
	float horizontal = length(ray.xz);
	float azimuth = horizontal > 0.00001 ? degrees(atan(ray.x, -ray.z)) : 0.0;
	float elevation = degrees(atan(ray.y, horizontal));
	vec2 angles = vec2(azimuth, elevation);
	vec2 grid_distance = abs(mod(angles + vec2(5.0), vec2(10.0)) - vec2(5.0));
	// Longitude converges at the poles, where azimuth has no unique value.
	float azimuth_fade = smoothstep(0.015, 0.08, horizontal);
	float grid = crosshair(grid_distance, 1.35, 0.19) * azimuth_fade;
	vec3 color = mix(vec3(0.035), vec3(0.86), grid);

	float horizon = 1.0 - smoothstep(0.20, 0.40, abs(elevation));
	vec3 horizon_color = azimuth < 0.0 ? vec3(0.94, 0.24, 0.22) : vec3(0.22, 0.86, 0.44);
	color = mix(color, horizon_color, horizon);
	float meridian = (1.0 - smoothstep(0.20, 0.40, abs(azimuth))) * azimuth_fade;
	color = mix(color, vec3(0.24, 0.64, 0.95), meridian);

	vec2 target_distance = angles - calibration_angles_deg;
	target_distance.x = mod(target_distance.x + 180.0, 360.0) - 180.0;
	target_distance.x *= max(cos(radians(calibration_angles_deg.y)), 0.15);
	float target = crosshair(abs(target_distance), 2.8, 0.42);
	return mix(color, vec3(1.0, 0.83, 0.20), target);
}

void vertex() {
	float viewport_aspect = VIEWPORT_SIZE.x / VIEWPORT_SIZE.y;
	vec2 fit = min(vec2(output_aspect / viewport_aspect, viewport_aspect / output_aspect), vec2(1.0));
	// Direct clip coordinates bypass Godot's projection-matrix Y correction.
	POSITION = vec4(vec2(VERTEX.x, -VERTEX.y) * fit, 1.0, 1.0);
}

void fragment() {
	// The legacy source texture clamps at its edges. Cut-sphere UVs use the physical mask.
	vec2 source_uv = cut_sphere ? UV : clamp(UV, vec2(0.0), vec2(1.0));
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
		float cut_limit = CUT_SPHERE_LIMIT + CUT_SPHERE_EDGE_TOLERANCE;
		if (!cut_sphere || (ray.y >= -cut_limit && ray.z <= cut_limit)) {
			if (cut_sphere) {
				// The warp locates the surface point. Sample it from the physical eye.
				ray = normalize(ray - eye_offset_in_radii);
			}
			vec3 color = calibration_target ? sample_calibration_target(ray) : sample_godot360(ray);
			color *= gain;
			if (!OUTPUT_IS_SRGB) {
				color = mix(color / 12.92, pow((color + 0.055) / 1.055, vec3(2.4)), step(0.04045, color));
			}
			ALBEDO = color;
		}
	}
}
