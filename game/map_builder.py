#!/usr/bin/env python3
"""
地图构建器 v3

简单 JSON 地图声明 → 自动推导沙滩/道路方向 → 带 desc 的资源 JSON → HTML 渲染

字符:
  S = 海   G = 绿地   O = 红地(橙地)   R = 绿路   r = 红路(橙路)

九宫格规则 (核心):
  对每个陆地格 (G/O)，看 8 邻居:

  - 4 cardinal (上下左右) 中是海的方向 → 决定 cardinal 沙滩边
      0 个海 cardinal → 检查 4 个对角是否有海 → negative beach
      1 个海 cardinal → {dir}-beach (单边沙滩)
      2 个海 cardinal:
          相邻 (L 形)  → {h}-{v}-beach   外凸沙滩 (左上/右上/左下/右下)
          相对 (薄半岛) → 退化为 single-beach
      3 个海 cardinal → island
      4 个海 cardinal → island-2

  - negative-beach: 仅在 0 个 cardinal 海时检查
      diagonal 左上是海 → left-top-negative-beach (内凹角)
      其他对角同理

道路规则:
  - 道路只连接到其他道路 (R/r), 不连接陆地。
  - 4 邻居中是 R/r 的方向 → 该方向连通

所有规则的关键: 一个格子的 tile = 它本身 + 8 邻居 共同决定。
"""

import json
from collections import Counter
from pathlib import Path


# ============================================================
# 1. 解析 assets_map_check.json → tile 注册表
# ============================================================


class TileRegistry:
    """大小写不敏感的 tile 描述 → 文件路径查找。

    assets_map_check.json 中的描述大小写不一致 (W-y-g- 与 w-y-g- 混用),
    这里统一用 lower() 作 key, 同时保留首次出现的原始大小写以便诊断。
    """

    def __init__(self, items):
        self._lower_to_file = {}
        self._lower_to_orig = {}
        for it in items:
            desc = it.get("description", "").strip()
            if not desc:
                continue
            key = desc.lower()
            if key not in self._lower_to_file:
                self._lower_to_file[key] = it["file"]
                self._lower_to_orig[key] = desc

    def get(self, desc, default=""):
        return self._lower_to_file.get(desc.lower(), default)

    def __contains__(self, desc):
        return desc.lower() in self._lower_to_file


def parse_tile_registry(json_path: str) -> TileRegistry:
    with open(json_path, "r") as f:
        data = json.load(f)
    return TileRegistry(data)


# ============================================================
# 2. 地图声明解析 + 邻居分析
# ============================================================

# L = location marker (city/POI). Renders as "location" tile.
#  - 不参与 R1 (road-sea) 检查 (L 不是 road)
#  - 不参与 R2 (1-wide land peninsula) 检查 (L 不触发 R2)
#  - 参与 R3 (sea strait): L 视作 land, 邻居 S 不会因 L 在两侧而触发
#  - 参与 R4 不适用 (L 不是 road)
VALID_CHARS = {"S", "G", "O", "R", "r", "L"}
LAND_CHARS = {"G", "O", "R", "r", "L"}
ROAD_CHARS = {"R", "r"}
LOCATION_CHARS = {"L"}
SKIP_VALIDATION = {"L"}  # L cells skip R1-R4 checks entirely


def parse_map(map_lines: list[str]) -> list[list[str]]:
    grid = []
    for line in map_lines:
        row = [ch for ch in line if ch in VALID_CHARS]
        if row:
            grid.append(row)
    # pad to rect
    width = max(len(r) for r in grid) if grid else 0
    for r in grid:
        while len(r) < width:
            r.append("S")
    return grid


def get_char(grid, r, c) -> str:
    """安全取字符，越界视为 S"""
    if r < 0 or r >= len(grid) or c < 0 or c >= len(grid[r]):
        return "S"
    return grid[r][c]


def is_land(ch):
    return ch in LAND_CHARS


def is_sea(ch):
    return ch == "S"


def is_location(ch):
    return ch in LOCATION_CHARS


# ============================================================
# 3. 地形规则校验 (在 resolve_tile 之前必须通过)
# ============================================================
#
# 规则:
#   R1: 道路 (R/r) 不能直接相邻海 (S)。道路必须被陆地 (G/O) 包裹。
#       Why: 没有 "海+道路" 沙滩 tile, 只有 "海+陆地" 沙滩。
#
#   R2: 一格陆地 (G/O/R/r) 不能在水平方向上左右都是海 (薄半岛宽=1),
#       也不能在垂直方向上上下都是海 (薄半岛高=1)。
#       Why: 1 格宽/高的陆地缺少 island 之外可用的 tile, 视觉断裂;
#            岛要么是 1×1 完全独立 (4 海) → island, 要么必须 ≥ 2 格宽和高。
#       例外: 当一格陆地同时被 4 边海包围时 (孤立 1×1 岛), 由 island-2 表达, 合法。
#
#   R3: 海格 (S) 不能在水平方向上左右都是陆地 (S 宽=1 的海峡),
#       也不能在垂直方向上上下都是陆地 (S 高=1 的海峡)。
#       Why: 与 R2 同源 — 没有 "海峡" tile, 沙滩需要至少 2 格海作为缓冲。
#
#   R4: 道路 (R/r) 不能被陆地完全包围 (即 4 邻居都不是道路)。
#       道路必须至少与一个邻居道路相连。
#       Why: 孤立的道路点没有意义 — 道路应当形成网络;
#            被陆地全包的单点用陆地表达即可。
#
# 校验失败时抛出 MapValidationError 并列出所有违规位置。


class MapValidationError(ValueError):
    pass


