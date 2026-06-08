#!/usr/bin/env python3
"""
osm_to_map.py — OSM 真实世界数据 → 1000×1000 游戏地图 decl JSON

将 OpenStreetMap 数据（带经纬度）映射到 1000×1000 的游戏画布上，
输出包含真实经纬度 + 画布坐标的 decl JSON，供下游 map_builder.py 消费。

工作流：
  osm_to_map.py → <name>_decl.json  ─┐
                                     ├→ map_builder.py → map_resolved.json + map_viewer.html
  手写 / 编辑 字符网格 ───────────────┘

比例建议（1000×1000 单城市）:
   5km ×  5km =  5 m/pixel   街区级, 建筑细节
  10km × 10km = 10 m/pixel   城市中心（推荐）
  20km × 20km = 20 m/pixel   整个区
  50km × 50km = 50 m/pixel   整个城市

用法:
  python3 osm_to_map.py --city shanghai --size-km 10
  python3 osm_to_map.py --lat 31.2304 --lon 121.4737 --size-km 5 --name my_city
  python3 osm_to_map.py --city beijing --size-km 10 --no-render
"""

import argparse
import json
import math
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# ============================================================
# 常量
# ============================================================

CANVAS_SIZE = 1000  # 1000×1000 画布

DEFAULT_SIZE_KM = 10.0

# 预置城市
PRESET_CITIES = {
    "shanghai":  {"name": "Shanghai",   "lat": 31.2304, "lon": 121.4737},
    "beijing":   {"name": "Beijing",    "lat": 39.9042, "lon": 116.4074},
    "tokyo":     {"name": "Tokyo",      "lat": 35.6895, "lon": 139.6917},
    "paris":     {"name": "Paris",      "lat": 48.8566, "lon":   2.3522},
    "london":    {"name": "London",     "lat": 51.5074, "lon":  -0.1278},
    "newyork":   {"name": "New York",   "lat": 40.7128, "lon": -74.0060},
    "hangzhou":  {"name": "Hangzhou",   "lat": 30.2741, "lon": 120.1551},
    "shenzhen":  {"name": "Shenzhen",   "lat": 22.5431, "lon": 114.0579},
    "guangzhou": {"name": "Guangzhou",  "lat": 23.1291, "lon": 113.2644},
}

# 字符 → 颜色（matplotlib 渲染用）
CHAR_COLORS = {
    "S": "#1a5276",  # 海
    "G": "#27ae60",  # 绿地
    "O": "#e67e22",  # 红地（已开发）
    "R": "#2ecc71",  # 绿路
    "r": "#f39c12",  # 红路
    "L": "#e74c3c",  # 位置标记
}

# Overpass 端点（fallback）
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
]

# POI 查询 tag（生成 L 标记）
POI_TAGS = {
    "aeroway":  {"aerodrome", "terminal", "aeroway"},
    "railway":  {"station", "subway", "tram_stop", "halt", "monorail"},
    "tourism":  {"museum", "attraction", "viewpoint", "monument",
                 "artwork", "zoo", "theme_park", "gallery"},
    "historic": {"monument", "memorial", "castle", "ruins", "archaeological_site"},
    "amenity":  {"theatre", "cinema", "university", "hospital",
                 "library", "place_of_worship", "town_hall"},
    "leisure":  {"stadium", "marina", "park"},
    "natural":  {"peak", "spring"},
}

# ============================================================
# 1. 几何转换
# ============================================================


def compute_bbox(center_lat: float, center_lon: float, size_km: float) -> Dict:
    """中心 + 正方形边长 → bbox。1°lat ≈ 111.32km, 1°lon ≈ 111.32·cos(lat)km。"""
    lat_delta = (size_km / 2) / 111.32
    lon_delta = (size_km / 2) / (111.32 * math.cos(math.radians(center_lat)))
    return {
        "min_lat": center_lat - lat_delta,
        "max_lat": center_lat + lat_delta,
        "min_lon": center_lon - lon_delta,
        "max_lon": center_lon + lon_delta,
    }


