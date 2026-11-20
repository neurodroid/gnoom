# Godot linear track dome demo

Follow the [Ubuntu 26.04 installation and launch steps](../README.md#install-on-ubuntu-2604-lts) to open the project in Godot 4.7.2. Press **F5** to run the dome scene. With the game focused, hold **↑** to move forward or **↓** to move backward. Reaching `TrackEnd` returns the camera to `TrackStart`. Reverse travel stops at `TrackStart`.

## Arduino rotary encoder

1. Open [`arduino/rotary/rotary.ino`](../arduino/rotary/rotary.ino) in the Arduino IDE and upload the sketch. Keep `rotary_only.ino` in the same folder as the main sketch. The firmware reads channel A on D2 and channel B on D7.
2. In `dome/linear_track_dome.tscn`, select `LinearTrackDome` and set **Serial Port** to the Arduino’s device path. On Linux this might be `/dev/ttyACM0`, `/dev/ttyUSB0`, or a stable link under `/dev/serial/by-id/`.
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

The dome scene uses Godot360’s six capture cameras at the moving eye position. It uses the legacy **250° equidistant fisheye**, **Front-Truncated** crop, and `blender/warp/meshwarp.data` from the Blender Game Engine setup. [Blender dome renderer](https://github.com/blender/blender/blob/v2.79b/source/gameengine/Ketsji/KX_Dome.cpp#L1667-L1715)

The standalone window opens with a **1920 × 1080** game area. The game keeps that render resolution as the window size changes. The 16:10 warp occupies a centered **1728 × 1080** area with 96 black pixels at each side at native resolution. The dome camera starts pitched **15° down**. Adjust **Transform → Rotation → X** on `DemoCamera/DomeCamera` to aim it. Negative X angles pitch the view downward.

Press **F5** with **Embed Game on Next Play** off in the **Game** toolbar menu. Drag the standalone window by its title bar to the projector and release it there. The dome scene switches to fullscreen after the window settles on another display at **1920 × 1080**. The project uses the X11 display driver on Linux so it can detect the move. In a GNOME Wayland session, it reads the active display modes through `busctl` to account for XWayland scaling. [Godot game embedding](https://docs.godotengine.org/en/4.7/tutorials/editor/game_embedding.html)

To launch directly in fullscreen, use `--fullscreen --screen N` with the projector’s display index. Keep the Godot project in the repository, where it can find the legacy warp file. To use another type-2 mesh, set **Warp Mesh Path** and **Projector Aspect** on `DemoCamera/DomeCamera`.

Clear **Use Warp Mesh** on `DomeCamera` to view the unwarped front-truncated projection. Clear **Front Truncated** as well for the full circular fisheye. Use **Mirror Horizontal** if your optical path needs a lateral flip. The normal monitor view is available by opening `assets/linear_track_demo.tscn` and pressing **F6**.

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
