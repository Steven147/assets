"""Build desc -> tile file path mapping from kenney_pixel-shmup/Tiles/."""
import json
from pathlib import Path
from typing import Dict

GAME_DIR = Path(__file__).resolve().parent.parent.parent

# Hand-curated mapping of desc string -> tile file.
# All entries verified to exist in kenney_pixel-shmup/Tiles/. Source mapping
# taken from output/shanghai_150km/shanghai_150km_registry.json (62 unique
# descs covering G/O/S chars, road variants, and beach variants).
DESC_TO_TILE: Dict[str, str] = {
    "G-full-land": "tile_0050.png",
    "G-o-bottom-road": "tile_0100.png",
    "G-o-full-road": "tile_0086.png",
    "G-o-left-bottom-road": "tile_0075.png",
    "G-o-left-right-bottom-road": "tile_0088.png",
    "G-o-left-right-road": "tile_0074.png",
    "G-o-left-right-top-road": "tile_0089.png",
    "G-o-left-road": "tile_0113.png",
    "G-o-left-top-bottom-road": "tile_0077.png",
    "G-o-left-top-road": "tile_0099.png",
    "G-o-right-bottom-road": "tile_0073.png",
    "G-o-right-road": "tile_0101.png",
    "G-o-right-top-bottom-road": "tile_0076.png",
    "G-o-right-top-road": "tile_0097.png",
    "G-o-top-bottom-road": "tile_0085.png",
    "G-o-top-road": "tile_0112.png",
    "O-full-land": "tile_0056.png",
    "W-full-sea": "tile_0042.png",
    "W-y-g-bottom-beach": "tile_0062.png",
    "W-y-g-island": "tile_0064.png",
    "W-y-g-island-2": "tile_0065.png",
    "W-y-g-left-beach": "tile_0049.png",
    "W-y-g-left-bottom-beach": "tile_0061.png",
    "W-y-g-left-bottom-negative-beach": "tile_0041.png",
    "W-y-g-left-top-beach": "tile_0037.png",
    "W-y-g-left-top-negative-beach": "tile_0053.png",
    "W-y-g-right-beach": "tile_0051.png",
    "W-y-g-right-bottom-beach": "tile_0063.png",
    "W-y-g-right-bottom-negative-beach": "tile_0040.png",
    "W-y-g-right-top-beach": "tile_0039.png",
    "W-y-g-right-top-negative-beach": "tile_0052.png",
    "W-y-g-top-beach": "tile_0038.png",
    "W-y-o-bottom-beach": "tile_0068.png",
    "W-y-o-island": "tile_0070.png",
    "W-y-o-island-2": "tile_0071.png",
    "W-y-o-left-beach": "tile_0055.png",
    "W-y-o-left-bottom-beach": "tile_0067.png",
    "W-y-o-left-bottom-negative-beach": "tile_0047.png",
    "W-y-o-left-top-beach": "tile_0043.png",
    "W-y-o-left-top-negative-beach": "tile_0059.png",
    "W-y-o-right-beach": "tile_0057.png",
    "W-y-o-right-bottom-beach": "tile_0069.png",
    "W-y-o-right-bottom-negative-beach": "tile_0046.png",
    "W-y-o-right-top-beach": "tile_0045.png",
    "W-y-o-right-top-negative-beach": "tile_0058.png",
    "W-y-o-top-beach": "tile_0044.png",
    "location": "tile_0003.png",
    "o-w-bottom-road": "tile_0106.png",
    "o-w-full-road": "tile_0092.png",
    "o-w-left-bottom-road": "tile_0081.png",
    "o-w-left-right-bottom-road": "tile_0094.png",
    "o-w-left-right-road": "tile_0080.png",
    "o-w-left-right-top-road": "tile_0095.png",
    "o-w-left-road": "tile_0119.png",
    "o-w-left-top-bottom-road": "tile_0083.png",
    "o-w-left-top-road": "tile_0105.png",
    "o-w-right-bottom-road": "tile_0079.png",
    "o-w-right-road": "tile_0107.png",
    "o-w-right-top-bottom-road": "tile_0082.png",
    "o-w-right-top-road": "tile_0103.png",
    "o-w-top-bottom-road": "tile_0091.png",
    "o-w-top-road": "tile_0118.png",
}


def generate_tile_paths() -> Dict[str, str]:
    """Return desc -> absolute URL path (e.g. /kenney_pixel-shmup/Tiles/...).

    The editor HTML is served from /pipeline/editor/editor.html, so a relative
    path would resolve under /pipeline/editor/ and 404. Absolute paths resolve
    from the server root (which is the game dir) and hit the right files.
    """
    return {
        desc: f"/kenney_pixel-shmup/Tiles/{filename}"
        for desc, filename in DESC_TO_TILE.items()
    }


def write_tile_paths_js(out_path: Path) -> None:
    """Write tile_paths.js for the browser to load."""
    paths = generate_tile_paths()
    out_path.write_text(
        f"window.TILE_PATHS = {json.dumps(paths, indent=2)};\n",
        encoding="utf-8",
    )
