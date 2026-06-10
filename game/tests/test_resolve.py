# tests/test_resolve.py
from pipeline.grid import parse_map
from pipeline.resolve import resolve_tile, build_compact_grid
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
    code_to_tile, encoded = build_compact_grid(grid, registry)
    # 3x3 grid, encoded as list of strings (matches decl.json `map` shape)
    assert len(encoded) == 3
    assert all(isinstance(row, str) and len(row) == 3 for row in encoded)
    # Sea (S) row is uniform
    assert encoded[0] == encoded[1] == encoded[2] or (
        encoded[0][0] == encoded[0][1] == encoded[0][2]
    )  # all-S row
    assert encoded[1][1] != encoded[0][0]  # G-island vs S
    # The G island desc should be present in the registry
    descs = {v["desc"] for v in code_to_tile.values()}
    assert "W-y-g-island-2" in descs
    # file is empty when registry is empty
    code_for_g_island = next(c for c, t in code_to_tile.items() if t["desc"] == "W-y-g-island-2")
    assert code_to_tile[code_for_g_island]["file"] == ""
    # All cells in the encoded grid map back to the original descs
    for row in encoded:
        for ch in row:
            assert ch in code_to_tile


def test_build_compact_grid_codes_are_sorted_by_desc() -> None:
    # Two cells that resolve to two descs; sort order should be alphabetical
    grid = parse_map(["SS", "GG"])  # S row, G row
    registry = make_registry()
    code_to_tile, _ = build_compact_grid(grid, registry)
    descs = [t["desc"] for t in code_to_tile.values()]
    assert descs == sorted(descs)


def test_build_compact_grid_rejects_more_than_62_unique_descs() -> None:
    # A grid larger than 62 distinct descs is impossible to encode with one char.
    # We construct a 63x1 grid of unique chars (impossible in practice — VALID_CHARS
    # is only 6 — so instead we patch the resolve function).
    grid = parse_map(["S" * 1] * 1)
    registry = make_registry()
    import pytest
    from pipeline import resolve as resolve_mod
    calls = {"n": 0}

    def fake_resolve(_grid, _r, _c):
        calls["n"] += 1
        return f"desc-{calls['n']:03d}"

    original = resolve_mod.resolve_tile
    resolve_mod.resolve_tile = fake_resolve
    try:
        # Force a 63-cell grid to elicit 63 unique descs
        grid_63 = [["S"] for _ in range(63)]
        with pytest.raises(ValueError, match="62"):
            build_compact_grid(grid_63, registry)
    finally:
        resolve_mod.resolve_tile = original
