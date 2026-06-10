"""Resolve each cell to a tile description via 9-neighbor analysis."""
from pipeline.grid import get_char
from pipeline.registry import TileRegistry

LAND_CHARS = {"G", "O", "R", "r", "L"}
ROAD_CHARS = {"R", "r"}

# 62 single-char codes: '0'-'9' + 'A'-'Z' + 'a'-'z'. Sorted alphabetically when
# assigned to descs, so the same desc set always produces the same mapping.
CODE_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
assert len(CODE_CHARS) == 62


def _is_sea(ch: str) -> bool:
    return ch == "S"


def _beach(grid, r, c, prefix, full) -> str:
    n_top = _is_sea(get_char(grid, r - 1, c))
    n_bot = _is_sea(get_char(grid, r + 1, c))
    n_lft = _is_sea(get_char(grid, r, c - 1))
    n_rgt = _is_sea(get_char(grid, r, c + 1))
    d_tl = _is_sea(get_char(grid, r - 1, c - 1))
    d_tr = _is_sea(get_char(grid, r - 1, c + 1))
    d_bl = _is_sea(get_char(grid, r + 1, c - 1))
    d_br = _is_sea(get_char(grid, r + 1, c + 1))

    seas = []
    if n_top: seas.append("top")
    if n_bot: seas.append("bottom")
    if n_lft: seas.append("left")
    if n_rgt: seas.append("right")
    n = len(seas)

    if n == 0:
        if d_tl: return f"{prefix}-left-top-negative-beach"
        if d_tr: return f"{prefix}-right-top-negative-beach"
        if d_bl: return f"{prefix}-left-bottom-negative-beach"
        if d_br: return f"{prefix}-right-bottom-negative-beach"
        return full
    if n == 1:
        return f"{prefix}-{seas[0]}-beach"
    if n == 2:
        s = set(seas)
        if s == {"top", "bottom"}: return f"{prefix}-top-beach"
        if s == {"left", "right"}: return f"{prefix}-left-beach"
        h = "left" if "left" in s else "right"
        v = "top" if "top" in s else "bottom"
        return f"{prefix}-{h}-{v}-beach"
    if n == 3:
        return f"{prefix}-island"
    return f"{prefix}-island-2"


def _road(grid, r, c, base, road) -> str:
    """Connect only to other roads."""
    conn = set()
    for d, dr, dc in [("top", -1, 0), ("bottom", 1, 0),
                      ("left", 0, -1), ("right", 0, 1)]:
        if get_char(grid, r + dr, c + dc) in ROAD_CHARS:
            conn.add(d)
    n = len(conn)
    if n == 4:
        return f"{base}-{road}-full-road"
    if n == 3:
        miss = ({"top", "bottom", "left", "right"} - conn).pop()
        m = {"top": "left-right-bottom", "bottom": "left-right-top",
             "left": "right-top-bottom", "right": "left-top-bottom"}
        return f"{base}-{road}-{m[miss]}-road"
    if n == 2:
        pair = frozenset(conn)
        m = {frozenset(["left", "right"]): "left-right",
             frozenset(["top", "bottom"]): "top-bottom",
             frozenset(["left", "top"]): "left-top",
             frozenset(["right", "top"]): "right-top",
             frozenset(["left", "bottom"]): "left-bottom",
             frozenset(["right", "bottom"]): "right-bottom"}
        return f"{base}-{road}-{m[pair]}-road"
    if n == 1:
        return f"{base}-{road}-{conn.pop()}-road"
    return f"{base}-{road}-full-road"


def resolve_tile(grid, r, c) -> str:
    ch = grid[r][c]
    if ch == "S": return "W-full-sea"
    if ch == "L": return "location"
    if ch == "R": return _road(grid, r, c, "G", "o")
    if ch == "r": return _road(grid, r, c, "o", "w")
    if ch == "G": return _beach(grid, r, c, "W-y-g", "G-full-land")
    if ch == "O": return _beach(grid, r, c, "W-y-o", "O-full-land")
    return "W-full-sea"


def generate_desc_json(grid, registry: TileRegistry) -> list[list[dict]]:
    """Deprecated: per-cell {char,desc,file} dict list. Replaced by build_compact_grid."""
    result = []
    for r, row in enumerate(grid):
        line = []
        for c in range(len(row)):
            desc = resolve_tile(grid, r, c)
            line.append({"char": grid[r][c], "desc": desc, "file": registry.get(desc, "")})
        result.append(line)
    return result


def build_compact_grid(grid, registry: TileRegistry) -> tuple[dict, list[str]]:
    """Resolve a char grid to (code_to_tile, encoded_grid).

    encoded_grid is a list of single-char strings (one per row, same shape as
    decl.json's ``map`` field). code_to_tile maps each code to
    ``{"desc": ..., "file": registry.get(desc, "")}``.

    Descs are sorted alphabetically before code assignment, so the same desc
    set always produces the same mapping. Raises ``ValueError`` if more than
    62 unique descs are encountered.
    """
    # 1. Resolve all cells to descs.
    desc_grid: list[list[str]] = [
        [resolve_tile(grid, r, c) for c in range(len(grid[r]))]
        for r in range(len(grid))
    ]
    unique_descs = sorted({d for row in desc_grid for d in row})
    if len(unique_descs) > len(CODE_CHARS):
        raise ValueError(
            f"build_compact_grid: {len(unique_descs)} unique descs exceeds "
            f"the {len(CODE_CHARS)}-char single-code budget; need 2-char encoding"
        )
    # 3. Build code->{desc,file} table.
    code_to_tile: dict[str, dict] = {
        CODE_CHARS[i]: {"desc": d, "file": registry.get(d, "")}
        for i, d in enumerate(unique_descs)
    }
    # 4. Encode grid: replace each desc with its single-char code, then join
    #    each row into a string (matches decl.json's `map` field shape).
    desc_to_code = {t["desc"]: code for code, t in code_to_tile.items()}
    encoded: list[str] = [
        "".join(desc_to_code[d] for d in row) for row in desc_grid
    ]
    return code_to_tile, encoded
