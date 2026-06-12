"""Map editor server: generates meta + tile_paths, serves static, POST /save."""
import argparse
import json
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


def write_meta(meta: dict, out_path: Path) -> None:
    """Write meta.json to out_path."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def write_tile_paths_to(out_path: Path) -> None:
    """Write tile_paths.js for the browser."""
    from pipeline.editor.tile_paths_gen import write_tile_paths_js
    write_tile_paths_js(out_path)


def save_decl_from_request(decl: dict) -> Path:
    """Validate decl shape and write to input/<name>_decl.json. Returns path."""
    name = decl.get("name", "").strip()
    if not name:
        raise ValueError("missing name")
    rows = decl["rows"]
    cols = decl["cols"]
    map_lines = decl["map"]
    if len(map_lines) != rows:
        raise ValueError(f"map has {len(map_lines)} rows, expected {rows} (shape mismatch)")
    for i, line in enumerate(map_lines):
        if len(line) != cols:
            raise ValueError(f"row {i} has {len(line)} cols, expected {cols} (shape mismatch)")
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = INPUT_DIR / f"{name}_decl.json"
    out.write_text(json.dumps(decl, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
