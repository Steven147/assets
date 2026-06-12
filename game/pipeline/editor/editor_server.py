"""Map editor server: generates meta + tile_paths, serves static, POST /save."""
import argparse
import http.server
import json
import os
import socketserver
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Optional

# Ensure project root is on sys.path so this script works when run directly
# (e.g. `python3 pipeline/editor/editor_server.py ...`).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from pipeline.editor.city_presets import get_preset  # noqa: E402

GAME_DIR = _PROJECT_ROOT
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


class EditorHandler(http.server.SimpleHTTPRequestHandler):
    """Static file server with a single POST /save endpoint."""

    def do_POST(self) -> None:  # noqa: N802
        if self.path.rstrip("/") != "/save":
            self.send_error(404, "not found")
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            out = save_decl_from_request(payload)
            body = json.dumps({"ok": True, "path": str(out)}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (ValueError, KeyError) as e:
            body = json.dumps({"ok": False, "error": str(e)}).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        sys.stderr.write(f"[editor] {format % args}\n")


def find_free_port() -> int:
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    meta = resolve_meta(args.name, args.city, args.rows, args.cols, args.span_km)
    write_meta(meta, EDITOR_DIR / "meta.json")
    write_tile_paths_to(EDITOR_DIR / "tile_paths.js")
    port = args.port or find_free_port()
    os.chdir(GAME_DIR)
    httpd = socketserver.TCPServer(("127.0.0.1", port), EditorHandler)
    url = f"http://127.0.0.1:{port}/pipeline/editor/editor.html"
    print(f"[editor] serving on {url}")
    print(f"[editor] meta: {meta}")
    if not args.no_open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[editor] shutting down")
        httpd.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
