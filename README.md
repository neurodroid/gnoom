# Gnoom

Gnoom is a collection of GNU/Linux tools for rodent virtual reality research. The current linear-track demo runs in **Godot 4** and uses the bundled Godot360 code for spherical dome projection. The track has patterned walls, colored landmarks, and keyboard or Arduino rotary encoder control. [Godot project](godot4/project.godot) · [Dome and encoder setup](godot4/README.md)

## Install on Ubuntu 26.04 LTS

Install mise from its maintainer’s Ubuntu PPA. The demo uses XWayland on GNOME to detect when you move the game window to the projector. [mise installation instructions](https://mise.jdx.dev/installing-mise.html#apt)

```sh
sudo apt update
sudo apt install software-properties-common xwayland
sudo add-apt-repository ppa:jdxcode/mise
sudo apt update
sudo apt install mise
```

Install the Godot release used to test this demo. These commands use mise directly and work without shell activation. [mise exec documentation](https://mise.jdx.dev/cli/exec.html)

```sh
mise install godot@4.7.2-stable
mise exec godot@4.7.2-stable -- godot --version
```

## Run the demo

From the repository root, launch the Godot editor with the demo project.

```sh
mise exec godot@4.7.2-stable -- godot --editor --path godot4
```

Let the editor finish importing the assets, then press **F5** to run the dome demo with the Optoma and Seton starting warp. For projector use, turn off **Embed Game on Next Play** in the **Game** toolbar menu before pressing **F5**. The standalone game renders at 1920 × 1080 and switches to fullscreen when moved onto a 1080p display. [Godot game embedding](https://docs.godotengine.org/en/4.7/tutorials/editor/game_embedding.html) · [Projector output](godot4/README.md#projector-output)

To launch from the terminal, run the import command once on a fresh checkout, then start the game.

```sh
mise exec godot@4.7.2-stable -- godot --headless --path godot4 --import
mise exec godot@4.7.2-stable -- godot --path godot4
```

Use **↑** and **↓** to test movement without connecting an Arduino. For the unwarped preview, open `godot4/dome/linear_track_dome.tscn` and press **F6**. [Optoma and Seton starting calibration](godot4/README.md#optoma-and-seton-starting-calibration) · [Legacy projection](godot4/README.md#legacy-front-truncated-projection)

## Blender Game Engine and research background

The original implementation used the Blender Game Engine for dome projection and included a game controlled by two optical mice. The original scene, hardware utilities, and documentation are available for reference. [Blender scene](gnoom-simple.blend) · [Archived GettingStarted](https://code.google.com/archive/p/gnoom/wikis/GettingStarted.wiki) · [Archived DomeProjection](https://code.google.com/archive/p/gnoom/wikis/DomeProjection.wiki)

Dalai Felinto integrated the dome projection mode into Blender. The original Gnoom design was used in rodent virtual reality studies and adapted commercially by PhenoSys. [Paul Bourke’s dome projection notes](https://paulbourke.net/dome/) · [PMID 23396102](https://pubmed.ncbi.nlm.nih.gov/23396102/) · [PMID 33068531](https://pubmed.ncbi.nlm.nih.gov/33068531/) · [PhenoSys JetBall](https://www.phenosys.com/brain-research/virtual-reality/jetball/)
