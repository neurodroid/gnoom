extends "res://addons/godot360/src/camera360.gd"

const WARP_MESH := preload("res://dome/fisheye_warp_mesh.gd")
const PROJECTOR_SHADER := preload("res://dome/dome_projection.gdshader")
const GNOME_SCREEN_RESOLUTION := preload("res://dome/gnome_screen_resolution.gd")
const PROJECTOR_RESOLUTION := Vector2i(1920, 1080)

@export var use_warp_mesh := true
@export var warp_mesh_path := "res://../blender/warp/meshwarp.data"
@export_range(0.5, 4.0, 0.001) var projector_aspect := 1.6
@export var front_truncated := true
@export var mirror_horizontal := false

var _settled_screen := -1
var _sampled_screen := -1
var _sampled_position: Vector2i


func _ready() -> void:
	# Godot360 captures the world from the same eye position in all directions.
	num_cameras = 6
	super._ready()
	render_quad.name = "ProjectorImage"
	render_quad.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	render_quad.material_override = mat
	mat.shader = PROJECTOR_SHADER
	mat.set_shader_parameter("fovx", fovx)
	mat.set_shader_parameter("subcamera_fov", camera_fov)
	mat.set_shader_parameter("projector_aspect", projector_aspect)
	mat.set_shader_parameter("front_truncated", front_truncated)
	mat.set_shader_parameter("mirror_horizontal", mirror_horizontal)

	var calibration: ArrayMesh
	if use_warp_mesh:
		calibration = WARP_MESH.load_mesh(warp_mesh_path, projector_aspect)
		if calibration == null:
			push_warning("Could not load the type-2 dome warp at %s. Showing the unwarped image." % warp_mesh_path)
	if calibration != null:
		render_quad.mesh = calibration
	mat.set_shader_parameter("apply_warp", calibration != null)
	mat.set_shader_parameter("output_aspect", projector_aspect if calibration != null or front_truncated else 1.0)

	for i in viewports.size():
		viewports[i].name = "CubeFace%d" % i
		viewports[i].render_target_update_mode = SubViewport.UPDATE_ALWAYS
		mat.set_shader_parameter("Texture%d" % i, viewports[i].get_texture())
	super._process(0.0)
	_watch_projector_window()


func _watch_projector_window() -> void:
	if DisplayServer.get_name() != "X11" or Engine.is_embedded_in_editor():
		return
	if get_window() != get_tree().root:
		return

	var poll := Timer.new()
	poll.wait_time = 0.25
	poll.autostart = true
	poll.timeout.connect(_update_projector_window)
	add_child(poll)


func _update_projector_window() -> void:
	var window := get_window()
	var screen := window.current_screen
	var position := window.position
	# Let the title-bar drag settle before asking the window manager for fullscreen.
	if screen != _sampled_screen or position != _sampled_position:
		_sampled_screen = screen
		_sampled_position = position
		return
	if screen == _settled_screen:
		return

	var moved_between_screens := _settled_screen >= 0
	_settled_screen = screen
	var is_windowed := window.mode == Window.MODE_WINDOWED or window.mode == Window.MODE_MAXIMIZED
	if not is_windowed:
		return

	var physical_size := GNOME_SCREEN_RESOLUTION.get_physical_resolution(screen)
	if moved_between_screens:
		if physical_size == PROJECTOR_RESOLUTION:
			window.mode = Window.MODE_FULLSCREEN
	elif window.mode == Window.MODE_WINDOWED and window.size == PROJECTOR_RESOLUTION:
		var screen_size := DisplayServer.screen_get_size(screen)
		if physical_size != screen_size and physical_size.x > 0 and physical_size.y > 0:
			var scale := Vector2(screen_size) / Vector2(physical_size)
			var preview_size := Vector2i((Vector2(PROJECTOR_RESOLUTION) * scale).round())
			var centered_position := window.position + (window.size - preview_size) / 2
			window.size = preview_size
			window.position = centered_position
