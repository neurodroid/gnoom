extends RefCounted

const DISPLAY_CONFIG := "org.gnome.Mutter.DisplayConfig"


static func get_physical_resolution(screen: int) -> Vector2i:
	var screen_size := DisplayServer.screen_get_size(screen)
	if OS.get_environment("XDG_SESSION_TYPE") != "wayland" or not FileAccess.file_exists("/usr/bin/busctl"):
		return screen_size
	if "GNOME" not in OS.get_environment("XDG_CURRENT_DESKTOP").to_upper():
		return screen_size

	var output := []
	var result := OS.execute("/usr/bin/busctl", [
		"--user", "--json=short", "--timeout=1s", "call", DISPLAY_CONFIG,
		"/org/gnome/Mutter/DisplayConfig", DISPLAY_CONFIG, "GetCurrentState",
	], output)
	if result != 0 or output.is_empty():
		return screen_size

	var reply: Variant = JSON.parse_string(output[0])
	if not reply is Dictionary or reply.get("type") != "ua((ssss)a(siiddada{sv})a{sv})a(iiduba(ssss)a{sv})a{sv}":
		return screen_size

	var screens: Array[Rect2i] = []
	for index in DisplayServer.get_screen_count():
		screens.append(Rect2i(DisplayServer.screen_get_position(index), DisplayServer.screen_get_size(index)))
	if screen < 0 or screen >= screens.size():
		return screen_size
	return _match_resolution(reply["data"], screens, screen)


static func _match_resolution(state: Array, screens: Array[Rect2i], screen: int) -> Vector2i:
	var target := screens[screen]
	if int(state[3].get("layout-mode", {}).get("data", 1)) == 2:
		return target.size

	# Mutter lists physical modes by connector and logical desktop rectangles separately.
	var active_modes: Dictionary[String, Vector2i] = {}
	for monitor: Array in state[1]:
		for mode: Array in monitor[1]:
			if mode[6].get("is-current", {}).get("data", false):
				active_modes[monitor[0][0]] = Vector2i(int(mode[1]), int(mode[2]))
				break

	var logical_displays: Dictionary[Rect2i, Vector2i] = {}
	var largest_logical_width := 0
	for monitor: Array in state[2]:
		var physical: Vector2i = active_modes.get(monitor[5][0][0], Vector2i.ZERO)
		if physical == Vector2i.ZERO:
			return target.size
		if int(monitor[3]) % 2 != 0:
			physical = Vector2i(physical.y, physical.x)
		var logical_size := Vector2i((Vector2(physical) / float(monitor[2])).round())
		var logical_position := Vector2i(int(monitor[0]), int(monitor[1]))
		logical_displays[Rect2i(logical_position, logical_size)] = physical
		largest_logical_width = maxi(largest_logical_width, logical_size.x)
	if largest_logical_width == 0:
		return target.size

	# XWayland multiplies all logical monitor rectangles by the same integer scale.
	var largest_x11_width := 0
	for bounds in screens:
		largest_x11_width = maxi(largest_x11_width, bounds.size.x)
	var xwayland_scale := roundi(float(largest_x11_width) / largest_logical_width)
	for bounds in logical_displays:
		if Rect2i(bounds.position * xwayland_scale, bounds.size * xwayland_scale) == target:
			return logical_displays[bounds]
	return target.size
