# tests/test_validate.py
from pipeline.grid import parse_map
from pipeline.validate import validate_map


def test_validate_clean_grid_returns_no_errors() -> None:
    # All-land 3x3: every G has land on all 4 sides, no 1-wide peninsula.
    grid = parse_map(["GGGGG", "GGGGG", "GGGGG"])
    assert validate_map(grid) == []


def test_r1_road_touching_sea_is_violation() -> None:
    # 'R' on edge of land touching sea on right.
    grid = parse_map(["SGGRS"])
    errors = validate_map(grid)
    assert any("R1" in e and "right" in e for e in errors)


def test_r2_land_width_one_peninsula() -> None:
    # G at (1,2): land above + below, sea on both left and right -> 1-wide peninsula.
    grid = parse_map(["GGGGGG", "SSGSSG", "GGGGGG"])
    errors = validate_map(grid)
    assert any("R2" in e and "left and right" in e for e in errors)


def test_r2_one_by_one_island_is_legal() -> None:
    # 1x1 land surrounded by sea on all 4 sides — legal (island-2 tile).
    grid = parse_map(["SSSSS", "SSSGS", "SSSSS"])
    errors = validate_map(grid)
    assert not any("R2" in e for e in errors)


def test_r3_sea_strait_height_one() -> None:
    # Sea at (1,1) has land on both top and bottom.
    grid = parse_map(["SGS", "SSS", "SGS"])
    errors = validate_map(grid)
    assert any("R3" in e for e in errors)


def test_r4_isolated_road_surrounded_by_land() -> None:
    # Single 'R' cell with no road neighbors — violation.
    grid = parse_map(["SGGGS", "SGRGS", "SGGGS"])
    errors = validate_map(grid)
    assert any("R4" in e for e in errors)


def test_l_cell_skips_all_validation() -> None:
    # 'L' marker, even on the edge, should not trigger any rule.
    grid = parse_map(["SSSSS", "SSSSS", "SSSLS", "SSSSS", "SSSSS"])
    assert validate_map(grid) == []
