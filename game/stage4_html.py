#!/usr/bin/env python3
"""Stage 4: resolved + registry -> output/<name>/<name>_viewer.html."""
import argparse
import json
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pipeline.render import generate_map_html, generate_world_html

PORT = 8765


def _ensure_server() -> None:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=0.3)
        return  # already running
    except Exception:
        pass
    subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(0.5)


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage 4: render HTML")
    ap.add_argument("name")
    ap.add_argument("--serve", action="store_true",
                    help="Start http server and open browser")
    args = ap.parse_args()

    out_dir = Path("output") / args.name
    resolved = json.loads(
        (out_dir / f"{args.name}_resolved.json").read_text(encoding="utf-8")
    )
    registry = json.loads(
        (out_dir / f"{args.name}_registry.json").read_text(encoding="utf-8")
    )

    if resolved.get("kind", "single") == "single":
        out_path = out_dir / f"{args.name}_viewer.html"
        generate_map_html(resolved, registry, str(out_path))
    else:
        out_path = out_dir / "world_viewer.html"
        generate_world_html(resolved, registry, str(out_path))

    print(f"✅ stage4 → {out_path}")
    if args.serve:
        _ensure_server()
        url = f"http://127.0.0.1:{PORT}/{out_path}"
        webbrowser.open(url)
        print(f"🌐 opened {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
