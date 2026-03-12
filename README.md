# Fusion3DMap

This repository contains a set of Python scripts that build a 3D map animation using GPX data and tile sources (satellite imagery and elevation data).

## Overview

- **main.py** is the entry point. It sets up directories, configures map parameters, and invokes the `MapBuilder` class to:
  1. collect geometry data from GPX files
  2. calculate and download image/elevation tiles
  3. assemble the tiles into a DaVinci Resolve Fusion composition
  4. add route geometry, markers and camera animation
  5. render the final result in Resolve

- **utils.py** contains helper functions, tile and map builder classes that handle most of the processing.
- **geometry.py** defines GPX handling and route processing.
- **slippytiles.py** holds tile source definitions and utilities for working with slippy map tiles.
- **resolve.py** provides wrappers around the DaVinci Resolve Fusion scripting API for building the Fusion composition.

## Requirements

Install Python dependencies with:

```bash
pip install -r requirements.txt
```

You must also have DaVinci Resolve installed; the script uses the `DaVinciResolveScript` module which is provided by Resolve and is not available via pip.

## Configuration

1. **Directories**: The script will create `gpx/`, `images/`, and `images/download/` in the project root.
2. **.env**: Create a `.env` file containing API keys for tile providers, e.g.
   ```ini
   MAPTILER_API_KEY="<your key>"
   ```
3. **main.py settings**: Adjust zoom level, elevation range and other parameters when instantiating `MapBuilder`.

## Usage

1. Place your GPX file(s) inside the `gpx/` directory.
2. Modify `main.py` if you need different map options or additional file sources.
3. Run:
   ```bash
   python main.py
   ```
4. The process will generate tiles, assemble the Fusion map, and open/operate on a Resolve instance if available.

## Notes

- Tile downloads respect the configured max zoom levels and API keys.
- If you want to change image or elevation providers, update `TileSources` in `slippytiles.py` or modify the selection in `main.py`.
- Camera animation, markers, and geometry settings can be customized through the Fusion component templates stored in `components/`.

---

Feel free to fork and adapt the code for your own mapping or video production workflows.