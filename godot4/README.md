# Godot linear track dome demo

Follow the [Ubuntu 26.04 installation and launch steps](../README.md#install-on-ubuntu-2604-lts) to open the project in Godot 4.7.2. Press **F5** to run the dome scene with the Optoma and Seton starting warp. With the game focused, hold **↑** to move forward or **↓** to move backward. Reaching `TrackEnd` returns the camera to `TrackStart`. Reverse travel stops at `TrackStart`.

## Arduino rotary encoder

1. Open [`arduino/rotary/rotary.ino`](../arduino/rotary/rotary.ino) in the Arduino IDE and upload the sketch. Keep `rotary_only.ino` in the same folder as the main sketch. The firmware reads channel A on D2 and channel B on D7.
2. In `dome/linear_track_dome_calibration.tscn`, select `LinearTrackDomeCalibration` and set **Serial Port** to the Arduino’s device path. On Linux this might be `/dev/ttyACM0`, `/dev/ttyUSB0`, or a stable link under `/dev/serial/by-id/`.
3. Run with **F5**. Godot retries the selected port every second while it is unavailable. The Godot console reports the connection state. Clear **Serial Port** for a keyboard-only run.

After the first editor import, you can also launch from the repository root and select the port for that run with `GNOOM_SERIAL_PORT`.

```sh
GNOOM_SERIAL_PORT=/dev/ttyACM0 mise exec godot@4.7.2-stable -- godot --path godot4
```

The sketch sends a raw byte at 115200 baud on each change of channel A. By default `0x01` advances the camera and `0x00` moves it backward. Turn on **Invert Encoder** if movement is reversed. **Meters Per Step** starts at `0.0001` for the demo. For physical calibration, divide the wheel circumference in meters by the number of emitted steps per wheel revolution, then multiply by the desired virtual travel gain.

If Ubuntu reports **Permission denied** and the serial device belongs to the `dialout` group, run `sudo usermod -aG dialout "$USER"`, then sign out and back in before restarting Godot. [Arduino serial port permissions](https://support.arduino.cc/hc/en-us/articles/360016495679-Fix-port-access-on-Linux)

The project uses GdSerial when its `GdSerialManager` class is available. Install the addon in `godot4/addons/gdserial` to use it. The bundled Linux reader uses `/usr/bin/python3` and the standard library. The process running Godot needs read access to the chosen serial device. [GdSerial installation](https://github.com/SujithChristopher/gdserial#installation)

## Projector output

The [dome projection references](../docs/dome/README.md) include the dimensioned sketch, optical drawing, earlier settings, and hardware specifications.

The dome renderer uses Godot360’s six capture cameras at the moving eye position and a level **250° equidistant fisheye** with the opening and floor of the cut sphere masked out. The modeled sphere has a radius of **0.60 m**. The vertical opening behind the eye and the horizontal floor below it are each about **0.344 m** from the sphere center. At center height the screen spans **±125°** from straight ahead.

The standalone window opens with a **1920 × 1080** game area and keeps that render resolution as the window size changes. The unwarped preview is centered in a square. A loaded warp is fitted to the game area using its **Projector Aspect**.

Press **F5** with **Embed Game on Next Play** off in the **Game** toolbar menu. Drag the standalone window by its title bar to the projector and release it there. The dome scene switches to fullscreen after the window settles on another display at **1920 × 1080**. The project uses the X11 display driver on Linux so it can detect the move. In a GNOME Wayland session, it reads the active display modes through `busctl` to account for XWayland scaling. [Godot game embedding](https://docs.godotengine.org/en/4.7/tutorials/editor/game_embedding.html)

To launch directly in fullscreen, use `--fullscreen --screen N` with the projector’s display index. Open `dome/linear_track_dome.tscn` and press **F6** for the unwarped preview, or open `assets/linear_track_demo.tscn` and press **F6** for the normal monitor view.

### Check alignment with angular targets

Press **F5**, then press **C** with the game focused to toggle the calibration pattern through the same warp as the track. White crosses mark 10° azimuth and elevation intervals. Blue marks zero azimuth, and the horizon is red on the left and green on the right. The gold target starts straight ahead at 0° azimuth and 0° elevation. [Paul Bourke’s polar grid alignment guide](https://paulbourke.net/dome/faq/)

Use **A/D** to move the target left or right in azimuth and **W/S** to raise or lower it in elevation. Each step is 5°. Hold **Shift** for 1° steps or press **R** to reset the target. The Godot console prints the selected azimuth and elevation.

Check the projected marks from the player’s eye position against known directions near the center, horizon, side rims, upper opening, and floor. To collect correspondences for fitting a new warp, project markers at known raster positions and measure where they land. [Bourke’s camera calibration method](https://paulbourke.net/dome/cameracalibration/index.html)

### Calibrate the cut sphere

Select `DemoCamera/DomeCamera` in `dome/linear_track_dome_calibration.tscn`. Keep **Cut Sphere** enabled, **Front Truncated** off, and **Fovx** at 250°. Set **Warp Mesh Path** to a matching type-2 warp, set **Projector Aspect** to the aspect used to generate it, and enable **Use Warp Mesh**. Use **Mirror Horizontal** if your optical path needs a lateral flip.

The warp maps projector pixels to a full circular, level 250° fisheye centered on the sphere. For a dome point hit by the projected ray, let `d` be the unit vector from the sphere center to that point, with +X right, +Y up, and −Z into the dome. Its off-axis angle is `theta = acos(-d.z)`. In the fisheye disk, `(x, y) = normalize(d.xy) * theta / radians(125)`, with `(0, 0)` on the forward axis. Write source coordinates `u = (1 + x) / 2` and `v = (1 + y) / 2`, with `v` increasing upward. [Meshmapper calibration method](https://paulbourke.org/dome/meshmapper/)

A type-2 file starts with `2` on its first line and the grid width and height on the second. Each remaining line stores one grid vertex as `projector_x projector_y u v gain`. List each row from left to right, starting with the bottom row. Projector X spans ±**Projector Aspect**, with positive values to the right. Projector Y spans ±1, with positive values up. Use gain `1` for the original brightness. A negative vertex gain excludes its adjoining grid cells.

Set **Eye Offset M** to the player’s eye position relative to the sphere center in meters, using the same axes. The renderer uses this offset when looking up the scene for each surface point, so the warp stays tied to the sphere center.

### Optoma and Seton starting calibration

The project starts in `dome/linear_track_dome_calibration.tscn` with the estimated 16:9 warp. Use the projector's full 1920 × 1080 raster with digital keystone and four-corner correction off. Set the optical zoom to the widest **1.0×** end, which corresponds to a **1.40:1** throw ratio. The model assumes upright mounting and minimum vertical lens shift, where the lens axis lines up with the bottom of the image. [Optoma ZH507+ specifications](https://www.optomausa.com/product/zh507plus) · [Optoma manual, pp. 17 and 73](https://device.report/m/c0777380c2348f5beb1376af476593bf030a81c9a1ca1ba9a9be9cbbc6d897be_optim.pdf)

The starting geometry uses the screen's sphere center as the origin, with +X right, +Y up, and −Z into the dome. The projector model assumes zero yaw and roll.

| Parameter | Starting value |
| --- | --- |
| Projector lens center | `(0, −0.390, −0.600) m`, from the legacy distances |
| Projector pitch | **4.2° down** toward the mirror, estimated by ray tracing |
| Mirror center of curvature | `(0, −0.460, 0) m`, from the legacy distances |
| Mirror surface | Seton JB DDOME4 (500 mm model, 510 × 245 mm exterior). The model assumes a **250 mm radius of curvature** and a reflecting quarter sphere facing up and into the dome. [Seton technical sheet](../docs/dome/DMEU_TDS_Y4261312_FR_std.lang.all.pdf) |

The nominal mount reaches about **92% of the modeled screen area**, with gaps where the lower side rims fall outside the projector raster. The model accounts for blockage by the curved screen and assumes clearance around the floor cut and other hardware. Check focus on the dome. Optoma's manual gives a 1.2 m minimum straight-path focus distance, and the convex mirror changes the beam's focus.

Regenerate the warp after measuring the lens and mirror positions or adjusting the physical pitch. Run `python3 godot4/dome/generate_optoma_warp.py --help` from the repository root for the adjustable parameters. Use `--output` when saving a trial warp and set **Warp Mesh Path** in the calibration scene to load it.

If the mount allows a placement trial, the generated warp covers about **99.4%** of the modeled screen with the lens 240 mm farther from the mirror and 50 mm lower, at `(0, −0.440, −0.840) m`, pitched **0.4° down**. Generate that trial with `--lens 0 -0.44 -0.84 --pitch-deg -0.4`. Check beam clearance and focus on the hardware before using the trial position.

### Legacy Front-Truncated projection

Open `dome/linear_track_dome_legacy.tscn` and press **F6**, or pass `res://dome/linear_track_dome_legacy.tscn` to Godot after `--path godot4`. This scene uses the Blender Game Engine’s **Front-Truncated** 250° fisheye and `blender/warp/meshwarp.data`. Keep `godot4` inside the repository so Godot can find the file. The legacy camera starts pitched **15° down**, and its 16:10 warp covers a centered **1728 × 1080** area at native resolution. [Blender dome renderer](https://github.com/blender/blender/blob/v2.79b/source/gameengine/Ketsji/KX_Dome.cpp#L1667-L1715)

### Legacy calibration transcribed from the screenshots

| Item | Recorded values |
| --- | --- |
| Blender Game Engine | Front-Truncated, angle 250°, tilt 0°, resolution factor 1.00, tessellation 4, `meshwarp.data` |
| Meshmapper grid | Ratio 1.00, width 142, height 80 |
| Meshmapper projector | Aspect 1.60, throw 1.20, tilt 0.15, offset 0.00, position `(0.60, 0.00, 0.07)` |
| Meshmapper mirror | Radius and depth 0.22, position `(0.00, 0.00, 0.00)` |
| Meshmapper dome | Radius 0.60, angle 180°, position `(0.00, 0.00, 0.46)` |

The Meshmapper values come from the [warp mesh settings screenshot](../docs/dome/Screenshot-meshdata.png). Its projector tilt field leaves the units unspecified. Godot reads the resulting warp table directly. It captures each cube face at 800 × 800 as the starting rendering resolution.

The vendored Godot360 runtime comes from the upstream `master` source under the included MIT license. The camera script omits the optional editor icon annotation. [Godot360 source](https://github.com/Cykyrios/Godot360/tree/master/addons/godot360)
