#!/usr/bin/env python3
"""Stage 2: decl -> output/<name>/<name>_grid.json (with R1-R4 validation)."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pipeline.decl import read_decl
from pipeline.grid import parse_map
from pipeline.validate import validate_map


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage 2: grid + validate")
    ap.add_argument("name")
    args = ap.parse_args()

    out_dir = Path("output") / args.name
    decl = read_decl(out_dir / f"{args.name}_decl.json")

    if decl.get("kind", "single") == "single":
        grid = parse_map(decl["map"])
        errors = validate_map(grid)
        result = {
            "name": decl["name"],
            "kind": "single",
            "rows": len(grid),
            "cols": max((len(r) for r in grid), default=0),
            "grid": [[{"char": ch} for ch in row] for row in grid],
            "validation": {"ok": not errors, "rule_violations": errors},
        }
    else:  # world
        scenes = []
        all_ok = True
        for sc in decl["scenes"]:
            grid = parse_map(sc["map"])
            errors = validate_map(grid)
            scenes.append({
                "id": sc["id"],
                "grid": [[{"char": ch} for ch in row] for row in grid],
                "validation": {"ok": not errors, "rule_violations": errors},
            })
            all_ok = all_ok and not errors
        result = {
            "name": decl["name"],
            "kind": "world",
            "scenes": scenes,
            "validation": {"ok": all_ok},
        }

    out_path = out_dir / f"{args.name}_grid.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    if not result["validation"]["ok"]:
        n = sum(len(s.get("validation", {}).get("rule_violations", []))
                for s in result.get("scenes", [result]))
        print(f"⚠️  {n} R1-R4 violation(s) written to grid.json (non-blocking)")
    print(f"✅ stage2 → {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