def validate_map(grid) -> list[str]:
    """检查地图是否符合 tile 集合的几何约束。返回违规列表 (空 = 合法)。"""
    errors: list[str] = []
    rows = len(grid)
    if rows == 0:
        return errors
    cols = max(len(r) for r in grid)

    for r in range(rows):
        for c in range(cols):
            ch = get_char(grid, r, c)

            # L cells skip validation entirely (they are pure markers,
            # always rendered as a fixed "location" tile).
            if ch in SKIP_VALIDATION:
                continue

            top = get_char(grid, r - 1, c)
            bot = get_char(grid, r + 1, c)
            lft = get_char(grid, r, c - 1)
            rgt = get_char(grid, r, c + 1)

            # R1: 道路不能直接挨海
            if ch in ROAD_CHARS:
                for d, nb in [
                    ("top", top),
                    ("bottom", bot),
                    ("left", lft),
                    ("right", rgt),
                ]:
                    if is_sea(nb):
                        errors.append(
                            f"R1 [{r},{c}] '{ch}' road touches sea on {d}; "
                            f"roads must be wrapped by land (G/O)."
                        )

            # R4: 道路不能被陆地完全包围 (4 邻居中至少 1 个是道路)
            if ch in ROAD_CHARS:
                if not any(nb in ROAD_CHARS for nb in (top, bot, lft, rgt)):
                    errors.append(
                        f"R4 [{r},{c}] '{ch}' road is surrounded by ground "
                        f"(no adjacent R/r); roads must connect to other roads."
                    )

            # R2: 陆地不能是 1 格宽/高的薄半岛
            if is_land(ch):
                # 1×1 完全孤岛 (4 边都是海) 是合法的
                if is_sea(top) and is_sea(bot) and is_sea(lft) and is_sea(rgt):
                    pass
                else:
                    if is_sea(lft) and is_sea(rgt):
                        errors.append(
                            f"R2 [{r},{c}] '{ch}' land has sea on BOTH left and right "
                            f"(width=1 peninsula). Land must be ≥2 wide here."
                        )
                    if is_sea(top) and is_sea(bot):
                        errors.append(
                            f"R2 [{r},{c}] '{ch}' land has sea on BOTH top and bottom "
                            f"(height=1 peninsula). Land must be ≥2 tall here."
                        )

            # R3: 海不能是 1 格宽/高的海峡
            if is_sea(ch):
                if is_land(lft) and is_land(rgt):
                    errors.append(
                        f"R3 [{r},{c}] 'S' sea has land on BOTH left and right "
                        f"(width=1 strait). Sea must be ≥2 wide here."
                    )
                if is_land(top) and is_land(bot):
                    errors.append(
                        f"R3 [{r},{c}] 'S' sea has land on BOTH top and bottom "
                        f"(height=1 strait). Sea must be ≥2 tall here."
                    )

    return errors


# ============================================================
# 4. 核心：从九宫格 → tile desc
# ============================================================


def resolve_tile(grid, r, c) -> str:
    ch = grid[r][c]
    if ch == "S":
        return "W-full-sea"
    if ch == "L":
        # L is always a fixed "location" marker tile, regardless of neighbors.
        return "location"
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
    # 4 cardinal 是否海
    n_top = is_sea(get_char(grid, r - 1, c))
    n_bot = is_sea(get_char(grid, r + 1, c))
    n_lft = is_sea(get_char(grid, r, c - 1))
    n_rgt = is_sea(get_char(grid, r, c + 1))

    # 4 diagonal 是否海
    d_tl = is_sea(get_char(grid, r - 1, c - 1))
    d_tr = is_sea(get_char(grid, r - 1, c + 1))
    d_bl = is_sea(get_char(grid, r + 1, c - 1))
    d_br = is_sea(get_char(grid, r + 1, c + 1))

    seas = []
    if n_top:
        seas.append("top")
    if n_bot:
        seas.append("bottom")
    if n_lft:
        seas.append("left")
    if n_rgt:
        seas.append("right")
    n = len(seas)

    if n == 0:
        # cardinals 全陆地 → 检查对角是否有海 (内凹角)
        # 优先级: tl, tr, bl, br (一般地图至多一个为真)
        if d_tl:
            return f"{prefix}-left-top-negative-beach"
        if d_tr:
            return f"{prefix}-right-top-negative-beach"
        if d_bl:
            return f"{prefix}-left-bottom-negative-beach"
        if d_br:
            return f"{prefix}-right-bottom-negative-beach"
        return full

    if n == 1:
        return f"{prefix}-{seas[0]}-beach"

    if n == 2:
        s = set(seas)
        # 对向: 薄半岛, 没有专用 tile, 退化
        if s == {"top", "bottom"}:
            return f"{prefix}-top-beach"
        if s == {"left", "right"}:
            return f"{prefix}-left-beach"
        # L 角: 命名 horizontal-vertical
        h = "left" if "left" in s else "right"
        v = "top" if "top" in s else "bottom"
        return f"{prefix}-{h}-{v}-beach"

    if n == 3:
        return f"{prefix}-island"

    # n == 4
    return f"{prefix}-island-2"


def _road(grid, r, c, base, road):
    """只连接到其他道路 (R/r)"""
    conn = set()
    for d, dr_, dc_ in [
        ("top", -1, 0),
        ("bottom", 1, 0),
        ("left", 0, -1),
        ("right", 0, 1),
    ]:
        nb = get_char(grid, r + dr_, c + dc_)
        if nb in ROAD_CHARS:
            conn.add(d)

    n = len(conn)
    if n == 4:
        return f"{base}-{road}-full-road"
    if n == 3:
        miss = ({"top", "bottom", "left", "right"} - conn).pop()
        m = {
            "top": "left-right-bottom",
            "bottom": "left-right-top",
            "left": "right-top-bottom",
            "right": "left-top-bottom",
        }
        return f"{base}-{road}-{m[miss]}-road"
    if n == 2:
        pair = frozenset(conn)
        m = {
            frozenset(["left", "right"]): "left-right",
            frozenset(["top", "bottom"]): "top-bottom",
            frozenset(["left", "top"]): "left-top",
            frozenset(["right", "top"]): "right-top",
            frozenset(["left", "bottom"]): "left-bottom",
            frozenset(["right", "bottom"]): "right-bottom",
        }
        return f"{base}-{road}-{m[pair]}-road"
    if n == 1:
        return f"{base}-{road}-{conn.pop()}-road"
    # 孤立: 退化为 full
    return f"{base}-{road}-full-road"