def real_size_km(bbox: Dict) -> Tuple[float, float]:
    """bbox 真实 km 尺寸 (width_km, height_km)。"""
    avg_lat = (bbox["min_lat"] + bbox["max_lat"]) / 2
    h_km = (bbox["max_lat"] - bbox["min_lat"]) * 111.32
    w_km = (bbox["max_lon"] - bbox["min_lon"]) * 111.32 * math.cos(math.radians(avg_lat))
    return w_km, h_km


def latlon_to_xy(lat: float, lon: float, bbox: Dict) -> Tuple[int, int]:
    """lat/lon → 1000×1000 画布 (x, y)。y 翻转使北在上。"""
    x = (lon - bbox["min_lon"]) / (bbox["max_lon"] - bbox["min_lon"]) * CANVAS_SIZE
    y = (bbox["max_lat"] - lat) / (bbox["max_lat"] - bbox["min_lat"]) * CANVAS_SIZE
    return int(round(x)), int(round(y))


def xy_to_latlon(x: int, y: int, bbox: Dict) -> Tuple[float, float]:
    """1000×1000 画布 (x, y) → lat/lon（用于照片 EXIF 反查）。"""
    lon = bbox["min_lon"] + (x / CANVAS_SIZE) * (bbox["max_lon"] - bbox["min_lon"])
    lat = bbox["max_lat"] - (y / CANVAS_SIZE) * (bbox["max_lat"] - bbox["min_lat"])
    return lat, lon


# ============================================================
# 2. Overpass API 查询
# ============================================================


def build_overpass_query(bbox: Dict) -> str:
    """构建多边形/线/点要素的 Overpass 查询。"""
    b = f"{bbox['min_lat']},{bbox['min_lon']},{bbox['max_lat']},{bbox['max_lon']}"

    poly_specs = [
        # (key, value) → land char
        ("natural", "water"), ("natural", "coastline"),
        ("waterway", "riverbank"),
        ("leisure", "park"), ("landuse", "grass"),
        ("landuse", "forest"), ("landuse", "cemetery"),
        ("leisure", "garden"), ("leisure", "nature_reserve"),
        ("landuse", "residential"), ("landuse", "commercial"),
        ("landuse", "industrial"), ("landuse", "retail"),
    ]
    parts = []
    for k, v in poly_specs:
        parts.append(f'  way["{k}"="{v}"]({b});')
        parts.append(f'  relation["{k}"="{v}"]({b});')

    for h in ["motorway", "trunk", "primary", "secondary", "tertiary", "residential"]:
        parts.append(f'  way["highway"="{h}"]({b});')

    for k, vs in POI_TAGS.items():
        for v in vs:
            parts.append(f'  node["{k}"="{v}"]({b});')

    return f"""
[out:json][timeout:180];
(
{chr(10).join(parts)}
);
out body;
>;
out skel qt;
"""


def fetch_overpass(bbox: Dict) -> Dict:
    """拉取 OSM 数据，自动 fallback 端点。"""
    query = build_overpass_query(bbox)
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")

    last_err: Optional[Exception] = None
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            print(f"  → Overpass: {endpoint}")
            t0 = time.time()
            req = urllib.request.Request(
                endpoint, data=data,
                headers={"User-Agent": "osm-to-map/1.0 (game dev)"},
            )
            with urllib.request.urlopen(req, timeout=180) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            print(f"  ← {len(payload.get('elements', []))} 要素 ({time.time()-t0:.1f}s)")
            return payload
        except Exception as e:
            print(f"  ✗ {endpoint}: {e}")
            last_err = e
    raise RuntimeError(f"所有 Overpass 端点均失败: {last_err}")


# ============================================================
# 3. 索引与几何
# ============================================================


def index_elements(overpass_data: Dict):
    """分离 nodes 和 way 几何。"""
    nodes = {n["id"]: n for n in overpass_data.get("elements", [])
             if n.get("type") == "node"}
    ways: Dict[int, Dict] = {}
    way_geom: Dict[int, List[Tuple[float, float]]] = {}
    for w in overpass_data.get("elements", []):
        if w.get("type") != "way":
            continue
        ways[w["id"]] = w
        coords = [nodes[nid] for nid in w.get("nodes", [])
                  if nid in nodes]
        if len(coords) >= 2:
            way_geom[w["id"]] = [(c["lat"], c["lon"]) for c in coords]
    return nodes, ways, way_geom


