#!/usr/bin/env python3
"""Stage 1: source -> output/<name>/<name>_decl.json

Usage:
  python3 stage1_source.py local <name>
  python3 stage1_source.py osm --city shanghai --size-km 10 [--name <output_dir>]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pipeline.sources import get_source


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage 1: source")
    sub = ap.add_subparsers(dest="source", required=True)

    p_local = sub.add_parser("local")
    p_local.add_argument("name")

    p_osm = sub.add_parser("osm")
    p_osm.add_argument("--city", required=True,
                       choices=["shanghai", "beijing", "tokyo", "paris",
                                "london", "newyork", "hangzhou", "shenzhen",
                                "guangzhou", "xiamen", "xian", "bangkok",
                                "weifang", "syracuse"])
    p_osm.add_argument("--size-km", type=float, default=10.0)
    p_osm.add_argument("--name", default=None,
                       help="output dir name (default: <city>_<size_km>km)")

    args = ap.parse_args()

    if args.source == "local":
        out = get_source("local").run(name=args.name)
    else:  # osm
        out = get_source("osm").run(city=args.city, size_km=args.size_km, name=args.name)
    print(f"✅ stage1 → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
