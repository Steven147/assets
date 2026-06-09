"""OSM source: Overpass API -> 1000x1000 character grid decl JSON.

Ported from osm_to_map.py; core helpers exposed for unit testing.
"""
import json
import math
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

CANVAS_SIZE = 1000
DEFAULT_SIZE_KM = 10.0

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

POI_TAGS = {
    "aeroway":  {"aerodrome", "terminal"},
    "railway":  {"station", "subway", "tram_stop", "halt", "monorail"},
    "tourism":  {"museum", "attraction", "viewpoint", "monument",
                 "artwork", "zoo", "theme_park", "gallery"},
    "historic": {"monument", "memorial", "castle", "ruins"},
    "amenity":  {"theatre", "cinema", "university", "hospital",
                 "library", "place_of_worship", "town_hall"},
    "leisure":  {"stadium", "marina", "park"},
    "natural":  {"peak", "spring"},
}

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
]


# ========== Geometry ==========

def compute_bbox(center_lat: float, center_lon: float, size_km: float) -> dict:
    lat_delta = (size_km / 2) / 111.32
    lon_delta = (size_km / 2) / (111.32 * math.cos(math.radians(center_lat)))
    return {
        "min_lat": center_lat - lat_delta,
        "max_lat": center_lat + lat_delta,
        "min_lon": center_lon - lon_delta,
        "max_lon": center_lon + lon_delta,
    }


def real_size_km(bbox: dict) -> tuple[float, float]:
    avg_lat = (bbox["min_lat"] + bbox["max_lat"]) / 2
    h = (bbox["max_lat"] - bbox["min_lat"]) * 111.32
    w = (bbox["max_lon"] - bbox["min_lon"]) * 111.32 * math.cos(math.radians(avg_lat))
    return w, h


def latlon_to_xy(lat: float, lon: float, bbox: dict) -> tuple[int, int]:
    x = (lon - bbox["min_lon"]) / (bbox["max_lon"] - bbox["min_lon"]) * CANVAS_SIZE
    y = (bbox["max_lat"] - lat) / (bbox["max_lat"] - bbox["min_lat"]) * CANVAS_SIZE
    return int(round(x)), int(round(y))


def xy_to_latlon(x: int, y: int, bbox: dict) -> tuple[float, float]:
    lon = bbox["min_lon"] + (x / CANVAS_SIZE) * (bbox["max_lon"] - bbox["min_lon"])
    lat = bbox["max_lat"] - (y / CANVAS_SIZE) * (bbox["max_lat"] - bbox["min_lat"])
    return lat, lon


# ========== Rasterize ==========

def _line_cells(p0, p1):
    x0, y0 = p0; x1, y1 = p1
    dx = abs(x1 - x0); dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1; sy = 1 if y0 < y1 else -1
    err = dx + dy; cells = []
    while True:
        cells.append((x0, y0))
        if x0 == x1 and y0 == y1: break
        e2 = 2 * err
        if e2 >= dy: err += dy; x0 += sx
        if e2 <= dx: err += dx; y0 += sy
    return cells


def rasterize_polygon(coords, bbox, char: str, grid: list[list[str]]) -> None:
    if len(coords) < 3: return
    pts = [latlon_to_xy(lat, lon, bbox) for lat, lon in coords]
    ys = [p[1] for p in pts]
    y_min = max(0, min(ys)); y_max = min(CANVAS_SIZE - 1, max(ys))
    for y in range(y_min, y_max + 1):
        xs = []
        for i in range(len(pts)):
            x1, y1 = pts[i]; x2, y2 = pts[(i + 1) % len(pts)]
            if (y1 <= y < y2) or (y2 <= y < y1):
                t = (y - y1) / (y2 - y1) if y2 != y1 else 0
                xs.append(x1 + t * (x2 - x1))
        xs.sort()
        for j in range(0, len(xs) - 1, 2):
            x0 = max(0, int(math.ceil(xs[j])))
            x1 = min(CANVAS_SIZE - 1, int(math.floor(xs[j + 1])))
            for x in range(x0, x1 + 1):
                grid[y][x] = char


def rasterize_line(coords, bbox, char: str, grid: list[list[str]]) -> None:
    if len(coords) < 2: return
    pts = [latlon_to_xy(lat, lon, bbox) for lat, lon in coords]
    for i in range(len(pts) - 1):
        for x, y in _line_cells(pts[i], pts[i + 1]):
            if 0 <= x < CANVAS_SIZE and 0 <= y < CANVAS_SIZE:
                grid[y][x] = char


def rasterize_poi(lat, lon, bbox, grid):
    x, y = latlon_to_xy(lat, lon, bbox)
    if 0 <= x < CANVAS_SIZE and 0 <= y < CANVAS_SIZE:
        grid[y][x] = "L"
    return x, y


# ========== Overpass ==========