# ============================================================
# 4. 生成带 desc 的 JSON
# ============================================================


def generate_desc_json(grid, registry) -> list[list[dict]]:
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
    """生成静态 HTML — 用户手动点按钮 import map_resolved.json 渲染。

    与 assets_catalog.html 风格对齐: 无嵌入数据, 不依赖 fetch/HTTP server,
    直接 file:// 双击打开即可使用。
    """
    legend_items = [
        ("S", "海", "#1a5276"),
        ("G", "绿地", "#27ae60"),
        ("O", "红地", "#e67e22"),
        ("R", "绿路", "#2ecc71"),
        ("r", "红路", "#f39c12"),
    ]
    legend_html = "".join(
        f'<div class="li"><span class="lc" style="background:{color}"></span>{ch}={label}</div>'
        for ch, label, color in legend_items
    )
    colors_js = json.dumps(COLORS)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tile Map Viewer</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#1a1a2e;color:#eee;font-family:'Courier New',monospace;
  display:flex;flex-direction:column;align-items:center;min-height:100vh;padding:20px}}
h2{{margin-bottom:8px}}
.subtitle{{color:#888;font-size:13px;margin-bottom:18px}}
.toolbar{{display:flex;justify-content:center;gap:12px;margin-bottom:20px;flex-wrap:wrap;align-items:center}}
.toolbar button{{background:#0f3460;color:#e94560;border:1px solid #e94560;padding:8px 20px;
  border-radius:8px;cursor:pointer;font-size:14px;font-weight:600;font-family:inherit;transition:all .2s}}
.toolbar button:hover{{background:#e94560;color:#fff}}
.toolbar .default-link{{background:#0f3460;color:#6a9fb5;border:1px solid #1b3a5c;padding:8px 20px;
  border-radius:8px;font-size:13px;text-decoration:none;display:inline-flex;align-items:center;transition:all .2s}}
.toolbar .default-link:hover{{background:#1b3a5c;color:#e94560;border-color:#e94560}}
.map{{display:grid;gap:1px;padding:16px;background:#16213e;border-radius:12px;
  box-shadow:0 8px 32px rgba(0,0,0,.3)}}
.tile{{width:48px;height:48px;position:relative;border-radius:2px;overflow:hidden}}
.tile img{{width:100%;height:100%;object-fit:cover;image-rendering:pixelated}}
.tile .tag{{position:absolute;bottom:1px;right:1px;font-size:8px;color:#fff;
  background:rgba(0,0,0,.7);padding:0 2px;border-radius:2px;pointer-events:none}}
.tile .miss{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
  font-size:9px;color:#ff6b6b;text-align:center;padding:2px;line-height:1.1}}
.legend{{margin-top:20px;padding:16px;background:#0f3460;border-radius:8px;max-width:1000px}}
.legend h3{{margin-bottom:8px}}
.li{{display:inline-block;margin:4px 8px;font-size:13px}}
.lc{{display:inline-block;width:16px;height:16px;border-radius:3px;vertical-align:middle;margin-right:4px}}
.stats{{margin-top:20px;padding:16px;background:#0f3460;border-radius:8px;max-width:1000px;font-size:12px}}
.stats div{{margin:2px 0}}
.empty{{padding:40px;text-align:center;color:#888;line-height:1.6}}
.empty code{{background:#0f3460;padding:2px 6px;border-radius:3px;color:#6a9fb5}}
.toast{{position:fixed;bottom:30px;left:50%;transform:translateX(-50%);
  background:#16213e;color:#4ade80;border:1px solid #4ade80;
  padding:12px 24px;border-radius:10px;font-size:14px;font-weight:600;
  opacity:0;transition:opacity .3s;pointer-events:none;z-index:100}}
.toast.show{{opacity:1}}
.toast.error{{color:#ff6b6b;border-color:#ff6b6b}}
</style></head><body>
<h2>🗺️ Tile Map Viewer</h2>
<p class="subtitle">通过本地 server 自动加载 (推荐: <code>just view-map-bg</code>)，或手动 Import</p>
<div class="toolbar">
  <button onclick="document.getElementById('jsonFileInput').click()">📂 Import JSON</button>
  <a class="default-link" href="map_resolved.json" target="_blank">🔗 map_resolved.json</a>
  <input type="file" id="jsonFileInput" accept=".json" style="display:none">
</div>
<div id="root"><div class="empty">Loading…</div></div>
<div class="legend"><h3>图例</h3>{legend_html}</div>
<div id="stats"></div>
<div class="toast" id="toast"></div>
<script>
const COLORS = {colors_js};
// JSON 中的图片路径是绝对路径 (/Users/lsq/env/assets/game/...)。
// 本 HTML 在 output/ 下, 需要剥离绝对前缀, 再加 ../ 跳到 game/ 根。
const ABS_PREFIX = "/Users/lsq/env/assets/game/";

function showToast(msg, isError) {{
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast show' + (isError ? ' error' : '');
  setTimeout(() => t.className = 'toast', 2200);
}}

// 把 JSON 中的绝对路径转成 server 根 (/) 下的相对路径。
// HTML 在 /output/, server 根在 game/, 所以图片访问 /Tiles/xxx.png 即可。
function resolveSrc(fp) {{
  if (!fp) return '';
  if (fp.indexOf(ABS_PREFIX) === 0) return '/' + fp.slice(ABS_PREFIX.length);
  return fp;
}}

function render(grid) {{
  const cols = grid[0] ? grid[0].length : 0;
  const root = document.getElementById('root');
  root.innerHTML = '';
  const map = document.createElement('div');
  map.className = 'map';
  map.style.gridTemplateColumns = 'repeat(' + cols + ', 48px)';

  const missing = {{}};
  let html = '';
  grid.forEach((row, r) => {{
    row.forEach((cell, c) => {{
      const ch = cell.char, desc = cell.desc, fp = cell.file;
      const bg = COLORS[ch] || '#333';
      if (fp) {{
        html += '<div class="tile" title="' + desc + ' [' + r + ',' + c + ']">' +
                '<img src="' + resolveSrc(fp) + '">' +
                '<span class="tag">' + ch + '</span></div>';
      }} else {{
        missing[desc] = (missing[desc] || 0) + 1;
        html += '<div class="tile" style="background:' + bg + '" title="MISSING: ' + desc + ' [' + r + ',' + c + ']">' +
                '<span class="miss">' + desc + '</span></div>';
      }}
    }});
  }});
  map.innerHTML = html;
  root.appendChild(map);

  const stats = document.getElementById('stats');
  const missKeys = Object.keys(missing);
  if (missKeys.length) {{
    stats.className = 'stats';
    let s = '<h3>⚠️ 缺失资源</h3>';
    missKeys.sort((a, b) => missing[b] - missing[a]).forEach(k => {{
      s += '<div>' + k + ' × ' + missing[k] + '</div>';
    }});
    stats.innerHTML = s;
  }} else {{
    stats.className = '';
    stats.innerHTML = '';
  }}
}}

document.getElementById('jsonFileInput').addEventListener('change', function(e) {{
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = ev => {{
    try {{
      const data = JSON.parse(ev.target.result);
      if (!Array.isArray(data) || !Array.isArray(data[0])) {{
        throw new Error('expected 2D array of cells');
      }}
      render(data);
      showToast('✅ Loaded ' + data.length + '×' + (data[0]||[]).length);
    }} catch(err) {{
      showToast('❌ Invalid JSON: ' + err.message, true);
    }}
  }};
  reader.readAsText(file);
}});

// 启动: 优先 fetch 同目录 map_resolved.json (需要 http:// server)。
// 失败 (例如 file:// 打开) → 提示用户手动 Import。
(function autoload() {{
  if (location.protocol === 'file:') {{
    document.getElementById('root').innerHTML =
      '<div class="empty">⚠️ 你正在通过 <code>file://</code> 打开此页面，浏览器会拒绝加载本地图片。<br>' +
      '推荐: 在 game/ 目录运行 <code>just view-map-bg</code>，或手动 <b>📂 Import JSON</b>。</div>';
    return;
  }}
  fetch('map_resolved.json')
    .then(r => r.ok ? r.json() : Promise.reject(r.status))
    .then(data => {{ render(data); showToast('✅ Auto-loaded map_resolved.json'); }})
    .catch(err => {{
      document.getElementById('root').innerHTML =
        '<div class="empty">未自动找到 <code>map_resolved.json</code> (' + err + ')。<br>' +
        '请使用上面 <b>📂 Import JSON</b> 手动选择。</div>';
    }});
}})();
</script>
</body></html>"""

    with open(output_path, "w") as f:
        f.write(html)


# ============================================================
# 6. 主程序: 大测试图覆盖各种边界
# ============================================================


def process_single(base: Path, registry: TileRegistry) -> bool:
    """原边界测试地图 (24×34, 字符: S/G/O/R/r)。单场景。"""
    # ---- 合法的大型测试地图 (24 列 × 30 行) ----
    # 所有海/陆地块均 ≥2 格宽和高, 道路 ≥1 格陆地缓冲。
    # 区块 A (行  1- 9): G 大陆 — 测 4 边 + 4 外凸角 + 4 内凹角 (2x2 嵌入海)
    # 区块 B (行 12-20): O 大陆 — 测同样情况
    # 区块 C (行 23-27): 道路网络, 测所有 junction (G/O 路均有)
    # 区块 D (行 29)    : 小岛 (1×1, 2×2)
    map_decl = {
        "name": "boundary_test_map",
        "map": [
            "SSSSSSSSSSSSSSSSSSSSSSSS",
            "SGGGGGGGGGGGGGGGGGGGGGGS",
            "SGGGGGGGGGGGGGGGGGGGGGGS",
            "SGGSSGGGGGGGGGGGGGGGGGGS",
            "SGGSSGGGGGGGGGGGGGGGGGGS",
            "SGGGGGGGGGGGGGGSSGGGGGGS",
            "SGGGGGGGGGGGGGGSSGGGGGGS",
            "SGGGGGGGGGGGGGGGGGGGGGGS",
            "SGGGGGGGGGGGGGGGGGGGGGGS",
            "SGGGGGGGGGGGGGGGGGGGGGGS",
            "SSSSSSSSSSSSSSSSSSSSSSSS",
            "SSSSSSSSSSSSSSSSSSSSSSSS",
            "SOOOOOOOOOOOOOOOOOOOOOOS",
            "SOOOOOOOOOOOOOOOOOOOOOOS",
            "SOOOOSSOOOOOOOOOOOOOOOOS",
            "SOOOOSSOOOOOOOOOOOOOOOOS",
            "SOOOOOOOOOOOOOOOOOOOOOOS",
            "SOOOOOOOOOOOOOOOOSSOOOOS",
            "SOOOOOOOOOOOOOOOOSSOOOOS",
            "SOOOOOOOOOOOOOOOOOOOOOOS",
            "SOOOOOOOOOOOOOOOOOOOOOOS",
            "SSSSSSSSSSSSSSSSSSSSSSSS",
            "SSSSSSSSSSSSSSSSSSSSSSSS",
            "SGGGGGGGGGGGGGGGGGGGGGGS",
            "SGRRRRRGGGRGGGGGGRRRRRGS",
            "SGGGGGRGGGRRRRGGRGGGGRGS",
            "SGGRRRRRRRRGGGRRRRRRRRGS",
            "SGGGGGRGGGRRGGRGGGGGGRGS",
            "SGGGGGGGGGGGGGGGGGGGGGGS",
            "SSSSSSSSSSSSSSSSSSSSSSSS",
            "SSSSSSSSSSSSSSSSSSSSSSSS",
            "SSGSSSGGSSSGGSSSGGSSGGSS"[:24],
            "SSSSSSGGSSSGGSSSGGSSGGSS"[:24],
            "SSSSSSSSSSSSSSSSSSSSSSSS",
        ],
    }

    # 全部 pad / 截断到 24 列
    width = 24
    map_decl["map"] = [(line + "S" * width)[:width] for line in map_decl["map"]]

    input_dir = base / "input"
    output_dir = base / "output"
    input_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)

    map_path = input_dir / "map_decl.json"
    with open(map_path, "w") as f:
        json.dump(map_decl, f, indent=2, ensure_ascii=False)

    grid = parse_map(map_decl["map"])

    errors = validate_map(grid)
    if errors:
        print(f"❌ single map 校验失败: {len(errors)} 条违规\n")
        for e in errors:
            print(f"  • {e}")
        return False
    print("✅ single map 校验通过\n")

    desc_json = generate_desc_json(grid, registry)
    desc_path = output_dir / "map_resolved.json"
    with open(desc_path, "w") as f:
        json.dump(desc_json, f, indent=2, ensure_ascii=False)

    html_path = output_dir / "map_viewer.html"
    generate_html(grid, registry, str(html_path))

    print(f"[single] 地图声明: {map_path}")
    print(f"[single] 资源 JSON: {desc_path}")
    print(f"[single] HTML 查看器: {html_path}\n")

    descs = [cell["desc"] for row in desc_json for cell in row]
    print("Tile 使用统计 (single):")
    for desc, cnt in Counter(descs).most_common():
        marker = "  " if desc in registry else "✗ "
        print(f"  {marker}{desc}: {cnt}")

    missing = [d for d in set(descs) if d not in registry]
    if missing:
        print("\n⚠️ 注册表缺失 (HTML 中标红显示):")
        for d in sorted(missing):
            print(f"  - {d}")
    return True


# ============================================================
# 7. 多场景世界地图 (input/world_decl.json)
# ============================================================


def generate_world_viewer_html(world_resolved, registry, output_path):
    """生成多场景查看器 + 飞行切换动画 (passthrough animation)。

    设计要点:
      - 每个场景渲染为独立的 <div class="scene">, 初始仅 root scene 可见
      - 根场景 (world) 上叠加 regions: clickable 热点 + ✈️ 飞行图标
      - 点击 region → 飞行 700ms:
          · world scene 缩放并平移到 region 中心
          · ✈️ sprite 沿 bezier 曲线飞到 region
          · 到达后, 目标场景淡入, world 隐藏
      - "← Back" 反向播放同一动画
      - 浏览器前进/后退 (popstate) 同步场景
    """
    abs_prefix_js = json.dumps("/Users/lsq/env/assets/game/")

    # Embedded resolved data — viewer is meant to be opened via http server
    # that maps "/" to game/. So we embed the JSON directly.
    resolved_json = json.dumps(world_resolved, ensure_ascii=False)

    # Collect unique regions
    root_scene = next((s for s in world_resolved["scenes"] if s.get("back") is None), world_resolved["scenes"][0])
    regions = root_scene.get("regions", [])

    # Legend items
    legend_html = (
        '<div class="li"><span class="lc" style="background:#1a5276"></span>海</div>'
        '<div class="li"><span class="lc" style="background:#27ae60"></span>绿地</div>'
        '<div class="li"><span class="lc" style="background:#e67e22"></span>红地</div>'
        '<div class="li"><span class="lc" style="background:#2ecc71"></span>绿路</div>'
        '<div class="li"><span class="lc" style="background:#f39c12"></span>红路</div>'
        '<div class="li"><span class="lc" style="background:#6a9fb5"></span>📍 城市</div>'
    )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>World Map Viewer · Passthrough Flight</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0a0e27;color:#eee;font-family:'Courier New',monospace;
  display:flex;flex-direction:column;align-items:center;min-height:100vh;padding:20px;
  overflow:hidden}}
h2{{margin-bottom:4px;font-size:18px}}
.subtitle{{color:#888;font-size:12px;margin-bottom:14px}}
.toolbar{{display:flex;justify-content:center;gap:10px;margin-bottom:14px;flex-wrap:wrap;align-items:center}}
.toolbar button{{background:#0f3460;color:#e94560;border:1px solid #e94560;padding:7px 16px;
  border-radius:7px;cursor:pointer;font-size:13px;font-weight:600;font-family:inherit;transition:all .2s}}
.toolbar button:hover{{background:#e94560;color:#fff}}
.toolbar .back{{background:#16213e;color:#6a9fb5;border-color:#1b3a5c;display:none}}
.toolbar .back:hover{{background:#1b3a5c;color:#e94560;border-color:#e94560}}
.toolbar .back.show{{display:inline-flex;align-items:center;gap:6px}}
.scene-host{{position:relative;width:100%;max-width:1200px;height:600px;
  display:flex;align-items:center;justify-content:center;
  background:radial-gradient(ellipse at center, #16213e 0%, #0a0e27 100%);
  border-radius:12px;overflow:hidden;perspective:1200px}}
.scene{{position:absolute;display:grid;gap:1px;padding:12px;background:#16213e;
  border-radius:10px;box-shadow:0 8px 32px rgba(0,0,0,.4);
  transform-origin:center center;transition:transform .7s cubic-bezier(.4,.0,.2,1),
    opacity .7s ease}}
.scene.fade-out{{opacity:0;pointer-events:none}}
.scene.fade-in{{opacity:1;pointer-events:auto}}
.scene.hidden{{display:none}}
.tile{{width:36px;height:36px;position:relative;border-radius:2px;overflow:hidden;
  transition:width .3s,height .3s}}
.tile img{{width:100%;height:100%;object-fit:cover;image-rendering:pixelated}}
.tile .tag{{position:absolute;bottom:1px;right:1px;font-size:8px;color:#fff;
  background:rgba(0,0,0,.7);padding:0 2px;border-radius:2px;pointer-events:none}}
.tile .miss{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
  font-size:9px;color:#ff6b6b;text-align:center;padding:2px;line-height:1.1}}
.region{{position:absolute;border:2px solid #e94560;border-radius:8px;
  background:rgba(233,69,96,.08);cursor:pointer;transition:all .25s;
  display:flex;align-items:center;justify-content:center;flex-direction:column;
  font-size:14px;font-weight:700;color:#fff;text-shadow:0 1px 4px rgba(0,0,0,.8);
  pointer-events:auto;z-index:10}}
.region:hover{{background:rgba(233,69,96,.25);border-color:#ffd166;color:#ffd166;
  transform:scale(1.04)}}
.region .sub{{font-size:10px;font-weight:400;color:#ccc;margin-top:2px;
  text-shadow:0 1px 2px rgba(0,0,0,.9);letter-spacing:.2px}}
.region .pin{{position:absolute;top:-14px;font-size:16px;
  filter:drop-shadow(0 1px 2px rgba(0,0,0,.8))}}
.flight{{position:absolute;width:42px;height:42px;pointer-events:none;z-index:50;
  opacity:0;transform-origin:center center;transition:none}}
.flight.show{{opacity:1}}
.flight img{{width:100%;height:100%;object-fit:contain;
  filter:drop-shadow(0 2px 6px rgba(0,0,0,.6))}}
.legend{{margin-top:14px;padding:12px;background:#0f3460;border-radius:8px;max-width:1200px}}
.legend h3{{margin-bottom:6px;font-size:13px}}
.li{{display:inline-block;margin:3px 6px;font-size:12px}}
.lc{{display:inline-block;width:14px;height:14px;border-radius:3px;vertical-align:middle;margin-right:3px}}
.toast{{position:fixed;bottom:30px;left:50%;transform:translateX(-50%);
  background:#16213e;color:#4ade80;border:1px solid #4ade80;
  padding:10px 20px;border-radius:9px;font-size:13px;font-weight:600;
  opacity:0;transition:opacity .3s;pointer-events:none;z-index:200}}
.toast.show{{opacity:1}}
.scene-label{{position:absolute;top:18px;left:50%;transform:translateX(-50%);
  background:rgba(15,52,96,.92);color:#ffd166;padding:6px 18px;border-radius:18px;
  font-size:14px;font-weight:700;letter-spacing:1px;border:1px solid #e94560;
  pointer-events:none;z-index:15;opacity:0;transition:opacity .35s}}
.scene-label.show{{opacity:1}}
</style></head><body>
<h2>🌍 Birthday World · 6 年飞行航线</h2>
<p class="subtitle">点击地图上的红色区域 → 飞入子场景 · 按 ← Back 返回</p>
<div class="toolbar">
  <button class="back" id="backBtn">← 返回世界</button>
</div>
<div class="scene-host" id="sceneHost">
  <div class="scene-label" id="sceneLabel"></div>
  <div class="flight" id="flight"><img src="/kenney_pixel-shmup/Ships/ship_0001.png" alt="✈️"></div>
</div>
<div class="legend"><h3>图例</h3>{legend_html}</div>
<div class="toast" id="toast"></div>
<script>
const ABS_PREFIX = {abs_prefix_js};
const RESOLVED = {resolved_json};
const COLORS = {{S:"#1a5276",G:"#27ae60",O:"#e67e22",R:"#2ecc71",r:"#f39c12",L:"#6a9fb5"}};

const $ = (id) => document.getElementById(id);
const host = $("sceneHost");
const flight = $("flight");
const sceneLabel = $("sceneLabel");
const backBtn = $("backBtn");
const toast = $("toast");

function showToast(msg, isErr) {{
  toast.textContent = msg;
  toast.className = "toast show" + (isErr ? " error" : "");
  setTimeout(() => toast.className = "toast", 1800);
}}

function resolveSrc(fp) {{
  if (!fp) return "";
  if (fp.indexOf(ABS_PREFIX) === 0) return "/" + fp.slice(ABS_PREFIX.length);
  return fp;
}}

// 渲染单个场景的 grid (cell 数组)
function renderGrid(cells) {{
  const rows = cells.length;
  const cols = cells[0] ? cells[0].length : 0;
  const div = document.createElement("div");
  div.className = "scene-grid";
  div.style.gridTemplateColumns = `repeat(${{cols}}, 36px)`;
  let html = "";
  cells.forEach((row, r) => {{
    row.forEach((cell, c) => {{
      const ch = cell.char, desc = cell.desc, fp = cell.file;
      if (fp) {{
        html += `<div class="tile" title="${{desc}} [${{r}},${{c}}]">` +
                `<img src="${{resolveSrc(fp)}}">` +
                `<span class="tag">${{ch}}</span></div>`;
      }} else {{
        html += `<div class="tile" style="background:${{COLORS[ch]||'#333'}}" title="MISSING: ${{desc}}">` +
                `<span class="miss">${{desc}}</span></div>`;
      }}
    }});
  }});
  div.innerHTML = html;
  return div;
}}

// 全部场景预渲染 (隐藏), 等待切换显示
const sceneEls = {{}};
RESOLVED.scenes.forEach((sc, idx) => {{
  const wrap = document.createElement("div");
  wrap.className = "scene hidden";
  wrap.id = "scene-" + sc.id;
  wrap.dataset.idx = idx;
  wrap.appendChild(renderGrid(sc.grid));

  // 根场景叠加热区
  if (sc.regions && sc.regions.length) {{
    // 拿到 tile 像素位置
    const tileSize = 36 + 1; // gap 1px
    const pad = 12;
    sc.regions.forEach(reg => {{
      const r = document.createElement("div");
      r.className = "region";
      r.dataset.target = reg.id;
      r.style.left = (pad + reg.col * tileSize) + "px";
      r.style.top = (pad + reg.row * tileSize) + "px";
      r.style.width = (reg.cols * tileSize - 1) + "px";
      r.style.height = (reg.rows * tileSize - 1) + "px";
      r.innerHTML = `<span class="pin">📍</span>${{reg.label}}<div class="sub">${{reg.subtitle || ""}}</div>`;
      wrap.appendChild(r);
    }});
  }}

  host.appendChild(wrap);
  sceneEls[sc.id] = wrap;
}});

// 计算根场景的 region 中心 (像素坐标, 相对于 host)
function getRegionCenterPx(region) {{
  const tileSize = 37;
  const pad = 12;
  const cx = pad + (region.col + region.cols / 2) * tileSize - 0.5;
  const cy = pad + (region.row + region.rows / 2) * tileSize - 0.5;
  return {{ cx, cy }};
}}

// 飞行 + 切换场景
let currentId = null;
let animating = false;

function showScene(id, opts = {{}}) {{
  const target = sceneEls[id];
  if (!target) return;
  Object.values(sceneEls).forEach(el => {{
    el.classList.add("hidden");
    el.classList.remove("fade-in", "fade-out");
  }});
  target.classList.remove("hidden");
  target.classList.add("fade-in");
  target.style.transform = "translate(0,0) scale(1)";
  currentId = id;
  const sc = RESOLVED.scenes.find(s => s.id === id);
  sceneLabel.textContent = sc ? sc.title : "";
  sceneLabel.classList.add("show");
  backBtn.classList.toggle("show", !!(sc && sc.back));
  history.replaceState({{ id }}, "", "#" + id);
}}

// 飞行 + 缩放
function flyTo(targetId) {{
  if (animating || !sceneEls[targetId]) return;
  const fromId = currentId;
  const fromEl = sceneEls[fromId];
  const toEl = sceneEls[targetId];
  const fromScene = RESOLVED.scenes.find(s => s.id === fromId);
  const toScene = RESOLVED.scenes.find(s => s.id === targetId);

  // 决定是 "飞入" (从父→子) 还是 "飞出" (子→父)
  const isEnter = toScene.back === fromId;
  if (!isEnter) {{
    showScene(targetId);
    return;
  }}

  // 找父场景中对应的 region
  const reg = (fromScene.regions || []).find(r => r.id === targetId);
  if (!reg) {{
    showScene(targetId);
    return;
  }}

  animating = true;
  const hostRect = host.getBoundingClientRect();
  const tileSize = 37;
  const pad = 12;
  const regCenter = {{
    cx: pad + (reg.col + reg.cols / 2) * tileSize - 0.5,
    cy: pad + (reg.row + reg.rows / 2) * tileSize - 0.5,
  }};

  // world 缩放中心 = host 中心
  const hostCx = hostRect.width / 2;
  const hostCy = hostRect.height / 2;
  const dx = hostCx - regCenter.cx;
  const dy = hostCy - regCenter.cy;

  // 把 world scene 缩放并平移, 让 region 中心对齐 host 中心
  fromEl.style.transformOrigin = `${{regCenter.cx}}px ${{regCenter.cy}}px`;
  fromEl.style.transform = `translate(${{dx}}px, ${{dy}}px) scale(2)`;
  fromEl.classList.add("fade-out");

  // 飞机从 host 中心飞到 region 中心 (in reverse, 我们要它看起来从中心出发)
  // 实际上: 进入动画时, 飞机从 region 飞向中心 (飞机已经"到达"目标, 然后离开)
  // 退出动画时反过来
  const startX = regCenter.cx, startY = regCenter.cy;
  const endX = hostCx, endY = hostCy;
  flight.style.left = (startX - 21) + "px";
  flight.style.top = (startY - 21) + "px";
  flight.style.transform = "rotate(0deg) scale(0.5)";
  flight.classList.add("show");

  requestAnimationFrame(() => {{
    // 飞机飞到中心
    flight.style.transition = "left .7s cubic-bezier(.4,.0,.2,1), top .7s cubic-bezier(.4,.0,.2,1), transform .7s ease";
    flight.style.left = (endX - 21) + "px";
    flight.style.top = (endY - 21) + "px";
    flight.style.transform = "rotate(-30deg) scale(1.2)";
  }});

  setTimeout(() => {{
    // 切换场景
    flight.classList.remove("show");
    fromEl.classList.add("hidden");
    toEl.classList.remove("hidden");
    toEl.classList.add("fade-in");
    toEl.style.transform = "scale(0.85)";
    requestAnimationFrame(() => {{
      toEl.style.transition = "transform .35s ease-out";
      toEl.style.transform = "scale(1)";
    }});
    currentId = targetId;
    backBtn.classList.add("show");
    const sc = RESOLVED.scenes.find(s => s.id === targetId);
    sceneLabel.textContent = sc ? sc.title : "";
    history.pushState({{ id: targetId }}, "", "#" + targetId);
    animating = false;
  }}, 720);
}}

// 点击 region: 飞入
host.addEventListener("click", (e) => {{
  const reg = e.target.closest(".region");
  if (!reg || animating) return;
  flyTo(reg.dataset.target);
}});

// Back 按钮: 飞回父场景
backBtn.addEventListener("click", () => {{
  if (animating || !currentId) return;
  const sc = RESOLVED.scenes.find(s => s.id === currentId);
  if (!sc || !sc.back) return;
  flyBack(sc.back);
}});

function flyBack(parentId) {{
  if (animating) return;
  const fromEl = sceneEls[currentId];
  const toEl = sceneEls[parentId];
  if (!toEl) return;
  const toScene = RESOLVED.scenes.find(s => s.id === parentId);
  const regMatch = (toScene.regions || []).find(r => r.id === currentId);
  if (!regMatch) {{
    showScene(parentId);
    return;
  }}

  animating = true;
  const hostRect = host.getBoundingClientRect();
  const hostCx = hostRect.width / 2;
  const hostCy = hostRect.height / 2;
  const tileSize = 37;
  const pad = 12;
  const regCenter = {{
    cx: pad + (regMatch.col + regMatch.cols / 2) * tileSize - 0.5,
    cy: pad + (regMatch.row + regMatch.rows / 2) * tileSize - 0.5,
  }};

  // 飞机从中心飞到 region
  flight.style.transition = "none";
  flight.style.left = (hostCx - 21) + "px";
  flight.style.top = (hostCy - 21) + "px";
  flight.style.transform = "rotate(30deg) scale(1.2)";
  flight.classList.add("show");

  fromEl.classList.add("fade-out");
  fromEl.style.transform = "scale(0.85)";

  requestAnimationFrame(() => {{
    flight.style.transition = "left .7s cubic-bezier(.4,.0,.2,1), top .7s cubic-bezier(.4,.0,.2,1), transform .7s ease";
    flight.style.left = (regCenter.cx - 21) + "px";
    flight.style.top = (regCenter.cy - 21) + "px";
    flight.style.transform = "rotate(0deg) scale(0.5)";
  }});

  setTimeout(() => {{
    flight.classList.remove("show");
    fromEl.classList.add("hidden");
    toEl.classList.remove("hidden");
    toEl.classList.add("fade-in");
    toEl.style.transformOrigin = `${{regCenter.cx}}px ${{regCenter.cy}}px`;
    toEl.style.transform = "translate(0,0) scale(2)";
    requestAnimationFrame(() => {{
      toEl.style.transition = "transform .7s cubic-bezier(.4,.0,.2,1)";
      const dx = hostCx - regCenter.cx;
      const dy = hostCy - regCenter.cy;
      toEl.style.transform = `translate(${{dx}}px, ${{dy}}px) scale(2)`;
      // 然后再回弹到原位
      setTimeout(() => {{
        toEl.style.transition = "transform .5s ease-out";
        toEl.style.transform = "translate(0,0) scale(1)";
      }}, 50);
    }});
    currentId = parentId;
    const sc = RESOLVED.scenes.find(s => s.id === parentId);
    sceneLabel.textContent = sc ? sc.title : "";
    backBtn.classList.toggle("show", !!(sc && sc.back));
    history.pushState({{ id: parentId }}, "", "#" + parentId);
    setTimeout(() => {{ animating = false; }}, 750);
  }}, 720);
}}

window.addEventListener("popstate", (e) => {{
  const id = (e.state && e.state.id) || RESOLVED.scenes[0].id;
  if (id !== currentId) showScene(id);
}});

// 启动: 显示根场景
const initialId = (location.hash || "#" + RESOLVED.scenes[0].id).slice(1);
showScene(initialId);
showToast("✅ 加载 " + RESOLVED.scenes.length + " 个场景");
</script>
</body></html>"""

    with open(output_path, "w") as f:
        f.write(html)


def process_world(base: Path, registry: TileRegistry) -> bool:
    """读取 input/world_decl.json, 解析每个场景, 输出 world_resolved.json + world_viewer.html。

    Schema:
      {
        "name": "...",
        "scenes": [
          {
            "id": "world",        // 唯一 ID
            "title": "🌍 世界地图",
            "back": null,         // 父场景 ID, 根场景为 null
            "rows": 22, "cols": 60,
            "map": [...],         // 字符 S/G/O/R/r/L
            "regions": [          // 仅根场景: 可点击的子区域
              {"id": "china", "label": "中国", "row": 4, "col": 28, "rows": 5, "cols": 9, "subtitle": "..."}
            ]
          },
          // ... 其它子场景 (没有 regions)
        ]
      }
    """
    input_dir = base / "input"
    output_dir = base / "output"
    input_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)

    world_path = input_dir / "world_decl.json"
    if not world_path.exists():
        print("[world] 跳过: input/world_decl.json 不存在\n")
        return True

    with open(world_path, "r") as f:
        world_decl = json.load(f)

    scenes_in = world_decl.get("scenes", [])
    if not scenes_in:
        print("[world] 跳过: scenes 为空\n")
        return True

    # 校验每个场景
    print(f"[world] 发现 {len(scenes_in)} 个场景, 开始校验:")
    all_ok = True
    for sc in scenes_in:
        sid = sc.get("id", "?")
        try:
            grid = parse_map(sc["map"])
        except Exception as e:
            print(f"  ❌ {sid}: parse 失败 {e}")
            all_ok = False
            continue
        errors = validate_map(grid)
        if errors:
            print(f"  ❌ {sid} ({len(grid)}x{len(grid[0]) if grid else 0}): {len(errors)} 条违规")
            for e in errors[:5]:
                print(f"      • {e}")
            if len(errors) > 5:
                print(f"      ... ({len(errors) - 5} more)")
            all_ok = False
        else:
            print(f"  ✅ {sid} ({len(grid)}x{len(grid[0]) if grid else 0})")
    if not all_ok:
        print("[world] 校验失败, 不写产物\n")
        return False

    # 解析每个场景
    scenes_out = []
    for sc in scenes_in:
        grid = parse_map(sc["map"])
        cells = generate_desc_json(grid, registry)
        scene_obj = {
            "id": sc["id"],
            "title": sc.get("title", sc["id"]),
            "back": sc.get("back"),
            "rows": len(grid),
            "cols": len(grid[0]) if grid else 0,
            "grid": cells,
        }
        if "regions" in sc:
            scene_obj["regions"] = sc["regions"]
        scenes_out.append(scene_obj)

    resolved = {"name": world_decl.get("name", "world"), "scenes": scenes_out}
    resolved_path = output_dir / "world_resolved.json"
    with open(resolved_path, "w") as f:
        json.dump(resolved, f, indent=2, ensure_ascii=False)

    html_path = output_dir / "world_viewer.html"
    generate_world_viewer_html(resolved, registry, str(html_path))

    print(f"\n[world] 资源 JSON: {resolved_path}")
    print(f"[world] HTML 查看器: {html_path}\n")

    # Tile 统计
    all_descs = [cell["desc"] for sc in scenes_out for row in sc["grid"] for cell in row]
    print("Tile 使用统计 (world):")
    for desc, cnt in Counter(all_descs).most_common():
        marker = "  " if desc in registry else "✗ "
        print(f"  {marker}{desc}: {cnt}")

    missing = [d for d in set(all_descs) if d not in registry]
    if missing:
        print("\n⚠️ world 注册表缺失 (HTML 中标红显示):")
        for d in sorted(missing):
            print(f"  - {d}")
    return True


def main():
    base = Path(__file__).parent
    registry = parse_tile_registry(str(base / "assets_map_check.json"))

    print("=" * 60)
    print("map_builder v4 — 单场景 + 多场景世界")
    print("=" * 60 + "\n")

    print(">>> 处理单场景 (boundary test map)")
    process_single(base, registry)

    print("\n>>> 处理多场景 (world)")
    process_world(base, registry)


if __name__ == "__main__":
    main()
