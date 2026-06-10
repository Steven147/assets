#!/usr/bin/env python3
"""Stage 3: grid -> output/<name>/<name>_resolved.json + <name>_registry.json."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pipeline.registry import parse_tile_registry
from pipeline.resolve import build_compact_grid
from pipeline.world import resolve_world_scenes


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage 3: resolve tiles")
    ap.add_argument("name")
    args = ap.parse_args()

    base = Path(__file__).parent
    registry = parse_tile_registry(str(base / "assets_map_check.json"))
    out_dir = Path("output") / args.name
    grid_doc = json.loads(
        (out_dir / f"{args.name}_grid.json").read_text(encoding="utf-8")
    )

    if grid_doc.get("kind", "single") == "single":
        char_grid = [[c["char"] for c in row] for row in grid_doc["grid"]]
        code_to_tile, encoded = build_compact_grid(char_grid, registry)
        resolved = {
            "name": grid_doc["name"],
            "kind": "single",
            "rows": grid_doc["rows"],
            "cols": grid_doc["cols"],
            "map": encoded,
        }
        registry_data = code_to_tile
    else:
        resolved, code_to_tile = resolve_world_scenes(grid_doc, registry)
        registry_data = code_to_tile

    # Write resolved.json (compact map) and registry.json (code→desc+file)
    out_path = out_dir / f"{args.name}_resolved.json"
    out_path.write_text(json.dumps(resolved, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    reg_path = out_dir / f"{args.name}_registry.json"
    reg_path.write_text(json.dumps(registry_data, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"✅ stage3 → {out_path}")
    print(f"✅ stage3 → {reg_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
