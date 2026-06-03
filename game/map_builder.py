#!/usr/bin/env python3
"""
地图构建器 v2

简单 JSON 地图声明 → 自动推导沙滩/道路方向 → 带 desc 的资源 JSON → HTML 渲染

地图声明格式 (JSON):
  {
    "map": [
      "SSSSSSSS",
      "SGGGGGSS",
      "SGRGGGSS",
      ...
    ]
  }
  S = 海  G = 绿地  O = 红地(橙地)  R = 绿路  r = 红路(橙路)

自动推导规则:
  - 陆地邻居有海 → 自动替换为对应方向的沙滩 tile
  - 道路 → 根据邻居自动选择方向和连接数
  - Negative beach 自动检测（陆地包裹海的内角）

输出: 带描述的 JSON，每个格子包含 { char, desc, file }
"""

import json
from pathlib import Path


# ============================================================
# 1. 解析 assets_map_check.json → tile 注册表
# ============================================================


def parse_tile_registry(json_path: str) -> dict:
    """返回 { description: file_path }"""
    with open(json_path, "r") as f:
        data = json.load(f)
    registry = {}
    for item in data:
        desc = item.get("description", "").strip()
        if not desc:
            continue
        registry[desc] = item["file"]
    return registry


# ============================================================
# 2. 地图声明解析 + 邻居分析
# ============================================================

VALID_CHARS = {"S", "G", "O", "R", "r"}


def parse_map(map_lines: list[str]) -> list[list[str]]:
    """文本行 → 二维字符网格"""
    grid = []
    for line in map_lines:
        row = [ch for ch in line if ch in VALID_CHARS]
        if row:
            grid.append(row)
    return grid


def get_char(grid, r, c) -> str:
    """安全取字符，越界返回 S"""
    if r < 0 or r >= len(grid) or c < 0 or c >= len(grid[r]):
        return "S"
    return grid[r][c]


# ============================================================
# 3. 核心：从格子 + 邻居 → tile desc
# ============================================================

LAND_CHARS = {"G", "O", "R", "r"}


def is_land(ch):
    return ch in LAND_CHARS


def is_sea(ch):
    return ch == "S"


def resolve_tile(grid, r, c) -> str:
    ch = grid[r][c]

    if ch == "S":
        return "W-full-sea"

    if ch == "R":
        return _road(grid, r, c, "G", "o")
    if ch == "r":
        return _road(grid, r, c, "o", "w")

    if ch == "G":
        return _beach(grid, r, c, "W-y-g", "G-full-land")
    if ch == "O":
        return _beach(grid, r, c, "W-y-o", "O-full-land")

    return "W-full-sea"


def _beach(grid, r, c, prefix, full):
    n_top = get_char(grid, r - 1, c)
    n_bot = get_char(grid, r + 1, c)
    n_lft = get_char(grid, r, c - 1)
    n_rgt = get_char(grid, r, c + 1)

    sea = set()
    if is_sea(n_top):
        sea.add("top")
    if is_sea(n_bot):
        sea.add("bottom")
    if is_sea(n_lft):
        sea.add("left")
    if is_sea(n_rgt):
        sea.add("right")

    if not sea:
        return full
    if len(sea) >= 3:
        return f"{prefix}-island" if len(sea) == 3 else f"{prefix}-island-2"
    if len(sea) == 2:
        d = sorted(sea)
        # 对向
        if d == ["bottom", "top"]:
            return f"{prefix}-top-beach"
        if d == ["left", "right"]:
            return f"{prefix}-left-beach"
        # L 角
        name = "-".join(d)  # e.g. "left-top"
        neg = _is_negative(grid, r, c, d[0], d[1])
        return f"{prefix}-{name}-negative-beach" if neg else f"{prefix}-{name}-beach"
    if len(sea) == 1:
        d = sea.pop()
        return f"{prefix}-{d}-beach"
    return full


def _is_negative(grid, r, c, d1, d2):
    """两方向都临海时，检查对角是否也是陆地 → negative"""
    DR = {"top": -1, "bottom": 1, "left": 0, "right": 0}
    DC = {"top": 0, "bottom": 0, "left": -1, "right": 1}
    diag = get_char(grid, r + DR[d1] + DR[d2], c + DC[d1] + DC[d2])
    return is_land(diag)


def _road(grid, r, c, base, road):
    n_top = get_char(grid, r - 1, c)
    n_bot = get_char(grid, r + 1, c)
    n_lft = get_char(grid, r, c - 1)
    n_rgt = get_char(grid, r, c + 1)

    conn = set()
    for d, nb in [("top", n_top), ("bottom", n_bot), ("left", n_lft), ("right", n_rgt)]:
        if is_land(nb) or nb in ("R", "r"):
            conn.add(d)

    def tile(s):
        return f"{base}-{road}-{s}-road"

    if len(conn) == 4:
        return tile("full")
    if len(conn) == 3:
        miss = ({"top", "bottom", "left", "right"} - conn).pop()
        map3 = {
            "top": "left-right-bottom",
            "bottom": "left-right-top",
            "left": "right-top-bottom",
            "right": "left-top-bottom",
        }
        return tile(map3[miss])
    if len(conn) == 2:
        pair = frozenset(conn)
        map2 = {
            frozenset(["left", "right"]): "left-right",
            frozenset(["top", "bottom"]): "top-bottom",
            frozenset(["left", "top"]): "left-top",
            frozenset(["right", "top"]): "right-top",
            frozenset(["left", "bottom"]): "left-bottom",
            frozenset(["right", "bottom"]): "right-bottom",
        }
        return tile(map2[pair])
    if len(conn) == 1:
        return tile(conn.pop())
    return tile("full")


