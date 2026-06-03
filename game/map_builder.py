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

VALID_CHARS = {"S", "G", "O", "R", "r"}
LAND_CHARS = {"G", "O", "R", "r"}
ROAD_CHARS = {"R", "r"}


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


def main():
    base = Path(__file__).parent
    registry = parse_tile_registry(str(base / "assets_map_check.json"))

    # ---- 合法的大型测试地图 (24 列 × 30 行) ----
    # 所有海/陆地块均 ≥2 格宽和高, 道路 ≥1 格陆地缓冲。
    # 区块 A (行  1- 9): G 大陆 — 测 4 边 + 4 外凸角 + 4 内凹角 (2x2 嵌入海)
    # 区块 B (行 12-20): O 大陆 — 测同样情况
    # 区块 C (行 23-27): 道路网络, 测所有 junction (G/O 路均有)
    # 区块 D (行 29)    : 小岛 (1×1, 2×2)
    map_decl = {
        "name": "boundary_test_map",
        "map": [
            # 0
            "SSSSSSSSSSSSSSSSSSSSSSSS",
            # ===== G 大陆 =====
            # 1  G 顶边
            "SGGGGGGGGGGGGGGGGGGGGGGS",
            # 2  G
            "SGGGGGGGGGGGGGGGGGGGGGGS",
            # 3  内凹海洞 1: 2x2 在 (3-4, 3-4)
            "SGGSSGGGGGGGGGGGGGGGGGGS",
            # 4
            "SGGSSGGGGGGGGGGGGGGGGGGS",
            # 5  内凹海洞 2: 2x2 在 (5-6, 14-15) → 4 个 negative + cardinal beach
            "SGGGGGGGGGGGGGGSSGGGGGGS",
            # 6
            "SGGGGGGGGGGGGGGSSGGGGGGS",
            # 7  G
            "SGGGGGGGGGGGGGGGGGGGGGGS",
            # 8  G
            "SGGGGGGGGGGGGGGGGGGGGGGS",
            # 9  G 底边
            "SGGGGGGGGGGGGGGGGGGGGGGS",
            # 10 海分隔 (≥2 高)
            "SSSSSSSSSSSSSSSSSSSSSSSS",
            # 11
            "SSSSSSSSSSSSSSSSSSSSSSSS",
            # ===== O 大陆 =====
            # 12 O 顶
            "SOOOOOOOOOOOOOOOOOOOOOOS",
            # 13 O
            "SOOOOOOOOOOOOOOOOOOOOOOS",
            # 14 内凹海洞: 2x2 在 (14-15, 4-5)
            "SOOOOSSOOOOOOOOOOOOOOOOS",
            # 15
            "SOOOOSSOOOOOOOOOOOOOOOOS",
            # 16 O
            "SOOOOOOOOOOOOOOOOOOOOOOS",
            # 17 内凹海洞: 2x2 在 (17-18, 16-17)
            "SOOOOOOOOOOOOOOOOSSOOOOS",
            # 18
            "SOOOOOOOOOOOOOOOOSSOOOOS",
            # 19 O
            "SOOOOOOOOOOOOOOOOOOOOOOS",
            # 20 O 底
            "SOOOOOOOOOOOOOOOOOOOOOOS",
            # 21 海分隔
            "SSSSSSSSSSSSSSSSSSSSSSSS",
            # 22
            "SSSSSSSSSSSSSSSSSSSSSSSS",
            # ===== 道路网络 (在 G 大陆内, 道路被 G 包裹) =====
            # 23 G 顶
            "SGGGGGGGGGGGGGGGGGGGGGGS",
            # 24 水平 R + 死路 + 间断
            "SGRRRRRGGGRGGGGGGRRRRRGS",
            # 25 垂直 R + T 字 + 十字
            "SGGGGGRGGGRRRRGGRGGGGRGS",
            # 26 十字 + 角
            "SGGRRRRRRRRGGGRRRRRRRRGS",
            # 27 多种死路 + 拐角 (col 11 死路连到 row 26)
            "SGGGGGRGGGRRGGRGGGGGGRGS",
            # 28 G 底
            "SGGGGGGGGGGGGGGGGGGGGGGS",
            # 29 海分隔 (≥2 高)
            "SSSSSSSSSSSSSSSSSSSSSSSS",
            # 30
            "SSSSSSSSSSSSSSSSSSSSSSSS",
            # ===== 小岛 (≥2x2 或 1x1 完全 4 海包围) =====
            # 31 第一行: 1x1 单点 + 2x2 + 2x2 + 2x2
            "SSGSSSGGSSSGGSSSGGSSGGSS"[:24],
            # 32 第二行: 仅 2x2 部分 (第一格不连续 → 1x1 自动孤立)
            "SSSSSSGGSSSGGSSSGGSSGGSS"[:24],
            # 33 海尾
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

    # 校验地形规则 (R1: 道路远离海; R2: 陆地不薄半岛; R3: 海不窄海峡)
    errors = validate_map(grid)
    if errors:
        print(f"❌ 地图校验失败: {len(errors)} 条违规\n")
        for e in errors:
            print(f"  • {e}")
        print()
        raise MapValidationError(
            f"map_decl 不符合 tile 几何约束 ({len(errors)} 条违规)"
        )
    print("✅ 地图校验通过\n")

    desc_json = generate_desc_json(grid, registry)
    desc_path = output_dir / "map_resolved.json"
    with open(desc_path, "w") as f:
        json.dump(desc_json, f, indent=2, ensure_ascii=False)

    html_path = output_dir / "map_viewer.html"
    generate_html(grid, registry, str(html_path))

    print(f"地图声明: {map_path}")
    print(f"资源 JSON: {desc_path}")
    print(f"HTML 查看器: {html_path}")
    print()

    descs = [cell["desc"] for row in desc_json for cell in row]
    print("Tile 使用统计:")
    for desc, cnt in Counter(descs).most_common():
        marker = "  " if desc in registry else "✗ "
        print(f"  {marker}{desc}: {cnt}")

    missing = [d for d in set(descs) if d not in registry]
    if missing:
        print("\n⚠️ 注册表缺失 (HTML 中标红显示):")
        for d in sorted(missing):
            print(f"  - {d}")


if __name__ == "__main__":
    main()
