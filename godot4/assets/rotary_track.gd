extends Node3D

const BAUD_RATE := 115200
const RETRY_SECONDS := 1.0
const READ_LIMIT := 4096
const SERIAL_DEBUG_INTERVAL_MS := 1000
const SERIAL_DEBUG_SAMPLE_SIZE := 12
const KEYBOARD_SPEED := 0.4 # Meters per second.
const TRACK_END_TOLERANCE := 1.0e-7 # Meters, for rounding in the 3D marker positions.

@export var serial_port := ""
@export_range(0.000001, 0.1, 0.000001, "or_greater", "suffix:m") var meters_per_step := 0.0001
@export var invert_encoder := false

@onready var _camera: Camera3D = $DemoCamera
@onready var _start: Node3D = $LinearTrack/TrackStart
@onready var _finish: Node3D = $LinearTrack/TrackEnd

var _track_start: Vector3
var _track_direction: Vector3
var _track_length: float
var _distance: float
var _port: String
var _retry_in := 0.0
var _last_status := ""
var _serial_debug := false
var _serial_debug_counts := Vector3i.ZERO
var _serial_debug_sample := PackedByteArray()
var _serial_debug_next_report_ms := 0

var _manager: Object
var _native_open := false
var _native_disconnected := false
var _bridge: Dictionary = {}


func _ready() -> void:
	_track_start = to_local(_start.global_position)
	var segment := to_local(_finish.global_position) - _track_start
	_track_length = segment.length()
	if is_zero_approx(_track_length):
		push_error("Track motion requires distinct start and end markers.")
		set_process(false)
		return
	_track_direction = segment / _track_length
	_distance = clampf((_camera.position - _track_start).dot(_track_direction), 0.0, _track_length)

	_port = OS.get_environment("GNOOM_SERIAL_PORT").strip_edges()
	if _port.is_empty():
		_port = serial_port.strip_edges()
	if _port.is_empty():
		_report("Set Serial Port or GNOOM_SERIAL_PORT to drive the demo with Arduino.")
		return
	if meters_per_step <= 0.0:
		push_error("Encoder motion requires a positive meters_per_step.")
		_port = ""
		return
	_serial_debug = OS.get_environment("GNOOM_SERIAL_DEBUG") == "1"

	# Resolve the optional extension at runtime so the scene opens without it.
	if ClassDB.class_exists(&"GdSerialManager"):
		_manager = ClassDB.instantiate(&"GdSerialManager")
		_manager.connect(&"data_received", _on_serial_data)
		_manager.connect(&"port_disconnected", _on_serial_disconnect)
	elif OS.get_name() != "Linux":
		push_error("Install GdSerial 0.3.4 or later for encoder input on this platform.")
		_port = ""
		return
	_connect_serial()


func _process(delta: float) -> void:
	var direction := Input.get_action_strength(&"ui_up", true) - Input.get_action_strength(&"ui_down", true)
	if direction != 0.0 and not Input.is_key_pressed(KEY_CTRL):
		_advance(direction * KEYBOARD_SPEED * delta)
		_update_camera_position()
	if _port.is_empty():
		return

	if _native_open:
		_manager.poll_events()
		if _native_disconnected:
			_manager.close(_port)
			_native_open = false
			_native_disconnected = false
			_report("Disconnected from %s. Retrying." % _port)
			_retry_in = RETRY_SECONDS
	elif not _bridge.is_empty():
		_poll_bridge()
	else:
		_retry_in -= delta
		if _retry_in <= 0.0:
			_connect_serial()
	if _serial_debug:
		_report_serial_data()


func _connect_serial() -> void:
	_retry_in = RETRY_SECONDS
	if _manager != null:
		# Raw mode preserves 0x00 and delivers data without waiting for a newline.
		_native_open = _manager.open(_port, BAUD_RATE, 20, 0)
		if _native_open:
			_report("Connected to %s via GdSerial." % _port)
		else:
			_report("Could not open %s via GdSerial. Retrying." % _port)
		return

	var bridge_path := get_script().resource_path.get_base_dir().path_join("rotary_serial.py") as String
	var arguments := PackedStringArray(["-u", ProjectSettings.globalize_path(bridge_path), _port])
	_bridge = OS.execute_with_pipe("/usr/bin/python3", arguments, false)
	if _bridge.is_empty():
		_report("Could not start the Linux serial reader. Retrying.")


func _poll_bridge() -> void:
	var running := OS.is_process_running(_bridge["pid"])
	var stdout: FileAccess = _bridge["stdio"]
	var stderr: FileAccess = _bridge["stderr"]
	var bytes := _read_available(stdout)
	if not bytes.is_empty():
		_apply_steps(bytes)
	var message := _read_available(stderr).get_string_from_utf8().strip_edges()
	if message == "READY":
		_report("Connected to %s via the Linux serial reader." % _port)
	elif not message.is_empty():
		_report(message)
	if not running and stdout.get_length() == 0 and stderr.get_length() == 0:
		_bridge.clear()
		_retry_in = RETRY_SECONDS


static func _read_available(pipe: FileAccess) -> PackedByteArray:
	var count := mini(pipe.get_length(), READ_LIMIT)
	return pipe.get_buffer(count) if count > 0 else PackedByteArray()


func _on_serial_data(port: String, bytes: PackedByteArray) -> void:
	if port == _port:
		_apply_steps(bytes)


func _on_serial_disconnect(port: String) -> void:
	if port == _port:
		_native_disconnected = true


func _apply_steps(bytes: PackedByteArray) -> void:
	if _serial_debug and not bytes.is_empty():
		var ones := bytes.count(1)
		var zeros := bytes.count(0)
		_serial_debug_counts += Vector3i(ones, zeros, bytes.size() - ones - zeros)
		if _serial_debug_sample.is_empty():
			_serial_debug_sample = bytes.slice(0, SERIAL_DEBUG_SAMPLE_SIZE)

	var step := -meters_per_step if invert_encoder else meters_per_step
	for value in bytes:
		match value:
			0:
				_advance(-step)
			1:
				_advance(step)
	_update_camera_position()


func _report_serial_data() -> void:
	if _serial_debug_sample.is_empty():
		return
	var now := Time.get_ticks_msec()
	if now < _serial_debug_next_report_ms:
		return
	print("Encoder data on %s: 0x01=%d, 0x00=%d, other=%d, sample=%s, track=%.4f m" % [
		_port, _serial_debug_counts.x, _serial_debug_counts.y, _serial_debug_counts.z,
		_serial_debug_sample.hex_encode(), _distance,
	])
	_serial_debug_counts = Vector3i.ZERO
	_serial_debug_sample.clear()
	_serial_debug_next_report_ms = now + SERIAL_DEBUG_INTERVAL_MS


func _advance(meters: float) -> void:
	_distance = maxf(_distance + meters, 0.0)
	if meters > 0.0 and _distance >= _track_length - TRACK_END_TOLERANCE:
		_distance = 0.0


func _update_camera_position() -> void:
	_camera.position = _track_start + _track_direction * _distance


func _report(message: String) -> void:
	if message != _last_status:
		_last_status = message
		print("Encoder: ", message)


func _exit_tree() -> void:
	if _native_open:
		_manager.close(_port)
	# Dropping the pipes closes the reader's stdin and lets it exit cleanly.
	_bridge.clear()