# ============================================================
# 4. 生成带 desc 的 JSON
# ============================================================


def generate_desc_json(grid, registry) -> list[list[dict]]:
    """输出二维数组，每格 { char, desc, file }"""
    result = []
    for r, row in enumerate(grid):
        line = []
        for c in range(len(row)):
            desc = resolve_tile(grid, r, c)
            line.append(
                {
                    "char": grid[r][c],
                    "desc": desc,
                    "file": registry.get(desc, ""),
                }
            )
        result.append(line)
    return result


# ============================================================
# 5. 生成 HTML
# ============================================================

COLORS = {
    "S": "#1a5276",
    "G": "#27ae60",
    "O": "#e67e22",
    "R": "#2ecc71",
    "r": "#f39c12",
}


def generate_html(grid, registry, output_path):
    rows = len(grid)
    cols = max(len(r) for r in grid) if grid else 0

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tile Map Viewer</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#1a1a2e;color:#eee;font-family:'Courier New',monospace;
  display:flex;flex-direction:column;align-items:center;min-height:100vh;padding:20px}}
h2{{margin-bottom:16px}}
.map{{display:grid;grid-template-columns:repeat({cols},64px);gap:2px;
  padding:20px;background:#16213e;border-radius:12px;
  box-shadow:0 8px 32px rgba(0,0,0,.3)}}
.tile{{width:64px;height:64px;position:relative;border-radius:4px;overflow:hidden}}
.tile img{{width:100%;height:100%;object-fit:cover;image-rendering:pixelated}}
.tile .tag{{position:absolute;bottom:2px;right:2px;font-size:8px;color:#fff;
  background:rgba(0,0,0,.7);padding:1px 3px;border-radius:2px;pointer-events:none}}
.legend{{margin-top:20px;padding:16px;background:#0f3460;border-radius:8px;max-width:800px}}
.legend h3{{margin-bottom:8px}}
.li{{display:inline-block;margin:4px 8px;font-size:13px}}
.lc{{display:inline-block;width:16px;height:16px;border-radius:3px;vertical-align:middle;margin-right:4px}}
</style></head><body>
<h2>🗺️ Tile Map Viewer</h2>
<div class="map">
"""
    for r, row in enumerate(grid):
        for c in range(len(row)):
            desc = resolve_tile(grid, r, c)
            fp = registry.get(desc, "")
            ch = grid[r][c]
            bg = COLORS.get(ch, "#333")
            if fp:
                html += f'<div class="tile" title="{desc}"><img src="{fp}"><span class="tag">{ch}</span></div>\n'
            else:
                html += f'<div class="tile" style="background:{bg}" title="{desc}"><span class="tag">{ch}</span></div>\n'

    html += """</div>
<div class="legend"><h3>图例</h3>
"""
    for ch, label, color in [
        ("S", "海", "#1a5276"),
        ("G", "绿地", "#27ae60"),
        ("O", "红地", "#e67e22"),
        ("R", "绿路", "#2ecc71"),
        ("r", "红路", "#f39c12"),
    ]:
        html += f'<div class="li"><span class="lc" style="background:{color}"></span>{ch}={label}</div>\n'

    html += "</div></body></html>"

    with open(output_path, "w") as f:
        f.write(html)


# ============================================================
# 6. 主程序
# ============================================================


def main():
    base = Path(__file__).parent
    registry = parse_tile_registry(str(base / "assets_map_check.json"))

    # ---- 简单 JSON 地图声明 ----
    map_decl = {
        "name": "example_island",
        "map": [
            "SSSSSSSSSS",
            "SGSSGGGGSS",
            "SGGSGGGGSS",
            "SSSGGOGGOS",
            "SSSGOORrOS",
            "SSSGGOGGOS",
            "SSSGGOGGOS",
            "SSSOGGOGSS",
            "SSSGGGGGSS",
            "SSSSSSSSSS",
        ],
    }

    map_path = base / "map_decl.json"
    with open(map_path, "w") as f:
        json.dump(map_decl, f, indent=2, ensure_ascii=False)

    # 解析
    grid = parse_map(map_decl["map"])

    # 生成带 desc 的 JSON
    desc_json = generate_desc_json(grid, registry)
    desc_path = base / "map_resolved.json"
    with open(desc_path, "w") as f:
        json.dump(desc_json, f, indent=2, ensure_ascii=False)

    # 生成 HTML
    html_path = base / "map_viewer.html"
    generate_html(grid, registry, str(html_path))

    # 打印摘要
    print(f"地图声明: {map_path}")
    print(f"资源 JSON: {desc_path}")
    print(f"HTML 查看器: {html_path}")
    print()

    # 统计
    from collections import Counter

    descs = [cell["desc"] for row in desc_json for cell in row]
    print("Tile 使用统计:")
    for desc, cnt in Counter(descs).most_common():
        print(f"  {desc}: {cnt}")

    # 打印声明示例
    print("\n--- 地图声明 JSON ---")
    print(json.dumps(map_decl, indent=2, ensure_ascii=False))

    print("\n--- 资源 JSON (前 3 行) ---")
    for row in desc_json[:3]:
        print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main()
