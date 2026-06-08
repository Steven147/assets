# tests/test_resolve.py
from pipeline.grid import parse_map
from pipeline.resolve import resolve_tile, generate_desc_json
from pipeline.registry import TileRegistry


def make_registry() -> TileRegistry:
    # Minimal stub: resolve_tile only returns desc, registry is for stage3.
    return TileRegistry([])


def test_full_sea_tile() -> None:
    grid = parse_map(["SS", "SS"])
    assert resolve_tile(grid, 0, 0) == "W-full-sea"


def test_full_land_green() -> None:
    grid = parse_map(["GGG", "GGG", "GGG"])
    assert resolve_tile(grid, 1, 1) == "G-full-land"


def test_full_land_orange() -> None:
    grid = parse_map(["OOO", "OOO", "OOO"])
    assert resolve_tile(grid, 1, 1) == "O-full-land"


def test_single_beach_cardinal() -> None:
    # G at (1,1): sea only on top -> single "top-beach"
    grid = parse_map(["SSS", "GGG", "GGG"])
    assert resolve_tile(grid, 1, 1) == "W-y-g-top-beach"


def test_l_corner_beach() -> None:
    # G at (1,1): sea on top AND right -> "right-top-beach" (L corner)
    grid = parse_map(["GSS", "GGS", "GGG"])
    assert resolve_tile(grid, 1, 1) == "W-y-g-right-top-beach"


def test_island_three_seas() -> None:
    # G at (1,1): sea on top, left, right -> "island"
    grid = parse_map(["SGS", "SGS", "SSS"])
    assert resolve_tile(grid, 1, 1) == "W-y-g-island"


def test_island_2_all_seas() -> None:
    grid = parse_map(["SSS", "SGS", "SSS"])
    assert resolve_tile(grid, 1, 1) == "W-y-g-island-2"


def test_negative_beach_diagonal() -> None:
    # G at (1,1): no cardinal sea, but (0,0) diagonal is sea -> "left-top-negative-beach"
    grid = parse_map(["SGGGG", "GGGGG", "GGGGG"])
    assert resolve_tile(grid, 1, 1) == "W-y-g-left-top-negative-beach"


def test_l_marker_returns_location() -> None:
    # L cells always render as fixed "location" marker.
    grid = parse_map(["LLS", "LLS", "LLS"])
    assert resolve_tile(grid, 0, 0) == "location"
    assert resolve_tile(grid, 0, 1) == "location"


def test_road_straight_horizontal() -> None:
    # R at (2,2) with R on left (2,1) and right (2,3) -> "left-right" green road
    grid = parse_map(["GGGGG", "GGGGG", "GRRRG", "GGGGG", "GGGGG"])
    assert resolve_tile(grid, 2, 2) == "G-o-left-right-road"


def test_road_t_junction() -> None:
    # R at (1,1): roads on top (0,1), bot (2,1), left (1,0) -> 3 roads, missing right
    grid = parse_map(["RR", "RR", "SR"])
    assert resolve_tile(grid, 1, 1) == "G-o-left-top-bottom-road"


def test_road_cross() -> None:
    # R with all 4 neighbors as road -> "full-road"
    grid = parse_map(["SRS", "RRRR", "SRS"])
    # (1,1) has road on all 4 sides
    assert resolve_tile(grid, 1, 1) == "G-o-full-road"


def test_generate_desc_json_shape() -> None:
    grid = parse_map(["SSS", "SGS", "SSS"])
    registry = make_registry()
    result = generate_desc_json(grid, registry)
    # 3x3 grid, each cell is a dict with char/desc/file keys
    assert len(result) == 3
    assert len(result[0]) == 3
    assert set(result[0][0].keys()) == {"char", "desc", "file"}
    assert result[0][0]["char"] == "S"
    assert result[1][1]["char"] == "G"
    assert result[1][1]["desc"] == "W-y-g-island-2"
    # file is empty when registry is empty
    assert result[1][1]["file"] == ""
