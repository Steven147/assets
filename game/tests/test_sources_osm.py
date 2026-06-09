# tests/test_sources_osm.py — bbox & rasterize tests
import json
import math
from unittest.mock import patch, MagicMock
from pipeline.sources.osm import (
    compute_bbox, real_size_km, latlon_to_xy, xy_to_latlon,
    rasterize_polygon, CANVAS_SIZE,
    build_overpass_query, build_decl, OsmSource,
)


def test_compute_bbox_symmetric_around_center() -> None:
    bb = compute_bbox(31.2304, 121.4737, 10.0)
    assert bb["min_lat"] < 31.2304 < bb["max_lat"]
    assert bb["min_lon"] < 121.4737 < bb["max_lon"]
    # half-side in km = 5
    h_lat = (bb["max_lat"] - bb["min_lat"]) * 111.32
    assert math.isclose(h_lat, 10.0, abs_tol=0.1)


def test_real_size_km_matches_input() -> None:
    bb = compute_bbox(31.2304, 121.4737, 10.0)
    w, h = real_size_km(bb)
    assert math.isclose(w, 10.0, rel_tol=0.01)
    assert math.isclose(h, 10.0, rel_tol=0.01)


def test_latlon_to_xy_corner_corners() -> None:
    bb = compute_bbox(31.2304, 121.4737, 10.0)
    # Top-left (max_lat, min_lon) -> (0, 0)
    x, y = latlon_to_xy(bb["max_lat"], bb["min_lon"], bb)
    assert (x, y) == (0, 0)
    # Bottom-right (min_lat, max_lon) -> canvas size, off-by-one allowed
    x, y = latlon_to_xy(bb["min_lat"], bb["max_lon"], bb)
    assert (x, y) in {(CANVAS_SIZE - 1, CANVAS_SIZE - 1), (CANVAS_SIZE, CANVAS_SIZE)}


def test_xy_to_latlon_inverse() -> None:
    bb = compute_bbox(31.2304, 121.4737, 10.0)
    lat0, lon0 = 31.25, 121.5
    x, y = latlon_to_xy(lat0, lon0, bb)
    lat1, lon1 = xy_to_latlon(x, y, bb)
    assert math.isclose(lat0, lat1, abs_tol=0.001)
    assert math.isclose(lon0, lon1, abs_tol=0.001)


def test_rasterize_polygon_fills_interior() -> None:
    bb = compute_bbox(31.2304, 121.4737, 10.0)
    # 4x4 grid polygon
    coords = [
        (bb["max_lat"], bb["min_lon"]),
        (bb["max_lat"], bb["max_lon"]),
        (bb["min_lat"], bb["max_lon"]),
        (bb["min_lat"], bb["min_lon"]),
    ]
    grid = [["S"] * CANVAS_SIZE for _ in range(CANVAS_SIZE)]
    rasterize_polygon(coords, bb, "G", grid)
    # Center cell should be "G" (filled), corner might be "G" too if polygon is full canvas
    center_x, center_y = CANVAS_SIZE // 2, CANVAS_SIZE // 2
    assert grid[center_y][center_x] == "G"


def test_build_overpass_query_includes_bbox() -> None:
    bb = compute_bbox(31.2304, 121.4737, 10.0)
    q = build_overpass_query(bb)
    # The query uses raw float repr, not rounded to .4f
    assert str(bb["min_lat"]) in q
    assert "out body" in q


def test_build_decl_single_grid_no_world() -> None:
    bb = compute_bbox(31.2304, 121.4737, 10.0)
    grid = [["S"] * 10 for _ in range(10)]
    decl = build_decl(
        {"name": "Shanghai", "lat": 31.2304, "lon": 121.4737},
        bb, grid, [],
    )
    assert decl["name"] == "shanghai_map"
    assert decl["kind"] == "single"
    assert decl["source"] == "osm"
    # OSM source always uses CANVAS_SIZE for the rasters
    assert decl["rows"] == CANVAS_SIZE
    assert decl["cols"] == CANVAS_SIZE
    assert "pois" in decl and decl["pois"] == []


def test_osm_source_run_with_mocked_overpass(tmp_path, monkeypatch) -> None:
    """End-to-end with HTTP mocked."""
    monkeypatch.chdir(tmp_path)
    # Minimal fake Overpass response: one way (park) + one node (museum)
    fake_response = {
        "elements": [
            {"type": "way", "id": 1, "nodes": [10, 11, 12, 13], "tags": {"leisure": "park"}},
            {"type": "node", "id": 10, "lat": 31.235, "lon": 121.478, "tags": {}},
            {"type": "node", "id": 11, "lat": 31.235, "lon": 121.468, "tags": {}},
            {"type": "node", "id": 12, "lat": 31.225, "lon": 121.468, "tags": {}},
            {"type": "node", "id": 13, "lat": 31.225, "lon": 121.478, "tags": {}},
            {"type": "node", "id": 20, "lat": 31.23, "lon": 121.473,
             "tags": {"tourism": "museum", "name": "Test Museum"}},
        ]
    }

    def fake_urlopen(req, timeout=None):
        m = MagicMock()
        m.read.return_value = json.dumps(fake_response).encode("utf-8")
        m.__enter__ = lambda s: s
        m.__exit__ = lambda s, *a: False
        return m

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    src = OsmSource()
    out = src.run(city="shanghai", size_km=2.0, name="shanghai_test")
    assert out.exists()
    decl = json.loads(out.read_text(encoding="utf-8"))
    assert decl["name"] == "shanghai_test"
    assert decl["kind"] == "single"
    assert decl["source"] == "osm"
    # Park should have rasterized some 'G' cells.
    assert "G" in decl["map"][0] or any("G" in row for row in decl["map"])
    # Museum is a POI.
    assert any(p["name"] == "Test Museum" for p in decl["pois"])
