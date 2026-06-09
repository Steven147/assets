"""Character grid utilities: parse, safe access, JSON roundtrip."""
from typing import List

VALID_CHARS = {"S", "G", "O", "R", "r", "L"}


def parse_map(map_lines: list[str]) -> list[list[str]]:
    grid: list[list[str]] = []
    for line in map_lines:
        row = [ch for ch in line if ch in VALID_CHARS]
        if row:
            grid.append(row)
    width = max((len(r) for r in grid), default=0)
    for r in grid:
        while len(r) < width:
            r.append("S")
    return grid


def get_char(grid: list[list[str]], r: int, c: int) -> str:
    """Out-of-bounds treated as sea."""
    if r <0 or r >= len(grid) or c <0 or c >= len(grid[r]):
        return "S"
    return grid[r][c]
