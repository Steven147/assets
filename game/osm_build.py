#!/usr/bin/env python3
"""
osm_build.py — OSM decl JSON → map_resolved.json + map_viewer.html

把 osm_to_map.py 生成的 decl JSON 喂给 map_builder 管线，
输出到同一个目标文件夹（保持"每步产出一个文件夹"的工作流）。

不修改 map_builder.py — 直接 import 其函数，校验失败时仅警告不阻塞
（OSM 真实数据可能违反 R1-R4 几何约束）。
"""

import json
import os
import sys
from pathlib import Path

GAME_DIR = Path(__file__).parent.resolve()


def main():
    if len(sys.argv) < 2:
        print("usage: osm_build.py <target_dir>")
        sys.exit(1)
    target_dir = Path(sys.argv[1]).resolve()
    if not target_dir.is_dir():
        print(f"❌ 目录不存在: {target_dir}")
        sys.exit(1)

    decl_files = sorted(target_dir.glob("*_decl.json"))
    if not decl_files:
        print(f"❌ {target_dir} 中找不到 *_decl.json")
        sys.exit(1)
    decl_path = decl_files[0]
    print(f"📂 decl: {decl_path.name}")

    decl = json.loads(decl_path.read_text(encoding="utf-8"))

    # import map_builder 内部函数（不修改它）
    sys.path.insert(0, str(GAME_DIR))
    from map_builder import (
        parse_tile_registry, parse_map, validate_map,
        generate_desc_json, generate_html,
    )

    registry = parse_tile_registry(str(GAME_DIR / "assets_map_check.json"))
    grid = parse_map(decl["map"])

    # 校验：警告而非阻塞（OSM 真实数据可能违反 R1-R4）
    errors = validate_map(grid)
    if errors:
        print(f"⚠️  校验 {len(errors)} 条违规 (OSM 真实数据常见, 不阻塞):")
        for e in errors[:6]:
            print(f"   • {e}")
        if len(errors) > 6:
            print(f"   ... 共 {len(errors)} 条")
    else:
        print("✅ 校验通过")

    # 1) map_resolved.json
    desc_json = generate_desc_json(grid, registry)
    resolved_path = target_dir / "map_resolved.json"
    resolved_path.write_text(
        json.dumps(desc_json, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"✅ resolved: {resolved_path.name}")

    # 2) map_viewer.html
    html_path = target_dir / "map_viewer.html"
    generate_html(grid, registry, str(html_path))

    # 修复 viewer 的图片路径（subfolder 内的相对路径）
    rel = os.path.relpath(str(GAME_DIR), str(target_dir))
    text = html_path.read_text(encoding="utf-8")
    text = text.replace(
        'const ABS_PREFIX = "/Users/lsq/env/assets/game/";',
        f'const ABS_PREFIX = "/Users/lsq/env/assets/game/";\n'
        f'const REL_PREFIX = "{rel}";',
    )
    text = text.replace(
        "  if (fp.indexOf(ABS_PREFIX) === 0) return '/' + fp.slice(ABS_PREFIX.length);",
        "  if (fp.indexOf(ABS_PREFIX) === 0) return REL_PREFIX + '/' + fp.slice(ABS_PREFIX.length);",
    )
    html_path.write_text(text, encoding="utf-8")
    print(f"✅ viewer:   {html_path.name}")


if __name__ == "__main__":
    main()