# ============================================================
# 4. 栅格化
# ============================================================


def line_cells(p0, p1):
    """Bresenham 直线。"""
    x0, y0 = p0
    x1, y1 = p1
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    cells = []
    while True:
        cells.append((x0, y0))
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy
    return cells


def rasterize_polygon(coords, bbox, char, grid):
    """扫描线多边形填充。"""
    if len(coords) < 3:
        return
    pts = [latlon_to_xy(lat, lon, bbox) for lat, lon in coords]
    ys = [p[1] for p in pts]
    y_min = max(0, min(ys))
    y_max = min(CANVAS_SIZE - 1, max(ys))
    for y in range(y_min, y_max + 1):
        xs = []
        for i in range(len(pts)):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % len(pts)]
            if (y1 <= y < y2) or (y2 <= y < y1):
                t = (y - y1) / (y2 - y1) if y2 != y1 else 0
                xs.append(x1 + t * (x2 - x1))
        xs.sort()
        for j in range(0, len(xs) - 1, 2):
            x0 = max(0, int(math.ceil(xs[j])))
            x1 = min(CANVAS_SIZE - 1, int(math.floor(xs[j + 1])))
            for x in range(x0, x1 + 1):
                grid[y][x] = char


def rasterize_line(coords, bbox, char, grid):
    """栅格化线（道路）。"""
    if len(coords) < 2:
        return
    pts = [latlon_to_xy(lat, lon, bbox) for lat, lon in coords]
    for i in range(len(pts) - 1):
        for x, y in line_cells(pts[i], pts[i + 1]):
            if 0 <= x < CANVAS_SIZE and 0 <= y < CANVAS_SIZE:
                grid[y][x] = char


def rasterize_poi(lat, lon, bbox, grid):
    x, y = latlon_to_xy(lat, lon, bbox)
    if 0 <= x < CANVAS_SIZE and 0 <= y < CANVAS_SIZE:
        grid[y][x] = "L"
    return x, y


# ============================================================
# 5. 构建 decl JSON
# ============================================================


def build_decl(city_info, bbox, grid, pois) -> Dict:
    w_km, h_km = real_size_km(bbox)
    return {
        "name": city_info["name"].lower().replace(" ", "_") + "_map",
        "width": CANVAS_SIZE,
        "height": CANVAS_SIZE,
        "real_world": {
            "city": city_info["name"],
            "center_lat": city_info["lat"],
            "center_lon": city_info["lon"],
            "bbox": bbox,
            "size_km": {"width": round(w_km, 3), "height": round(h_km, 3)},
            "scale_m_per_pixel": round(w_km * 1000 / CANVAS_SIZE, 2),
        },
        "map": ["".join(row) for row in grid],
        "pois": sorted(pois, key=lambda p: (p["category"], p["name"])),
    }


# ============================================================
# 6. 可视化
# ============================================================


def render_folium(decl: Dict, output_path: Path):
    """交互式真实地图：bbox 框 + POI 圆点 + 弹窗显示 lat/lon 与游戏坐标。"""
    try:
        import folium
    except ImportError:
        print("  ⚠️ folium 未装, 跳过")
        return False
    rw = decl["real_world"]
    m = folium.Map(location=[rw["center_lat"], rw["center_lon"]],
                   zoom_start=13, tiles="OpenStreetMap")
    bbox = rw["bbox"]
    folium.Rectangle(
        bounds=[[bbox["min_lat"], bbox["min_lon"]],
                [bbox["max_lat"], bbox["max_lon"]]],
        color="red", weight=2, fill=False,
        popup=f"{decl['name']}<br>Scale: {rw['scale_m_per_pixel']} m/pixel",
    ).add_to(m)
    cat_color = {
        "aerodrome": "red", "station": "blue", "subway": "purple",
        "museum": "green", "attraction": "darkgreen", "monument": "brown",
        "theatre": "orange", "park": "lightgreen",
    }
    for poi in decl["pois"]:
        folium.CircleMarker(
            location=[poi["lat"], poi["lon"]],
            radius=4,
            color=cat_color.get(poi["category"], "blue"),
            fill=True, fill_opacity=0.8,
            popup=(
                f"<b>{poi['name']}</b> ({poi['category']})<br>"
                f"Game: ({poi['x']}, {poi['y']})<br>"
                f"Lat/Lon: ({poi['lat']:.5f}, {poi['lon']:.5f})"
            ),
        ).add_to(m)
    m.save(str(output_path))
    print(f"  ✅ 真实地图 (folium): {output_path}")
    return True


