# tests/test_grid.py
from pipeline.grid import parse_map, get_char


def test_parse_map_basic_rectangle() -> None:
    grid = parse_map(["SSG", "GGG", "GGS"])
    assert len(grid) ==3
    assert all(len(r) ==3 for r in grid)
    assert grid[0] == ["S", "S", "G"]


def test_parse_map_pads_short_rows_with_sea() -> None:
    grid = parse_map(["SSG", "GG"])
    assert len(grid) ==2
    assert grid[1] == ["G", "G", "S"] # padded to width3


def test_parse_map_strips_unknown_chars() -> None:
    grid = parse_map(["SXG", "GZG"])
    # 'X' and 'Z' are not in VALID_CHARS, stripped
    assert grid == [["S", "G"], ["G", "G"]]


def test_get_char_returns_sea_on_out_of_bounds() -> None:
    grid = parse_map(["GG", "GG"])
    assert get_char(grid, -1,0) == "S"
    assert get_char(grid,0, -1) == "S"
    assert get_char(grid,99,99) == "S"
    assert get_char(grid,0,0) == "G"
