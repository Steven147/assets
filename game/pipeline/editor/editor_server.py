"""Map editor server: generates meta + tile_paths, serves static, POST /save."""
import argparse
import sys
from pathlib import Path
from typing import Optional

from pipeline.editor.city_presets import get_preset

GAME_DIR = Path(__file__).resolve().parent.parent.parent
EDITOR_DIR = GAME_DIR / "pipeline" / "editor"
INPUT_DIR = GAME_DIR / "input"
DEFAULT_ROWS = 60
DEFAULT_COLS = 80
DEFAULT_SPAN_KM = 10


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="editor_server", description="Map editor server")
    p.add_argument("--name", default="", help="Map name (used for localStorage key + decl filename)")
    p.add_argument("--city", default="", help="City preset name (e.g. shanghai)")
    p.add_argument("--rows", type=int, default=DEFAULT_ROWS, help="Grid rows")
    p.add_argument("--cols", type=int, default=DEFAULT_COLS, help="Grid cols")
    p.add_argument("--span-km", dest="span_km", type=float, default=None, help="Override span_km (default: from city preset)")
    p.add_argument("--port", type=int, default=0, help="Port (0 = pick free port)")
    p.add_argument("--no-open", action="store_true", help="Don't open browser")
    return p.parse_args(argv)


def resolve_meta(name: str, city: str, rows: int, cols: int, span_km: Optional[float] = None) -> dict:
    """Build meta.json content. Falls back to 0,0 if city unknown."""
    if city:
        try:
            preset = get_preset(city)
        except KeyError:
            print(f"warning: unknown city preset '{city}', using 0,0", file=sys.stdout)
            center_lat, center_lng, default_span = 0.0, 0.0, DEFAULT_SPAN_KM
        else:
            center_lat = preset["center_lat"]
            center_lng = preset["center_lng"]
            default_span = preset["span_km"]
    else:
        center_lat, center_lng, default_span = 0.0, 0.0, DEFAULT_SPAN_KM

    return {
        "name": name or "untitled",
        "center_lat": center_lat,
        "center_lng": center_lng,
        "span_km": span_km if span_km is not None else default_span,
        "rows": rows,
        "cols": cols,
    }