def build_overpass_query(bbox: dict) -> str:
    b = f"{bbox['min_lat']},{bbox['min_lon']},{bbox['max_lat']},{bbox['max_lon']}"
    poly_specs = [
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


def _fetch_overpass_with_fallback(bbox: dict) -> dict:
    query = build_overpass_query(bbox)
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    last_err: Optional[Exception] = None
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            req = urllib.request.Request(
                endpoint, data=data,
                headers={"User-Agent": "osm-to-map/2.0 (game dev)"},
            )
            with urllib.request.urlopen(req, timeout=180) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            return payload
        except Exception as e:
            last_err = e
    raise RuntimeError(f"all Overpass endpoints failed: {last_err}")


def _index_elements(overpass_data: dict):
    nodes = {n["id"]: n for n in overpass_data.get("elements", [])
             if n.get("type") == "node"}
    ways: dict[int, dict] = {}
    way_geom: dict[int, list] = {}
    for w in overpass_data.get("elements", []):
        if w.get("type") != "way": continue
        ways[w["id"]] = w
        coords = [nodes[nid] for nid in w.get("nodes", []) if nid in nodes]
        if len(coords) >= 2:
            way_geom[w["id"]] = [(c["lat"], c["lon"]) for c in coords]
    return nodes, ways, way_geom


def build_decl(city_info: dict, bbox: dict, grid: list[list[str]], pois: list) -> dict:
    w_km, h_km = real_size_km(bbox)
    return {
        "name": city_info["name"].lower().replace(" ", "_") + "_map",
        "kind": "single",
        "source": "osm",
        "rows": CANVAS_SIZE,
        "cols": CANVAS_SIZE,
        "map": ["".join(row) for row in grid],
        "meta": {
            "city": city_info["name"],
            "center_lat": city_info["lat"],
            "center_lon": city_info["lon"],
            "bbox": bbox,
            "size_km": {"width": round(w_km, 3), "height": round(h_km, 3)},
            "scale_m_per_pixel": round(w_km * 1000 / CANVAS_SIZE, 2),
        },
        "pois": sorted(pois, key=lambda p: (p["category"], p["name"])),
    }


# ========== Source class ==========

class OsmSource:
    def run(self, city: str, size_km: float, name: Optional[str] = None) -> Path:
        c = PRESET_CITIES[city]
        center_lat, center_lon, city_name = c["lat"], c["lon"], c["name"]
        if name is None:
            name = f"{city}_{str(size_km).rstrip('0').rstrip('.').replace('.', '_')}km"

        bbox = compute_bbox(center_lat, center_lon, size_km)
        overpass_data = _fetch_overpass_with_fallback(bbox)
        nodes, ways, way_geom = _index_elements(overpass_data)

        grid = [["O"] * CANVAS_SIZE for _ in range(CANVAS_SIZE)]

        # Polygons (priority: S > G > O)
        poly_pri = [
            (["natural=water", "natural=coastline", "waterway=riverbank"], "S"),
            (["leisure=park", "landuse=grass", "landuse=forest",
              "landuse=cemetery", "leisure=garden", "leisure=nature_reserve"], "G"),
            (["landuse=residential", "landuse=commercial",
              "landuse=industrial", "landuse=retail"], "O"),
        ]
        for w in ways.values():
            tags = w.get("tags", {})
            coords = way_geom.get(w["id"])
            if not coords: continue
            for keys, char in poly_pri:
                matched = False
                for kv in keys:
                    k, v = kv.split("=", 1)
                    if tags.get(k) == v:
                        rasterize_polygon(coords, bbox, char, grid)
                        matched = True
                        break
                if matched: break

        # Roads
        for w in ways.values():
            tags = w.get("tags", {})
            hwy = tags.get("highway")
            if not hwy: continue
            coords = way_geom.get(w["id"])
            if not coords: continue
            if hwy in ("motorway", "trunk", "primary"):
                rasterize_line(coords, bbox, "R", grid)
            elif hwy in ("secondary", "tertiary", "residential"):
                rasterize_line(coords, bbox, "r", grid)

        # POIs
        pois = []
        for n in nodes.values():
            tags = n.get("tags", {})
            cat = None
            for k, vs in POI_TAGS.items():
                if tags.get(k) in vs:
                    cat = tags.get(k); break
            if not cat: continue
            name_poi = (tags.get("name:zh") or tags.get("name")
                        or tags.get("name:en") or "<unnamed>")
            x, y = rasterize_poi(n["lat"], n["lon"], bbox, grid)
            pois.append({
                "name": name_poi, "category": cat,
                "lat": n["lat"], "lon": n["lon"],
                "x": x, "y": y,
            })

        decl = build_decl(
            {"name": city_name, "lat": center_lat, "lon": center_lon},
            bbox, grid, pois,
        )
        decl["name"] = name  # override with user-provided name

        out_path = Path("output") / name / f"{name}_decl.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(decl, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return out_path