def render_matplotlib(decl: Dict, output_path: Path):
    """1000×1000 静态视图: 字符网格 + POI 标注。"""
    try:
        import matplotlib.pyplot as plt
        from matplotlib.colors import ListedColormap
    except ImportError:
        print("  ⚠️ matplotlib 未装, 跳过")
        return False

    char_to_int = {"S": 0, "G": 1, "O": 2, "R": 3, "r": 4, "L": 5}
    grid_int = [[char_to_int.get(ch, 2) for ch in row] for row in decl["map"]]
    cmap = ListedColormap([CHAR_COLORS[c] for c in "SGO RrL".replace(" ", "")])

    fig, ax = plt.subplots(figsize=(11, 11))
    ax.imshow(grid_int, cmap=cmap, vmin=0, vmax=5,
              interpolation="nearest", origin="upper")
    for poi in decl["pois"]:
        ax.annotate(
            poi["name"], xy=(poi["x"], poi["y"]),
            xytext=(4, -6), textcoords="offset points",
            fontsize=5.5, color="white",
            bbox=dict(boxstyle="round,pad=0.15", fc="black", ec="none", alpha=0.75),
        )
    rw = decl["real_world"]
    ax.set_title(
        f"{rw['city']} — 1000×1000 Game Map\n"
        f"Real: {rw['size_km']['width']:.2f}×{rw['size_km']['height']:.2f} km  "
        f"·  Scale: {rw['scale_m_per_pixel']:.1f} m/pixel  "
        f"·  POIs: {len(decl['pois'])}",
        fontsize=11,
    )
    ax.set_xticks([])
    ax.set_yticks([])
    plt.tight_layout()
    plt.savefig(output_path, dpi=80, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✅ 游戏地图 (matplotlib): {output_path}")
    return True


def render_ascii(decl: Dict, max_width: int = 80):
    """终端 ASCII 预览。"""
    grid = decl["map"]
    h, w = len(grid), len(grid[0])
    step = max(1, w // max_width)
    print(f"\n--- ASCII 预览 ({w//step}×{h//step} 采样) ---")
    for y in range(0, h, step):
        print("".join(grid[y][x] for x in range(0, w, step)))
    print("---\n")


# ============================================================
# 7. 主流程
# ============================================================


def main():
    ap = argparse.ArgumentParser(
        description="OSM → 1000×1000 game map decl JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--city", choices=list(PRESET_CITIES.keys()))
    ap.add_argument("--lat", type=float, help="中心纬度")
    ap.add_argument("--lon", type=float, help="中心经度")
    ap.add_argument("--name", type=str, help="城市显示名")
    ap.add_argument("--size-km", type=float, default=DEFAULT_SIZE_KM,
                    help=f"正方形边长 (km), 默认 {DEFAULT_SIZE_KM}")
    ap.add_argument("--output-dir", default=".")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--open", action="store_true",
                    help="生成后用系统默认浏览器打开 folium 地图")
    args = ap.parse_args()

    if args.city:
        c = PRESET_CITIES[args.city]
        center_lat, center_lon, city_name = c["lat"], c["lon"], c["name"]
    elif args.lat is not None and args.lon is not None:
        center_lat, center_lon = args.lat, args.lon
        city_name = args.name or "custom"
    else:
        ap.error("需要 --city 或 (--lat + --lon)")

    if args.name:
        city_name = args.name

    print(f"📍 城市: {city_name}")
    print(f"   中心: ({center_lat}, {center_lon})")
    print(f"   范围: {args.size_km}×{args.size_km} km")

    bbox = compute_bbox(center_lat, center_lon, args.size_km)
    w_km, h_km = real_size_km(bbox)
    print(f"   真实尺寸: {w_km:.2f}×{h_km:.2f} km")
    print(f"   比例: {w_km * 1000 / CANVAS_SIZE:.1f} m/pixel")

    if w_km > 30:
        print(f"   ⚠️  范围较大 ({w_km:.0f}km), Overpass 查询可能慢, 建议先用 10km 试\n")
    else:
        print()

    try:
        overpass_data = fetch_overpass(bbox)
    except Exception as e:
        print(f"❌ Overpass 失败: {e}")
        sys.exit(1)

    nodes, ways, way_geom = index_elements(overpass_data)
    print(f"   nodes: {len(nodes)}, ways: {len(ways)}\n")

    # 初始化网格：默认 O（已开发用地）
    grid = [["O"] * CANVAS_SIZE for _ in range(CANVAS_SIZE)]

    # 多边形优先级: S > G > O
    poly_pri = [
        (["natural=water", "natural=coastline", "waterway=riverbank"], "S"),
        (["leisure=park", "landuse=grass", "landuse=forest",
          "landuse=cemetery", "leisure=garden", "leisure=nature_reserve"], "G"),
        (["landuse=residential", "landuse=commercial",
          "landuse=industrial", "landuse=retail"], "O"),
    ]
    poly_count = 0
    for w in ways.values():
        tags = w.get("tags", {})
        coords = way_geom.get(w["id"])
        if not coords:
            continue
        for keys, char in poly_pri:
            for kv in keys:
                k, v = kv.split("=", 1)
                if tags.get(k) == v:
                    rasterize_polygon(coords, bbox, char, grid)
                    poly_count += 1
                    break
            else:
                continue
            break
    print(f"  栅格化多边形: {poly_count}")

    # 道路
    road_count = 0
    for w in ways.values():
        tags = w.get("tags", {})
        hwy = tags.get("highway")
        if not hwy:
            continue
        coords = way_geom.get(w["id"])
        if not coords:
            continue
        if hwy in ("motorway", "trunk", "primary"):
            rasterize_line(coords, bbox, "R", grid)
            road_count += 1
        elif hwy in ("secondary", "tertiary", "residential"):
            rasterize_line(coords, bbox, "r", grid)
            road_count += 1
    print(f"  栅格化道路:   {road_count}")

    # POI
    pois = []
    for n in nodes.values():
        tags = n.get("tags", {})
        cat = None
        for k, vs in POI_TAGS.items():
            if tags.get(k) in vs:
                cat = tags.get(k)
                break
        if not cat:
            continue
        name = (tags.get("name:zh") or tags.get("name")
                or tags.get("name:en") or "<unnamed>")
        x, y = rasterize_poi(n["lat"], n["lon"], bbox, grid)
        pois.append({
            "name": name, "category": cat,
            "lat": n["lat"], "lon": n["lon"],
            "x": x, "y": y,
        })
    print(f"  POI:          {len(pois)}\n")

    decl = build_decl(
        {"name": city_name, "lat": center_lat, "lon": center_lon},
        bbox, grid, pois,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    decl_path = output_dir / f"{decl['name']}_decl.json"
    with open(decl_path, "w", encoding="utf-8") as f:
        json.dump(decl, f, ensure_ascii=False, indent=2)

    cnt = lambda c: sum(r.count(c) for r in grid)
    print(f"✅ Decl JSON: {decl_path}")
    print(f"   字符分布: S={cnt('S')}  G={cnt('G')}  O={cnt('O')}  "
          f"R={cnt('R')}  r={cnt('r')}  L={cnt('L')}")

    render_ascii(decl)

    if not args.no_render:
        folium_path = output_dir / f"{decl['name']}_real.html"
        png_path = output_dir / f"{decl['name']}_game.png"
        render_folium(decl, folium_path)
        render_matplotlib(decl, png_path)
        if args.open and folium_path.exists():
            import subprocess, platform
            if platform.system() == "Darwin":
                subprocess.Popen(["open", str(folium_path)])
            else:
                subprocess.Popen(["xdg-open", str(folium_path)])

    print(f"\n💡 下一步: 用 map_builder.py 处理 {decl_path.name}")
    print(f"   或: python3 -c \"import json; d=json.load(open('{decl_path}'))")
    print(f"            from osm_to_map import latlon_to_xy")
    print(f"            # 导入照片时: x,y = latlon_to_xy(photo_lat, photo_lon, d['real_world']['bbox'])\"")


if __name__ == "__main__":
    main()
