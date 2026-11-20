#!/usr/bin/env python3
"""Generate a Godot type-2 warp for the Optoma ZH507+ and Seton JB DDOME4."""

from argparse import ArgumentParser, Namespace
from math import acos, cos, hypot, isfinite, radians, sin, sqrt
from pathlib import Path


DOME_RADIUS_M = 0.60
DOME_HALF_FOV = radians(125.0)
DOME_CUT_M = DOME_RADIUS_M * sin(radians(35.0))
# Keep parent-sphere UVs just beyond the cuts, so the shader can trim interpolated cells.
DOME_CUT_WITH_MARGIN_M = DOME_CUT_M + 0.06
PROJECTOR_ASPECT = 16 / 9
PROJECTOR_THROW = 1.40
BASELINE_MESH = Path(__file__).with_name("optoma_zh507plus_seton_ddome4.data")

Vector = tuple[float, float, float]


def dot(a: Vector, b: Vector) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def sphere_distances(
    origin_from_center: Vector, direction: Vector, radius: float
) -> tuple[float, float] | None:
    along = dot(origin_from_center, direction)
    discriminant = along * along + radius * radius - dot(origin_from_center, origin_from_center)
    if discriminant < 0:
        return None
    half_chord = sqrt(discriminant)
    return -along - half_chord, -along + half_chord


def trace_ray(
    lens: Vector, direction: Vector, mirror_center: Vector, mirror_radius: float
) -> tuple[float, float] | None:
    lens_from_mirror = tuple(a - b for a, b in zip(lens, mirror_center))
    distances = sphere_distances(lens_from_mirror, direction, mirror_radius)
    if distances is None or distances[0] <= 0:
        return None

    to_mirror = distances[0]
    mirror_hit = tuple(a + to_mirror * b for a, b in zip(lens, direction))
    normal = tuple((a - b) / mirror_radius for a, b in zip(mirror_hit, mirror_center))
    # The half-dome mirror is mounted with its convex quarter sphere up and into the dome.
    if normal[1] < 0 or normal[2] > 0:
        return None

    incoming_crossings = sphere_distances(lens, direction, DOME_RADIUS_M)
    for crossing in incoming_crossings or ():
        if 0 < crossing < to_mirror:
            y = lens[1] + crossing * direction[1]
            z = lens[2] + crossing * direction[2]
            if y >= -DOME_CUT_M and z <= DOME_CUT_M:
                return None

    normal_component = 2 * dot(direction, normal)
    reflected = tuple(a - normal_component * b for a, b in zip(direction, normal))
    distances = sphere_distances(mirror_hit, reflected, DOME_RADIUS_M)
    if distances is None or distances[1] <= 0:
        return None

    to_dome = distances[1]
    x, y, z = (a + to_dome * b for a, b in zip(mirror_hit, reflected))
    if y < -DOME_CUT_WITH_MARGIN_M or z > DOME_CUT_WITH_MARGIN_M:
        return None
    theta = acos(max(-1.0, min(1.0, -z / DOME_RADIUS_M)))
    radial = hypot(x, y)
    if radial < 1e-12:
        return 0.5, 0.5
    scale = theta / (2 * DOME_HALF_FOV * radial)
    return 0.5 + x * scale, 0.5 + y * scale


def write_warp(args: Namespace) -> int:
    width, height = args.grid
    lens, mirror_center = tuple(args.lens), tuple(args.mirror_center)
    half_width = 1 / (2 * PROJECTOR_THROW)
    half_height = half_width / PROJECTOR_ASPECT
    pitch = radians(args.pitch_deg)
    sin_pitch, cos_pitch = sin(pitch), cos(pitch)
    horizontal_sign = 1 if args.flip_raster_x else -1
    rows = []
    for row in range(height):
        raster_y = 2 * row / (height - 1) - 1
        # At 100% native offset, the lens axis lines up with the bottom edge of the image.
        y = (raster_y + 1 + 2 * args.lens_shift) * half_height
        vertices = []
        for column in range(width):
            raster_x = 2 * column / (width - 1) - 1
            x = horizontal_sign * raster_x * half_width
            ray = (x, sin_pitch + y * cos_pitch, cos_pitch - y * sin_pitch)
            ray_length = hypot(x, y, 1)
            direction = tuple(component / ray_length for component in ray)
            uv = trace_ray(lens, direction, mirror_center, args.mirror_radius)
            vertices.append((raster_x * PROJECTOR_ASPECT, raster_y, uv))
        rows.append(vertices)

    valid_cells = sum(
        all(rows[y][x][2] is not None for y in (row, row + 1) for x in (column, column + 1))
        for row in range(height - 1)
        for column in range(width - 1)
    )
    if valid_cells == 0:
        raise ValueError("No usable warp cells. Check your lens and mirror positions.")

    with args.output.open("w", encoding="ascii", newline="\n") as stream:
        stream.write(f"2\n{width} {height}\n")
        for vertices in rows:
            for x, y, uv in vertices:
                u, v, gain = (*uv, 1) if uv is not None else (0, 0, -1)
                stream.write(f"{x:.8f} {y:.8f} {u:.8f} {v:.8f} {gain}\n")
    return valid_cells


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=BASELINE_MESH)
    parser.add_argument("--grid", type=int, nargs=2, default=(193, 109), metavar=("WIDTH", "HEIGHT"))
    parser.add_argument("--lens", type=float, nargs=3, default=(0, -0.39, -0.60), metavar=("X", "Y", "Z"))
    parser.add_argument("--mirror-center", type=float, nargs=3, default=(0, -0.46, 0), metavar=("X", "Y", "Z"))
    parser.add_argument("--mirror-radius", type=float, default=0.25, help="Estimated radius of curvature in meters")
    parser.add_argument("--pitch-deg", type=float, default=-4.2, help="Physical projector pitch, positive up")
    parser.add_argument("--lens-shift", type=float, default=0.0, help="Extra upward shift in image heights (0 to 0.16)")
    parser.add_argument("--flip-raster-x", action="store_true", help="Match a horizontally reversed projector raster")
    args = parser.parse_args()
    if min(args.grid) < 2:
        parser.error("The grid must have at least two rows and columns.")
    if not all(isfinite(value) for value in (*args.lens, *args.mirror_center, args.mirror_radius, args.pitch_deg)):
        parser.error("Optical geometry must use finite values.")
    if args.mirror_radius <= 0:
        parser.error("Mirror radius must be positive.")
    if args.lens[2] >= args.mirror_center[2]:
        parser.error("The lens must be on the dome side of the mirror (smaller Z).")
    if hypot(*(a - b for a, b in zip(args.lens, args.mirror_center))) <= args.mirror_radius:
        parser.error("The lens must be outside the mirror sphere.")
    if not 0 <= args.lens_shift <= 0.16:
        parser.error("Lens shift must be between 0 and 0.16 image heights.")
    try:
        valid_cells = write_warp(args)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Wrote {args.output} with {valid_cells:,} usable cells before dome masking.")


if __name__ == "__main__":
    main()
