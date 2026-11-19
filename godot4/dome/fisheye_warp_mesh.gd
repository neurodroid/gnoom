extends RefCounted


static func load_mesh(path: String, aspect: float) -> ArrayMesh:
	var file := FileAccess.open(ProjectSettings.globalize_path(path).simplify_path(), FileAccess.READ)
	if file == null or file.get_line().strip_edges() != "2":
		return null
	var dimensions := _fields(file.get_line())
	if dimensions.size() != 2 or not dimensions[0].is_valid_int() or not dimensions[1].is_valid_int():
		return null
	var width := dimensions[0].to_int()
	var height := dimensions[1].to_int()
	if width < 2 or height < 2:
		return null

	var vertices := PackedVector3Array()
	var uvs := PackedVector2Array()
	var intensities := PackedColorArray()
	for i in width * height:
		var fields := _fields(file.get_line())
		if fields.size() != 5:
			return null
		var values := PackedFloat32Array()
		for field in fields:
			var value := field.to_float()
			if not field.is_valid_float() or not is_finite(value):
				return null
			values.append(value)
		vertices.append(Vector3(values[0] / aspect, values[1], 0.0))
		uvs.append(Vector2(values[2], 1.0 - values[3]))
		intensities.append(Color(values[4], values[4], values[4], 1.0))

	var indices := PackedInt32Array()
	for row in height - 1:
		for column in width - 1:
			var lower_left := row * width + column
			var lower_right := lower_left + 1
			var upper_left := lower_left + width
			var upper_right := upper_left + 1
			# The Blender type-2 renderer omits the whole cell for a negative gain.
			if minf(minf(intensities[lower_left].r, intensities[lower_right].r),
					minf(intensities[upper_left].r, intensities[upper_right].r)) < 0.0:
				continue
			indices.append_array([lower_left, lower_right, upper_right, lower_left, upper_right, upper_left])
	if indices.is_empty():
		return null

	var arrays: Array = []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = vertices
	arrays[Mesh.ARRAY_TEX_UV] = uvs
	arrays[Mesh.ARRAY_COLOR] = intensities
	arrays[Mesh.ARRAY_INDEX] = indices
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	return mesh


static func _fields(line: String) -> PackedStringArray:
	return line.replace("\t", " ").split(" ", false)
