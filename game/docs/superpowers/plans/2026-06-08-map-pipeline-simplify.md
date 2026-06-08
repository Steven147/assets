# Map Pipeline Simplify Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `map_builder.py` (1199 lines) + `osm_to_map.py` (566 lines) + `osm_build.py` (88 lines) with a clean 4-stage pipeline (`stage1_source` → `stage2_grid` → `stage3_resolved` → `stage4_html`) backed by a `pipeline/` subpackage of focused modules.

**Architecture:** 4 thin CLI scripts (`stage*_*.py`, 30-60 lines each) sit on top of a `pipeline/` subpackage containing `registry` / `decl` / `grid` / `validate` / `resolve` / `world` / `render` / `sources` (local + osm) / `html` (jinja2 templates). Stages communicate via JSON files in `output/<name>/` so each can be re-run independently. Source is pluggable by factory but only OSM + local are implemented.

**Tech Stack:** Python 3 (stdlib + `urllib` for OSM), jinja2 (HTML templates), pytest (tests), just (task runner).

---

## File Structure

### Delete (migration)
- `map_builder.py`
- `osm_to_map.py`
- `osm_build.py`
- `__pycache__/` (regenerated)

### Create — `pipeline/` subpackage
| File | Responsibility | Lines |
|------|---------------|-------|
| `pipeline/__init__.py` | Package marker | 1 |
| `pipeline/registry.py` | `parse_tile_registry()` + `TileRegistry` class (case-insensitive lookup) | ~50 |
| `pipeline/decl.py` | `read_decl()` / `write_decl()` — single unified schema | ~80 |
| `pipeline/grid.py` | `parse_map()` chars, `get_char()` safe, `grid_to_json()` / `json_to_grid()` | ~60 |
| `pipeline/validate.py` | `validate_map()` R1-R4 rules | ~80 |
| `pipeline/resolve.py` | `_beach()` / `_road()` / `resolve_tile()` / `generate_desc_json()` | ~120 |
| `pipeline/world.py` | `iter_scenes()` / `resolve_world_scenes()` shared world ops | ~60 |
| `pipeline/render.py` | `generate_map_html()` / `generate_world_html()` | ~80 |
| `pipeline/sources/__init__.py` | `get_source()` factory + `PRESET_CITY_KEYS` | ~20 |
| `pipeline/sources/local.py` | `LocalSource.run(name)` — copy `input/<name>_decl.json` to `output/<name>/` | ~40 |
| `pipeline/sources/osm.py` | `OsmSource.run(city, size_km, name)` — Overpass + rasterize + decl | ~500 |
| `pipeline/html/map_viewer.html.j2` | Single-scene viewer template | ~150 |
| `pipeline/html/world_viewer.html.j2` | Multi-scene viewer template | ~300 |

### Create — 4 stage scripts (each 30-60 lines)
| File | Stage |
|------|-------|
| `stage1_source.py` | source → `output/<name>/<name>_decl.json` |
| `stage2_grid.py` | decl → `output/<name>/<name>_grid.json` |
| `stage3_resolved.py` | grid → `output/<name>/<name>_resolved.json` |
| `stage4_html.py` | resolved → `output/<name>/<name>_viewer.html` or `world_viewer.html` |

### Create — tests
| File | Coverage |
|------|----------|
| `tests/conftest.py` | Add `tests/fixtures/` and `game/` to `sys.path` |
| `tests/test_registry.py` | TileRegistry: lookup, case-insensitive, missing key |
| `tests/test_grid.py` | parse_map (rect padding), get_char (out-of-bounds) |
| `tests/test_validate.py` | R1, R2, R3, R4 each with a tiny grid |
| `tests/test_resolve.py` | 1×1 island, L-corner, straight road, T-road, crossroad, isolated road |
| `tests/test_decl.py` | read/write roundtrip on a sample decl |
| `tests/test_world.py` | iter_scenes / resolve_world_scenes on a 2-scene fixture |
| `tests/test_sources_local.py` | LocalSource: single + world auto-detect, missing file |
| `tests/test_sources_osm.py` | OsmSource: bbox math, rasterize_polygon (mocked Overpass) |
| `tests/test_stages.py` | End-to-end: stage1→2→3→4 on `smoke_test` fixture |
| `tests/fixtures/smoke_test_decl.json` | 6×6 grid (single, all chars S/G/O/R/r/L) |

### Modify
| File | Change |
|------|--------|
| `justfile` | Replace all commands with new stage-based ones (see §8 of spec) |
| `input/world_decl.json` | Keep as-is (no rename needed) |

---

## Task 0.1: Project scaffolding (tests + pipeline dirs)

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/fixtures/smoke_test_decl.json`
- Create: `pipeline/__init__.py`

- [ ] **Step 1: Create `tests/__init__.py`**

```python
# tests/__init__.py — package marker
```

- [ ] **Step 2: Create `tests/conftest.py`**

```python
"""Pytest config: ensure game/ and tests/fixtures/ are importable."""
import sys
from pathlib import Path

GAME_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GAME_DIR))
sys.path.insert(0, str(GAME_DIR / "tests"))
```

- [ ] **Step 3: Create `tests/fixtures/smoke_test_decl.json`**

```json
{
  "name": "smoke_test",
  "kind": "single",
  "source": "local",
  "rows": 6,
  "cols": 6,
  "map": [
    "SSSSSS",
    "SGGGGGS",
    "SGRRRGS",
    "SGRRRGS",
    "SGGGGGS",
    "SSSSSS"
  ],
  "meta": {},
  "pois": []
}
```

- [ ] **Step 4: Create `pipeline/__init__.py`**

```python
# pipeline/__init__.py — package marker
```

- [ ] **Step 5: Run pytest with no tests yet to verify config works**

Run: `cd /Users/lsq/env/assets/game && python3 -m pytest tests/ -v --collect-only`
Expected: "no tests ran" or empty collection, no import errors.

- [ ] **Step 6: Commit**

```bash
git add tests/__init__.py tests/conftest.py tests/fixtures/smoke_test_decl.json pipeline/__init__.py
git commit -m "chore: scaffold pipeline/ and tests/ directories"
```

---

## Task 1.1: TileRegistry (TDD)

**Files:**
- Create: `pipeline/registry.py`
- Test: `tests/test_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_registry.py
import json
from pathlib import Path
import pytest
from pipeline.registry import parse_tile_registry, TileRegistry


def write_fixture(tmp_path: Path) -> Path:
    data = [
        {"file": "Tiles/a.png", "description": "W-full-sea"},
        {"file": "Tiles/b.png", "description": "w-y-g"},  # lowercase variant
        {"file": "Tiles/c.png", "description": ""},  # skipped
    ]
    p = tmp_path / "assets.json"
    p.write_text(json.dumps(data, ensure_ascii=False))
    return p


def test_parse_tile_registry_returns_class(tmp_path: Path) -> None:
    reg = parse_tile_registry(str(write_fixture(tmp_path)))
    assert isinstance(reg, TileRegistry)


def test_tile_registry_lookup_exact(tmp_path: Path) -> None:
    reg = parse_tile_registry(str(write_fixture(tmp_path)))
    assert reg.get("W-full-sea") == "Tiles/a.png"


def test_tile_registry_is_case_insensitive(tmp_path: Path) -> None:
    reg = parse_tile_registry(str(write_fixture(tmp_path)))
    # Description "w-y-g" stored lowercase; lookup with uppercase should hit.
    assert reg.get("W-Y-G") == "Tiles/b.png"
    assert reg.get("w-y-g") == "Tiles/b.png"


def test_tile_registry_missing_returns_empty(tmp_path: Path) -> None:
    reg = parse_tile_registry(str(write_fixture(tmp_path)))
    assert reg.get("does-not-exist") == ""


def test_tile_registry_contains_operator(tmp_path: Path) -> None:
    reg = parse_tile_registry(str(write_fixture(tmp_path)))
    assert "W-full-sea" in reg
    assert "w-y-g" in reg
    assert "missing" not in reg


def test_tile_registry_skips_empty_description(tmp_path: Path) -> None:
    reg = parse_tile_registry(str(write_fixture(tmp_path)))
    # Empty description was item index 2; should be skipped, not registered as "".
    assert reg.get("") == ""
```

- [ ] **Step 2: Run the test — verify it fails**

Run: `cd /Users/lsq/env/assets/game && python3 -m pytest tests/test_registry.py -v`
Expected: `ModuleNotFoundError: No module named 'pipeline.registry'`

- [ ] **Step 3: Implement `pipeline/registry.py`**

```python
"""Tile registry: maps tile description -> file path (case-insensitive)."""
import json
from pathlib import Path


class TileRegistry:
    def __init__(self, items: list) -> None:
        self._lower_to_file: dict[str, str] = {}
        self._lower_to_orig: dict[str, str] = {}
        for it in items:
            desc = (it.get("description") or "").strip()
            if not desc:
                continue
            key = desc.lower()
            if key not in self._lower_to_file:
                self._lower_to_file[key] = it["file"]
                self._lower_to_orig[key] = desc

    def get(self, desc: str, default: str = "") -> str:
        return self._lower_to_file.get(desc.lower(), default)

    def __contains__(self, desc: str) -> bool:
        return desc.lower() in self._lower_to_file


def parse_tile_registry(json_path: str) -> TileRegistry:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return TileRegistry(data)
```

- [ ] **Step 4: Run the test — verify it passes**

Run: `cd /Users/lsq/env/assets/game && python3 -m pytest tests/test_registry.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/registry.py tests/test_registry.py
git commit -m "feat(pipeline/registry): TileRegistry with case-insensitive lookup"
```

---

## Task 1.2: Grid parsing (TDD)

**Files:**
- Create: `pipeline/grid.py`
- Test: `tests/test_grid.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_grid.py
from pipeline.grid import parse_map, get_char


def test_parse_map_basic_rectangle() -> None:
    grid = parse_map(["SSG", "GGG", "GGS"])
    assert len(grid) == 3
    assert all(len(r) == 3 for r in grid)
    assert grid[0] == ["S", "S", "G"]


def test_parse_map_pads_short_rows_with_sea() -> None:
    grid = parse_map(["SSG", "GG"])
    assert len(grid) == 2
    assert grid[1] == ["G", "G", "S"]  # padded to width 3


def test_parse_map_strips_unknown_chars() -> None:
    grid = parse_map(["SXG", "GZG"])
    # 'X' and 'Z' are not in VALID_CHARS, stripped
    assert grid == [["S", "G"], ["G", "G"]]


def test_get_char_returns_sea_on_out_of_bounds() -> None:
    grid = parse_map(["GG", "GG"])
    assert get_char(grid, -1, 0) == "S"
    assert get_char(grid, 0, -1) == "S"
    assert get_char(grid, 99, 99) == "S"
    assert get_char(grid, 0, 0) == "G"
```

- [ ] **Step 2: Run the test — verify it fails**

Run: `cd /Users/lsq/env/assets/game && python3 -m pytest tests/test_grid.py -v`
Expected: `ModuleNotFoundError: No module named 'pipeline.grid'`

- [ ] **Step 3: Implement `pipeline/grid.py`**

```python
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
    if r < 0 or r >= len(grid) or c < 0 or c >= len(grid[r]):
        return "S"
    return grid[r][c]
```

- [ ] **Step 4: Run the test — verify it passes**

Run: `cd /Users/lsq/env/assets/game && python3 -m pytest tests/test_grid.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/grid.py tests/test_grid.py
git commit -m "feat(pipeline/grid): parse_map + get_char (rect padding + sea OOB)"
```

---

## Task 1.3: Geometry validation R1-R4 (TDD)

**Files:**
- Create: `pipeline/validate.py`
- Test: `tests/test_validate.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_validate.py
from pipeline.grid import parse_map
from pipeline.validate import validate_map


def test_validate_clean_grid_returns_no_errors() -> None:
    grid = parse_map(["SSSS", "SGGGS", "SSSS"])
    assert validate_map(grid) == []


def test_r1_road_touching_sea_is_violation() -> None:
    # 'R' on edge of land touching sea on right.
    grid = parse_map(["SGGRS"])
    errors = validate_map(grid)
    assert any("R1" in e and "right" in e for e in errors)


def test_r2_land_width_one_peninsula() -> None:
    # Land at (1,1) has sea on both left and right (1-wide peninsula).
    grid = parse_map(["SSS", "SGS", "SSS"])
    errors = validate_map(grid)
    assert any("R2" in e for e in errors)


def test_r2_one_by_one_island_is_legal() -> None:
    # 1x1 land surrounded by sea on all 4 sides — legal (island-2 tile).
    grid = parse_map(["SSS", "SGS", "SSS"])
    # Replace the land at (1,1) with sea and add a 1x1 island somewhere else.
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
```

- [ ] **Step 2: Run the test — verify it fails**

Run: `cd /Users/lsq/env/assets/game && python3 -m pytest tests/test_validate.py -v`
Expected: `ModuleNotFoundError: No module named 'pipeline.validate'`

- [ ] **Step 3: Implement `pipeline/validate.py`**

```python
"""Geometry validation rules R1-R4 (must pass before resolve_tile)."""
from pipeline.grid import get_char

LAND_CHARS = {"G", "O", "R", "r", "L"}
ROAD_CHARS = {"R", "r"}
SKIP_VALIDATION = {"L"}


def validate_map(grid: list[list[str]]) -> list[str]:
    """Return list of violation messages (empty = legal)."""
    errors: list[str] = []
    rows = len(grid)
    if rows == 0:
        return errors
    cols = max(len(r) for r in grid)

    for r in range(rows):
        for c in range(cols):
            ch = get_char(grid, r, c)
            if ch in SKIP_VALIDATION:
                continue

            top = get_char(grid, r - 1, c)
            bot = get_char(grid, r + 1, c)
            lft = get_char(grid, r, c - 1)
            rgt = get_char(grid, r, c + 1)

            # R1: road cannot directly touch sea
            if ch in ROAD_CHARS:
                for d, nb in [("top", top), ("bottom", bot),
                              ("left", lft), ("right", rgt)]:
                    if nb == "S":
                        errors.append(
                            f"R1 [{r},{c}] '{ch}' road touches sea on {d}; "
                            f"roads must be wrapped by land (G/O)."
                        )
                # R4: road must connect to another road
                if not any(nb in ROAD_CHARS for nb in (top, bot, lft, rgt)):
                    errors.append(
                        f"R4 [{r},{c}] '{ch}' road is surrounded by ground "
                        f"(no adjacent R/r); roads must connect to other roads."
                    )

            # R2: land cannot be 1-wide/1-tall peninsula (1x1 island is legal)
            if ch in LAND_CHARS:
                if not (top == "S" and bot == "S" and lft == "S" and rgt == "S"):
                    if lft == "S" and rgt == "S":
                        errors.append(
                            f"R2 [{r},{c}] '{ch}' land has sea on BOTH left and right "
                            f"(width=1 peninsula). Land must be >=2 wide here."
                        )
                    if top == "S" and bot == "S":
                        errors.append(
                            f"R2 [{r},{c}] '{ch}' land has sea on BOTH top and bottom "
                            f"(height=1 peninsula). Land must be >=2 tall here."
                        )

            # R3: sea cannot be 1-wide/1-tall strait
            if ch == "S":
                if lft in LAND_CHARS and rgt in LAND_CHARS:
                    errors.append(
                        f"R3 [{r},{c}] 'S' sea has land on BOTH left and right "
                        f"(width=1 strait). Sea must be >=2 wide here."
                    )
                if top in LAND_CHARS and bot in LAND_CHARS:
                    errors.append(
                        f"R3 [{r},{c}] 'S' sea has land on BOTH top and bottom "
                        f"(height=1 strait). Sea must be >=2 tall here."
                    )

    return errors
```

- [ ] **Step 4: Run the test — verify it passes**

Run: `cd /Users/lsq/env/assets/game && python3 -m pytest tests/test_validate.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/validate.py tests/test_validate.py
git commit -m "feat(pipeline/validate): R1-R4 geometry rules with L-skip"
```

---

## Task 1.4: Tile resolution — _beach, _road, resolve_tile (TDD)

**Files:**
- Create: `pipeline/resolve.py`
- Test: `tests/test_resolve.py`

- [ ] **Step 1: Write the failing test**

```python
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
    # G cell with sea only on top.
    grid = parse_map(["SSS", "SGG", "SGG"])
    assert resolve_tile(grid, 1, 1) == "W-y-g-top-beach"


def test_l_corner_beach() -> None:
    # G cell with sea on top AND right -> "right-top-beach"
    grid = parse_map(["SGG", "SGG", "SSS"])
    assert resolve_tile(grid, 1, 1) == "W-y-g-right-top-beach"


def test_island_three_seas() -> None:
    # G cell with sea on top, left, right -> "island"
    grid = parse_map(["SGS", "SGS", "SSS"])
    assert resolve_tile(grid, 1, 1) == "W-y-g-island"


def test_island_2_all_seas() -> None:
    grid = parse_map(["SSS", "SGS", "SSS"])
    assert resolve_tile(grid, 1, 1) == "W-y-g-island-2"


def test_negative_beach_diagonal() -> None:
    # G cell with no cardinal sea, but TL diagonal is sea -> "left-top-negative-beach"
    grid = parse_map(["SSGGG", "SGGGG", "GGGGG"])
    assert resolve_tile(grid, 1, 1) == "W-y-g-left-top-negative-beach"


def test_l_marker_returns_location() -> None:
    grid = parse_map(["GLG", "GGG", "GGG"])
    assert resolve_tile(grid, 0, 0) == "location"
    assert resolve_tile(grid, 0, 1) == "location"


def test_road_straight_horizontal() -> None:
    # R cell with R on left and right -> "left-right" green road
    grid = parse_map(["SSSS", "SGGG", "SRRGS", "SGGG", "SSSS"])
    # center road (2,2) has road at (2,1) and (2,3) -> left-right
    assert resolve_tile(grid, 2, 2) == "G-o-left-right-road"


def test_road_t_junction() -> None:
    # R cell with R on top, left, right (3 neighbors) -> "left-right-bottom" missing bottom
    grid = parse_map(["SRS", "SRRS", "SRS"])
    # (1,1) is missing top: result should encode "left-right-top" missing? No — T shape.
    # Actually R at (1,1) has roads at top (0,1), left (1,0), right (1,2). Missing bottom.
    assert resolve_tile(grid, 1, 1) == "G-o-left-right-bottom-road"


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
```

- [ ] **Step 2: Run the test — verify it fails**

Run: `cd /Users/lsq/env/assets/game && python3 -m pytest tests/test_resolve.py -v`
Expected: `ModuleNotFoundError: No module named 'pipeline.resolve'`

- [ ] **Step 3: Implement `pipeline/resolve.py`**

```python
"""Resolve each cell to a tile description via 9-neighbor analysis."""
from pipeline.grid import get_char
from pipeline.registry import TileRegistry

LAND_CHARS = {"G", "O", "R", "r", "L"}
ROAD_CHARS = {"R", "r"}


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
    result = []
    for r, row in enumerate(grid):
        line = []
        for c in range(len(row)):
            desc = resolve_tile(grid, r, c)
            line.append({"char": grid[r][c], "desc": desc, "file": registry.get(desc, "")})
        result.append(line)
    return result
```

- [ ] **Step 4: Run the test — verify it passes**

Run: `cd /Users/lsq/env/assets/game && python3 -m pytest tests/test_resolve.py -v`
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/resolve.py tests/test_resolve.py
git commit -m "feat(pipeline/resolve): 9-neighbor beach/road tile resolution"
```

---

## Task 1.5: Decl read/write (TDD)

**Files:**
- Create: `pipeline/decl.py`
- Test: `tests/test_decl.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_decl.py
import json
from pathlib import Path
import pytest
from pipeline.decl import read_decl, write_decl


SAMPLE_SINGLE = {
    "name": "foo",
    "kind": "single",
    "source": "local",
    "rows": 2, "cols": 2,
    "map": ["SS", "GG"],
    "meta": {},
    "pois": [],
}

SAMPLE_WORLD = {
    "name": "bar",
    "kind": "world",
    "source": "local",
    "scenes": [
        {"id": "root", "title": "Root", "back": None, "rows": 2, "cols": 2,
         "map": ["SS", "GG"], "regions": []},
    ],
}


def test_read_single(tmp_path: Path) -> None:
    p = tmp_path / "foo_decl.json"
    p.write_text(json.dumps(SAMPLE_SINGLE, ensure_ascii=False), encoding="utf-8")
    decl = read_decl(p)
    assert decl["name"] == "foo"
    assert decl["kind"] == "single"
    assert decl["map"] == ["SS", "GG"]


def test_read_world(tmp_path: Path) -> None:
    p = tmp_path / "bar_decl.json"
    p.write_text(json.dumps(SAMPLE_WORLD, ensure_ascii=False), encoding="utf-8")
    decl = read_decl(p)
    assert decl["kind"] == "world"
    assert len(decl["scenes"]) == 1
    assert decl["scenes"][0]["id"] == "root"


def test_write_then_read_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "round_decl.json"
    write_decl(SAMPLE_SINGLE, p)
    assert p.exists()
    again = read_decl(p)
    assert again == SAMPLE_SINGLE


def test_read_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_decl(tmp_path / "nope.json")


def test_auto_detect_kind_single() -> None:
    assert read_decl._detect_kind(SAMPLE_SINGLE) == "single"


def test_auto_detect_kind_world() -> None:
    assert read_decl._detect_kind(SAMPLE_WORLD) == "world"
```

- [ ] **Step 2: Run the test — verify it fails**

Run: `cd /Users/lsq/env/assets/game && python3 -m pytest tests/test_decl.py -v`
Expected: `ModuleNotFoundError: No module named 'pipeline.decl'`

- [ ] **Step 3: Implement `pipeline/decl.py`**

```python
"""Decl JSON: unified schema for source output (single or world)."""
import json
from pathlib import Path


def write_decl(decl: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(decl, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def read_decl(path: Path) -> dict:
    if not Path(path).exists():
        raise FileNotFoundError(f"decl not found: {path}")
    return json.loads(Path(path).read_text(encoding="utf-8"))


# Module-level helper for tests + sources/local.py
def _detect_kind(decl: dict) -> str:
    if "scenes" in decl:
        return "world"
    return decl.get("kind", "single")


read_decl._detect_kind = _detect_kind  # attach for testability
```

- [ ] **Step 4: Run the test — verify it passes**

Run: `cd /Users/lsq/env/assets/game && python3 -m pytest tests/test_decl.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/decl.py tests/test_decl.py
git commit -m "feat(pipeline/decl): read/write decl JSON with kind auto-detect"
```

---

## Task 1.6: World scene helpers (TDD)

**Files:**
- Create: `pipeline/world.py`
- Test: `tests/test_world.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_world.py
from pipeline.world import iter_scenes, resolve_world_scenes
from pipeline.registry import TileRegistry


WORLD_GRID_DOC = {
    "name": "test_world",
    "kind": "world",
    "scenes": [
        {
            "id": "root",
            "grid": [
                [{"char": "S"}, {"char": "G"}],
                [{"char": "G"}, {"char": "G"}],
            ],
            "validation": {"ok": True, "rule_violations": []},
        },
        {
            "id": "child",
            "grid": [
                [{"char": "G"}, {"char": "O"}],
                [{"char": "R"}, {"char": "r"}],
            ],
            "validation": {"ok": True, "rule_violations": []},
        },
    ],
}


def test_iter_scenes_yields_scenes_with_grid_and_metadata() -> None:
    out = list(iter_scenes(WORLD_GRID_DOC))
    assert len(out) == 2
    sid, grid, meta = out[0]
    assert sid == "root"
    assert grid == [["S", "G"], ["G", "G"]]
    assert meta["ok"] is True


def test_resolve_world_scenes_builds_resolved_doc() -> None:
    registry = TileRegistry([])
    resolved = resolve_world_scenes(WORLD_GRID_DOC, registry)
    assert resolved["name"] == "test_world"
    assert resolved["kind"] == "world"
    assert len(resolved["scenes"]) == 2
    # First cell of root scene: 'S' -> "W-full-sea"
    assert resolved["scenes"][0]["grid"][0][0]["desc"] == "W-full-sea"
    # R cell of child scene -> some road desc
    assert resolved["scenes"][1]["grid"][1][0]["char"] == "R"
    assert "road" in resolved["scenes"][1]["grid"][1][0]["desc"]
```

- [ ] **Step 2: Run the test — verify it fails**

Run: `cd /Users/lsq/env/assets/game && python3 -m pytest tests/test_world.py -v`
Expected: `ModuleNotFoundError: No module named 'pipeline.world'`

- [ ] **Step 3: Implement `pipeline/world.py`**

```python
"""Helpers for multi-scene (world) documents."""
from pipeline.resolve import generate_desc_json
from pipeline.registry import TileRegistry


def iter_scenes(grid_doc: dict):
    """Yield (scene_id, char_grid, validation_meta) for each scene."""
    for sc in grid_doc["scenes"]:
        char_grid = [[c["char"] for c in row] for row in sc["grid"]]
        yield sc["id"], char_grid, sc.get("validation", {})


def resolve_world_scenes(grid_doc: dict, registry: TileRegistry) -> dict:
    """Build resolved world doc with desc+file per cell."""
    scenes_out = []
    for sid, char_grid, _meta in iter_scenes(grid_doc):
        scenes_out.append({
            "id": sid,
            "rows": len(char_grid),
            "cols": max((len(r) for r in char_grid), default=0),
            "grid": generate_desc_json(char_grid, registry),
        })
    return {
        "name": grid_doc["name"],
        "kind": "world",
        "scenes": scenes_out,
    }
```

- [ ] **Step 4: Run the test — verify it passes**

Run: `cd /Users/lsq/env/assets/game && python3 -m pytest tests/test_world.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/world.py tests/test_world.py
git commit -m "feat(pipeline/world): iter_scenes + resolve_world_scenes"
```

---

## Task 1.7: LocalSource (TDD)

**Files:**
- Create: `pipeline/sources/__init__.py`
- Create: `pipeline/sources/local.py`
- Test: `tests/test_sources_local.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sources_local.py
import json
from pathlib import Path
import pytest
from pipeline.sources.local import LocalSource


@pytest.fixture
def game_layout(tmp_path: Path, monkeypatch) -> None:
    """Mock the game layout: tmp_path/{input, output}/."""
    (tmp_path / "input").mkdir()
    monkeypatch.chdir(tmp_path)


def test_local_source_copies_single_decl_to_output(game_layout, tmp_path) -> None:
    decl = {
        "name": "my_map", "kind": "single", "source": "local",
        "rows": 2, "cols": 2, "map": ["SS", "GG"], "meta": {}, "pois": [],
    }
    (tmp_path / "input" / "my_map_decl.json").write_text(
        json.dumps(decl, ensure_ascii=False), encoding="utf-8"
    )

    src = LocalSource()
    out = src.run(name="my_map")
    expected = tmp_path / "output" / "my_map" / "my_map_decl.json"
    assert out == expected
    assert expected.exists()
    again = json.loads(expected.read_text(encoding="utf-8"))
    assert again["name"] == "my_map"


def test_local_source_copies_world_decl(game_layout, tmp_path) -> None:
    decl = {
        "name": "my_world", "kind": "world", "source": "local",
        "scenes": [{"id": "root", "back": None, "rows": 2, "cols": 2,
                    "map": ["SS", "GG"], "title": "Root"}],
    }
    (tmp_path / "input" / "my_world_decl.json").write_text(
        json.dumps(decl, ensure_ascii=False), encoding="utf-8"
    )
    src = LocalSource()
    out = src.run(name="my_world")
    assert out.exists()
    again = json.loads(out.read_text(encoding="utf-8"))
    assert again["kind"] == "world"


def test_local_source_missing_file_raises(game_layout) -> None:
    src = LocalSource()
    with pytest.raises(FileNotFoundError):
        src.run(name="does_not_exist")
```

- [ ] **Step 2: Run the test — verify it fails**

Run: `cd /Users/lsq/env/assets/game && python3 -m pytest tests/test_sources_local.py -v`
Expected: `ModuleNotFoundError: No module named 'pipeline.sources.local'`

- [ ] **Step 3: Create `pipeline/sources/__init__.py`**

```python
# pipeline/sources/__init__.py — package marker
```

- [ ] **Step 4: Implement `pipeline/sources/local.py`**

```python
"""Local source: copy input/<name>_decl.json to output/<name>/."""
from pathlib import Path
from pipeline.decl import read_decl, write_decl


class LocalSource:
    def run(self, name: str) -> Path:
        src_path = Path("input") / f"{name}_decl.json"
        decl = read_decl(src_path)  # raises FileNotFoundError if missing
        out_path = Path("output") / name / f"{name}_decl.json"
        write_decl(decl, out_path)
        return out_path
```

- [ ] **Step 5: Run the test — verify it passes**

Run: `cd /Users/lsq/env/assets/game && python3 -m pytest tests/test_sources_local.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add pipeline/sources/__init__.py pipeline/sources/local.py tests/test_sources_local.py
git commit -m "feat(pipeline/sources/local): LocalSource copies decl to output/"
```

---

## Task 2.1: OsmSource — bbox math + geometry (TDD, no API)

**Files:**
- Create: `pipeline/sources/osm.py`
- Test: `tests/test_sources_osm.py` (bbox/rasterize only in this task)

- [ ] **Step 1: Write the failing test (bbox + rasterize helpers only)**

```python
# tests/test_sources_osm.py — bbox & rasterize tests
import math
from pipeline.sources.osm import (
    compute_bbox, real_size_km, latlon_to_xy, xy_to_latlon,
    rasterize_polygon, CANVAS_SIZE,
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
    # Bottom-right (min_lat, max_lon) -> (999, 999) approx
    x, y = latlon_to_xy(bb["min_lat"], bb["max_lon"], bb)
    assert (x, y) == (CANVAS_SIZE - 1, CANVAS_SIZE - 1)


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
```

- [ ] **Step 2: Run the test — verify it fails**

Run: `cd /Users/lsq/env/assets/game && python3 -m pytest tests/test_sources_osm.py -v`
Expected: `ModuleNotFoundError: No module named 'pipeline.sources.osm'`

- [ ] **Step 3: Implement `pipeline/sources/osm.py` (helpers + rasterize only — full source in next task)**

```python
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
```

- [ ] **Step 4: Run the test — verify it passes**

Run: `cd /Users/lsq/env/assets/game && python3 -m pytest tests/test_sources_osm.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/sources/osm.py tests/test_sources_osm.py
git commit -m "feat(pipeline/sources/osm): bbox math + rasterize helpers"
```

---

## Task 2.2: OsmSource — full source (Overpass + decl build)

**Files:**
- Modify: `pipeline/sources/osm.py` (add Overpass + build_decl + OsmSource class)
- Test: `tests/test_sources_osm.py` (add full-source test with mocked HTTP)

- [ ] **Step 1: Append tests for full OsmSource**

Append to `tests/test_sources_osm.py`:

```python
# Additional tests (append below existing imports)
import json
from unittest.mock import patch, MagicMock
from pipeline.sources.osm import (
    build_overpass_query, build_decl, OsmSource,
)


def test_build_overpass_query_includes_bbox() -> None:
    bb = compute_bbox(31.2304, 121.4737, 10.0)
    q = build_overpass_query(bb)
    assert "31.2304" in q or f"{bb['min_lat']:.4f}" in q
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
    assert decl["rows"] == 10
    assert decl["cols"] == 10
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
```

- [ ] **Step 2: Run the new tests — verify they fail**

Run: `cd /Users/lsq/env/assets/game && python3 -m pytest tests/test_sources_osm.py -v`
Expected: 3 failures (NameError on `build_overpass_query` / `build_decl` / `OsmSource`).

- [ ] **Step 3: Append the rest of `pipeline/sources/osm.py`**

Append to `pipeline/sources/osm.py`:

```python
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
```

- [ ] **Step 4: Run the tests — verify all pass**

Run: `cd /Users/lsq/env/assets/game && python3 -m pytest tests/test_sources_osm.py -v`
Expected: 8 passed (5 original + 3 new).

- [ ] **Step 5: Commit**

```bash
git add pipeline/sources/osm.py tests/test_sources_osm.py
git commit -m "feat(pipeline/sources/osm): full OsmSource (Overpass + rasterize + decl)"
```

---

## Task 2.3: get_source factory

**Files:**
- Modify: `pipeline/sources/__init__.py`
- Test: extend `tests/test_sources_local.py` (or new file)

- [ ] **Step 1: Add tests for the factory**

Create `tests/test_sources_factory.py`:

```python
# tests/test_sources_factory.py
from pipeline.sources import get_source, PRESET_CITY_KEYS
from pipeline.sources.local import LocalSource
from pipeline.sources.osm import OsmSource


def test_get_source_local() -> None:
    assert isinstance(get_source("local"), LocalSource)


def test_get_source_osm() -> None:
    assert isinstance(get_source("osm"), OsmSource)


def test_get_source_unknown_raises() -> None:
    import pytest
    with pytest.raises(ValueError):
        get_source("nope")


def test_preset_city_keys_contains_expected() -> None:
    assert "shanghai" in PRESET_CITY_KEYS
    assert "beijing" in PRESET_CITY_KEYS
    assert "tokyo" in PRESET_CITY_KEYS
```

- [ ] **Step 2: Implement `pipeline/sources/__init__.py`**

Replace the file content with:

```python
"""Source factory + preset city keys."""
from pipeline.sources.local import LocalSource
from pipeline.sources.osm import OsmSource, PRESET_CITIES

PRESET_CITY_KEYS = list(PRESET_CITIES.keys())

_SOURCES = {
    "local": LocalSource,
    "osm": OsmSource,
}


def get_source(name: str):
    if name not in _SOURCES:
        raise ValueError(
            f"unknown source '{name}', available: {list(_SOURCES)}"
        )
    return _SOURCES[name]()
```

- [ ] **Step 3: Run the test — verify it passes**

Run: `cd /Users/lsq/env/assets/game && python3 -m pytest tests/test_sources_factory.py -v`
Expected: 4 passed.

- [ ] **Step 4: Commit**

```bash
git add pipeline/sources/__init__.py tests/test_sources_factory.py
git commit -m "feat(pipeline/sources): get_source factory + PRESET_CITY_KEYS"
```

---

## Task 3.1: HTML templates (jinja2)

**Files:**
- Create: `pipeline/html/__init__.py` (package marker)
- Create: `pipeline/html/map_viewer.html.j2` (single-scene)
- Create: `pipeline/html/world_viewer.html.j2` (multi-scene)

- [ ] **Step 1: Create `pipeline/html/__init__.py`**

```python
# pipeline/html/__init__.py — package marker for jinja2 templates
```

- [ ] **Step 2: Create `pipeline/html/map_viewer.html.j2`**

> Adapted from the current `output/map_viewer.html`. Key changes: uses `<base href="/">` instead of absolute path prefix.

```html
<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<base href="/">
<title>Tile Map Viewer · {{ name }}</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#1a1a2e;color:#eee;font-family:'Courier New',monospace;
  display:flex;flex-direction:column;align-items:center;min-height:100vh;padding:20px}
h2{margin-bottom:8px}
.subtitle{color:#888;font-size:13px;margin-bottom:18px}
.toolbar{display:flex;justify-content:center;gap:12px;margin-bottom:20px;flex-wrap:wrap;align-items:center}
.toolbar button{background:#0f3460;color:#e94560;border:1px solid #e94560;padding:8px 20px;
  border-radius:8px;cursor:pointer;font-size:14px;font-weight:600;font-family:inherit;transition:all .2s}
.toolbar button:hover{background:#e94560;color:#fff}
.toolbar .default-link{background:#0f3460;color:#6a9fb5;border:1px solid #1b3a5c;padding:8px 20px;
  border-radius:8px;font-size:13px;text-decoration:none;display:inline-flex;align-items:center;transition:all .2s}
.toolbar .default-link:hover{background:#1b3a5c;color:#e94560;border-color:#e94560}
.map{display:grid;gap:1px;padding:16px;background:#16213e;border-radius:12px;
  box-shadow:0 8px 32px rgba(0,0,0,.3)}
.tile{width:48px;height:48px;position:relative;border-radius:2px;overflow:hidden}
.tile img{width:100%;height:100%;object-fit:cover;image-rendering:pixelated}
.tile .tag{position:absolute;bottom:1px;right:1px;font-size:8px;color:#fff;
  background:rgba(0,0,0,.7);padding:0 2px;border-radius:2px;pointer-events:none}
.tile .miss{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
  font-size:9px;color:#ff6b6b;text-align:center;padding:2px;line-height:1.1}
.legend{margin-top:20px;padding:16px;background:#0f3460;border-radius:8px;max-width:1000px}
.legend h3{margin-bottom:8px}
.li{display:inline-block;margin:4px 8px;font-size:13px}
.lc{display:inline-block;width:16px;height:16px;border-radius:3px;vertical-align:middle;margin-right:4px}
.stats{margin-top:20px;padding:16px;background:#0f3460;border-radius:8px;max-width:1000px;font-size:12px}
.stats div{margin:2px 0}
.empty{padding:40px;text-align:center;color:#888;line-height:1.6}
.empty code{background:#0f3460;padding:2px 6px;border-radius:3px;color:#6a9fb5}
.toast{position:fixed;bottom:30px;left:50%;transform:translateX(-50%);
  background:#16213e;color:#4ade80;border:1px solid #4ade80;
  padding:12px 24px;border-radius:10px;font-size:14px;font-weight:600;
  opacity:0;transition:opacity .3s;pointer-events:none;z-index:100}
.toast.show{opacity:1}
.toast.error{color:#ff6b6b;border-color:#ff6b6b}
</style></head><body>
<h2>🗺️ Tile Map Viewer · {{ name }}</h2>
<p class="subtitle">通过本地 server 自动加载 (推荐: <code>just view {{ name }}</code>)，或手动 Import</p>
<div class="toolbar">
  <button onclick="document.getElementById('jsonFileInput').click()">📂 Import JSON</button>
  <a class="default-link" href="{{ name }}_resolved.json" target="_blank">🔗 {{ name }}_resolved.json</a>
  <input type="file" id="jsonFileInput" accept=".json" style="display:none">
</div>
<div id="root"><div class="empty">Loading…</div></div>
<div class="legend"><h3>图例</h3>{{ legend_html | safe }}</div>
<div id="stats"></div>
<div class="toast" id="toast"></div>
<script>
const COLORS = {{ colors_js | safe }};
function showToast(msg, isError) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast show' + (isError ? ' error' : '');
  setTimeout(() => t.className = 'toast', 2200);
}
function resolveSrc(fp) {
  if (!fp) return '';
  // <base href="/"> strips the file:// origin, so the relative path is from game/.
  return fp.startsWith('/') ? fp : '/' + fp;
}
function render(grid) {
  const cols = grid[0] ? grid[0].length : 0;
  const root = document.getElementById('root');
  root.innerHTML = '';
  const map = document.createElement('div');
  map.className = 'map';
  map.style.gridTemplateColumns = 'repeat(' + cols + ', 48px)';
  const missing = {};
  let html = '';
  grid.forEach((row, r) => {
    row.forEach((cell, c) => {
      const ch = cell.char, desc = cell.desc, fp = cell.file;
      const bg = COLORS[ch] || '#333';
      if (fp) {
        html += '<div class="tile" title="' + desc + ' [' + r + ',' + c + ']">' +
                '<img src="' + resolveSrc(fp) + '">' +
                '<span class="tag">' + ch + '</span></div>';
      } else {
        missing[desc] = (missing[desc] || 0) + 1;
        html += '<div class="tile" style="background:' + bg + '" title="MISSING: ' + desc + ' [' + r + ',' + c + ']">' +
                '<span class="miss">' + desc + '</span></div>';
      }
    });
  });
  map.innerHTML = html;
  root.appendChild(map);
  const stats = document.getElementById('stats');
  const missKeys = Object.keys(missing);
  if (missKeys.length) {
    stats.className = 'stats';
    let s = '<h3>⚠️ 缺失资源</h3>';
    missKeys.sort((a, b) => missing[b] - missing[a]).forEach(k => {
      s += '<div>' + k + ' × ' + missing[k] + '</div>';
    });
    stats.innerHTML = s;
  } else {
    stats.className = ''; stats.innerHTML = '';
  }
}
document.getElementById('jsonFileInput').addEventListener('change', function(e) {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = ev => {
    try {
      const data = JSON.parse(ev.target.result);
      if (!Array.isArray(data) || !Array.isArray(data[0])) throw new Error('expected 2D array of cells');
      render(data);
      showToast('✅ Loaded ' + data.length + '×' + (data[0]||[]).length);
    } catch(err) { showToast('❌ Invalid JSON: ' + err.message, true); }
  };
  reader.readAsText(file);
});
(function autoload() {
  if (location.protocol === 'file:') {
    document.getElementById('root').innerHTML =
      '<div class="empty">⚠️ 你正在通过 <code>file://</code> 打开此页面。<br>推荐: 在 game/ 目录运行 <code>just view {{ name }}</code>，或手动 <b>📂 Import JSON</b>。</div>';
    return;
  }
  fetch('{{ name }}_resolved.json')
    .then(r => r.ok ? r.json() : Promise.reject(r.status))
    .then(data => { render(data); showToast('✅ Auto-loaded {{ name }}_resolved.json'); })
    .catch(err => {
      document.getElementById('root').innerHTML =
        '<div class="empty">未自动找到 <code>{{ name }}_resolved.json</code> (' + err + ')。<br>请使用上面 <b>📂 Import JSON</b> 手动选择。</div>';
    });
})();
</script>
</body></html>
```

- [ ] **Step 3: Create `pipeline/html/world_viewer.html.j2`**

> Adapted from the current `output/world_viewer.html` — preserves flight animation + scene passthrough. Variable: `resolved_json` (the full resolved world dict).

```html
<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<base href="/">
<title>World Map Viewer · {{ resolved.name }}</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0e27;color:#eee;font-family:'Courier New',monospace;
  display:flex;flex-direction:column;align-items:center;min-height:100vh;padding:20px;overflow:hidden}
h2{margin-bottom:4px;font-size:18px}
.subtitle{color:#888;font-size:12px;margin-bottom:14px}
.toolbar{display:flex;justify-content:center;gap:10px;margin-bottom:14px;flex-wrap:wrap;align-items:center}
.toolbar button{background:#0f3460;color:#e94560;border:1px solid #e94560;padding:7px 16px;
  border-radius:7px;cursor:pointer;font-size:13px;font-weight:600;font-family:inherit;transition:all .2s}
.toolbar button:hover{background:#e94560;color:#fff}
.toolbar .back{background:#16213e;color:#6a9fb5;border-color:#1b3a5c;display:none}
.toolbar .back:hover{background:#1b3a5c;color:#e94560;border-color:#e94560}
.toolbar .back.show{display:inline-flex;align-items:center;gap:6px}
.scene-host{position:relative;width:100%;max-width:1200px;height:600px;
  display:flex;align-items:center;justify-content:center;
  background:radial-gradient(ellipse at center, #16213e 0%, #0a0e27 100%);
  border-radius:12px;overflow:hidden;perspective:1200px}
.scene{position:absolute;display:grid;gap:1px;padding:12px;background:#16213e;
  border-radius:10px;box-shadow:0 8px 32px rgba(0,0,0,.4);
  transform-origin:center center;transition:transform .7s cubic-bezier(.4,.0,.2,1),
    opacity .7s ease}
.scene.fade-out{opacity:0;pointer-events:none}
.scene.fade-in{opacity:1;pointer-events:auto}
.scene.hidden{display:none}
.tile{width:36px;height:36px;position:relative;border-radius:2px;overflow:hidden;
  transition:width .3s,height .3s}
.tile img{width:100%;height:100%;object-fit:cover;image-rendering:pixelated}
.tile .tag{position:absolute;bottom:1px;right:1px;font-size:8px;color:#fff;
  background:rgba(0,0,0,.7);padding:0 2px;border-radius:2px;pointer-events:none}
.tile .miss{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
  font-size:9px;color:#ff6b6b;text-align:center;padding:2px;line-height:1.1}
.region{position:absolute;border:2px solid #e94560;border-radius:8px;
  background:rgba(233,69,96,.08);cursor:pointer;transition:all .25s;
  display:flex;align-items:center;justify-content:center;flex-direction:column;
  font-size:14px;font-weight:700;color:#fff;text-shadow:0 1px 4px rgba(0,0,0,.8);
  pointer-events:auto;z-index:10}
.region:hover{background:rgba(233,69,96,.25);border-color:#ffd166;color:#ffd166;
  transform:scale(1.04)}
.region .sub{font-size:10px;font-weight:400;color:#ccc;margin-top:2px;
  text-shadow:0 1px 2px rgba(0,0,0,.9);letter-spacing:.2px}
.region .pin{position:absolute;top:-14px;font-size:16px;
  filter:drop-shadow(0 1px 2px rgba(0,0,0,.8))}
.flight{position:absolute;width:42px;height:42px;pointer-events:none;z-index:50;
  opacity:0;transform-origin:center center;transition:none}
.flight.show{opacity:1}
.flight img{width:100%;height:100%;object-fit:contain;
  filter:drop-shadow(0 2px 6px rgba(0,0,0,.6))}
.legend{margin-top:14px;padding:12px;background:#0f3460;border-radius:8px;max-width:1200px}
.legend h3{margin-bottom:6px;font-size:13px}
.li{display:inline-block;margin:3px 6px;font-size:12px}
.lc{display:inline-block;width:14px;height:14px;border-radius:3px;vertical-align:middle;margin-right:3px}
.toast{position:fixed;bottom:30px;left:50%;transform:translateX(-50%);
  background:#16213e;color:#4ade80;border:1px solid #4ade80;
  padding:10px 20px;border-radius:9px;font-size:13px;font-weight:600;
  opacity:0;transition:opacity .3s;pointer-events:none;z-index:200}
.toast.show{opacity:1}
.scene-label{position:absolute;top:18px;left:50%;transform:translateX(-50%);
  background:rgba(15,52,96,.92);color:#ffd166;padding:6px 18px;border-radius:18px;
  font-size:14px;font-weight:700;letter-spacing:1px;border:1px solid #e94560;
  pointer-events:none;z-index:15;opacity:0;transition:opacity .35s}
.scene-label.show{opacity:1}
</style></head><body>
<h2>🌍 {{ resolved.name }}</h2>
<p class="subtitle">点击地图上的红色区域 → 飞入子场景 · 按 ← Back 返回</p>
<div class="toolbar">
  <button class="back" id="backBtn">← 返回世界</button>
</div>
<div class="scene-host" id="sceneHost">
  <div class="scene-label" id="sceneLabel"></div>
  <div class="flight" id="flight"><img src="kenney_pixel-shmup/Ships/ship_0001.png" alt="✈️"></div>
</div>
<div class="legend"><h3>图例</h3>{{ legend_html | safe }}</div>
<div class="toast" id="toast"></div>
<script>
const RESOLVED = {{ resolved_json | safe }};
const COLORS = {S:"#1a5276",G:"#27ae60",O:"#e67e22",R:"#2ecc71",r:"#f39c12",L:"#6a9fb5"};

const $ = (id) => document.getElementById(id);
const host = $("sceneHost");
const flight = $("flight");
const sceneLabel = $("sceneLabel");
const backBtn = $("backBtn");
const toast = $("toast");

function showToast(msg, isErr) {
  toast.textContent = msg;
  toast.className = 'toast show' + (isErr ? ' error' : '');
  setTimeout(() => toast.className = 'toast', 2200);
}

function resolveSrc(fp) {
  if (!fp) return '';
  return fp.startsWith('/') ? fp : '/' + fp;
}

const scenes = RESOLVED.scenes;
const sceneById = Object.fromEntries(scenes.map(s => [s.id, s]));

function renderSceneEl(scene) {
  const cols = scene.cols;
  const el = document.createElement('div');
  el.className = 'scene fade-in';
  el.id = 'scene-' + scene.id;
  el.style.gridTemplateColumns = 'repeat(' + cols + ', 36px)';
  let html = '';
  const missing = {};
  scene.grid.forEach((row, r) => {
    row.forEach((cell, c) => {
      const ch = cell.char, desc = cell.desc, fp = cell.file;
      const bg = COLORS[ch] || '#333';
      if (fp) {
        html += '<div class="tile" title="' + desc + ' [' + r + ',' + c + ']">' +
                '<img src="' + resolveSrc(fp) + '">' +
                '<span class="tag">' + ch + '</span></div>';
      } else {
        missing[desc] = (missing[desc] || 0) + 1;
        html += '<div class="tile" style="background:' + bg + '" title="MISSING: ' + desc + '">' +
                '<span class="miss">' + desc + '</span></div>';
      }
    });
  });
  el.innerHTML = html;
  // regions (root scene only)
  if (scene.regions) {
    scene.regions.forEach(reg => {
      const r = document.createElement('div');
      r.className = 'region';
      r.style.left = (reg.col * 37 + 12) + 'px';
      r.style.top = (reg.row * 37 + 12) + 'px';
      r.style.width = (reg.cols * 37 - 4) + 'px';
      r.style.height = (reg.rows * 37 - 4) + 'px';
      r.innerHTML = '<span class="pin">📍</span>' + reg.label +
                    (reg.subtitle ? '<span class="sub">' + reg.subtitle + '</span>' : '');
      r.onclick = () => flyTo(reg.id);
      el.appendChild(r);
    });
  }
  return el;
}

let currentScene = null;
function showScene(sid, withBack = false) {
  const scene = sceneById[sid];
  if (!scene) return;
  if (currentScene) {
    const old = document.getElementById('scene-' + currentScene);
    if (old) { old.classList.add('fade-out'); setTimeout(() => old.remove(), 700); }
  }
  const el = renderSceneEl(scene);
  host.appendChild(el);
  currentScene = sid;
  backBtn.classList.toggle('show', withBack);
  sceneLabel.textContent = scene.title || scene.id;
  sceneLabel.classList.add('show');
  setTimeout(() => sceneLabel.classList.remove('show'), 1500);
}

function flyTo(sid) {
  showScene(sid, true);
  history.pushState({scene: sid}, '', '#' + sid);
}

backBtn.onclick = () => {
  const root = scenes.find(s => s.back == null);
  if (root) { showScene(root.id, false); history.pushState({scene: root.id}, '', '#' + root.id); }
};

window.onpopstate = (e) => {
  const sid = e.state?.scene || scenes.find(s => s.back == null)?.id;
  showScene(sid, sid !== scenes.find(s => s.back == null)?.id);
};

// Init: show root scene
const initial = location.hash ? location.hash.slice(1) : scenes.find(s => s.back == null)?.id;
showScene(initial, location.hash !== '');
</script>
</body></html>
```

- [ ] **Step 4: Verify jinja2 can load the templates**

Run: `cd /Users/lsq/env/assets/game && python3 -c "from jinja2 import Environment, FileSystemLoader; env=Environment(loader=FileSystemLoader('pipeline/html')); print(env.list_templates())"`
Expected: `['map_viewer.html.j2', 'world_viewer.html.j2']`

If jinja2 is missing: `python3 -m pip install --user jinja2` (or use `.venv` if it exists).

- [ ] **Step 5: Commit**

```bash
git add pipeline/html/
git commit -m "feat(pipeline/html): jinja2 templates for map + world viewers"
```

---

## Task 3.2: render.py (TDD)

**Files:**
- Create: `pipeline/render.py`
- Test: `tests/test_render.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_render.py
import json
from pathlib import Path
from pipeline.render import generate_map_html, generate_world_html


SINGLE_RESOLVED = {
    "name": "smoke_test",
    "kind": "single",
    "rows": 2, "cols": 2,
    "grid": [
        [{"char": "S", "desc": "W-full-sea", "file": "Tiles/sea.png"},
         {"char": "G", "desc": "W-y-g-top-beach", "file": "Tiles/g.png"}],
        [{"char": "G", "desc": "G-full-land", "file": "Tiles/g.png"},
         {"char": "G", "desc": "G-full-land", "file": "Tiles/g.png"}],
    ],
}

WORLD_RESOLVED = {
    "name": "test_world",
    "kind": "world",
    "scenes": [
        {"id": "root", "title": "Root", "back": None, "rows": 2, "cols": 2,
         "grid": [
             [{"char": "S", "desc": "W-full-sea", "file": "Tiles/sea.png"},
              {"char": "G", "desc": "G-full-land", "file": "Tiles/g.png"}],
             [{"char": "G", "desc": "G-full-land", "file": "Tiles/g.png"},
              {"char": "G", "desc": "G-full-land", "file": "Tiles/g.png"}],
         ]},
    ],
}


def test_generate_map_html_writes_file(tmp_path: Path) -> None:
    out = tmp_path / "smoke_test_viewer.html"
    generate_map_html(SINGLE_RESOLVED, str(out))
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "smoke_test" in text
    assert "W-full-sea" in text or "fetch" in text  # template uses {{ name }}


def test_generate_map_html_includes_base_href(tmp_path: Path) -> None:
    out = tmp_path / "v.html"
    generate_map_html(SINGLE_RESOLVED, str(out))
    text = out.read_text(encoding="utf-8")
    assert '<base href="/">' in text


def test_generate_world_html_writes_file(tmp_path: Path) -> None:
    out = tmp_path / "world_viewer.html"
    generate_world_html(WORLD_RESOLVED, str(out))
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "test_world" in text
    assert "RESOLVED" in text


def test_generate_map_html_uses_resolved_name_for_link(tmp_path: Path) -> None:
    out = tmp_path / "v.html"
    generate_map_html(SINGLE_RESOLVED, str(out))
    text = out.read_text(encoding="utf-8")
    # Should reference the resolved JSON by its name
    assert "smoke_test_resolved.json" in text
```

- [ ] **Step 2: Run the test — verify it fails**

Run: `cd /Users/lsq/env/assets/game && python3 -m pytest tests/test_render.py -v`
Expected: `ModuleNotFoundError: No module named 'pipeline.render'`

- [ ] **Step 3: Implement `pipeline/render.py`**

```python
"""Render resolved JSON into HTML viewers using jinja2 templates."""
import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

HTML_DIR = Path(__file__).parent / "html"
COLORS = {"S": "#1a5276", "G": "#27ae60", "O": "#e67e22",
          "R": "#2ecc71", "r": "#f39c12", "L": "#6a9fb5"}
LEGEND = [
    ("S", "海"), ("G", "绿地"), ("O", "红地"),
    ("R", "绿路"), ("r", "红路"),
]


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(HTML_DIR)),
        autoescape=select_autoescape(["html"]),
    )


def _legend_html() -> str:
    return "".join(
        f'<div class="li"><span class="lc" style="background:{COLORS[ch]}"></span>{ch}={label}</div>'
        for ch, label in LEGEND
    )


def _world_legend_html() -> str:
    parts = [_legend_html(),
             '<div class="li"><span class="lc" style="background:#6a9fb5"></span>📍 城市</div>']
    return "".join(parts)


def generate_map_html(resolved: dict, output_path: str) -> None:
    env = _env()
    template = env.get_template("map_viewer.html.j2")
    html = template.render(
        name=resolved["name"],
        legend_html=_legend_html(),
        colors_js=json.dumps(COLORS),
    )
    Path(output_path).write_text(html, encoding="utf-8")


def generate_world_html(resolved: dict, output_path: str) -> None:
    env = _env()
    template = env.get_template("world_viewer.html.j2")
    html = template.render(
        resolved=resolved,
        resolved_json=json.dumps(resolved, ensure_ascii=False),
        legend_html=_world_legend_html(),
    )
    Path(output_path).write_text(html, encoding="utf-8")
```

- [ ] **Step 4: Run the test — verify it passes**

Run: `cd /Users/lsq/env/assets/game && python3 -m pytest tests/test_render.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/render.py tests/test_render.py
git commit -m "feat(pipeline/render): generate_map_html + generate_world_html"
```

---

## Task 4.1: stage1_source.py

**Files:**
- Create: `stage1_source.py`

- [ ] **Step 1: Implement `stage1_source.py`**

```python
#!/usr/bin/env python3
"""Stage 1: source -> output/<name>/<name>_decl.json

Usage:
  python3 stage1_source.py local <name>
  python3 stage1_source.py osm --city shanghai --size-km 10 [--name <output_dir>]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pipeline.sources import get_source


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage 1: source")
    sub = ap.add_subparsers(dest="source", required=True)

    p_local = sub.add_parser("local")
    p_local.add_argument("name")

    p_osm = sub.add_parser("osm")
    p_osm.add_argument("--city", required=True,
                       choices=["shanghai", "beijing", "tokyo", "paris",
                                "london", "newyork", "hangzhou", "shenzhen",
                                "guangzhou"])
    p_osm.add_argument("--size-km", type=float, default=10.0)
    p_osm.add_argument("--name", default=None,
                       help="output dir name (default: <city>_<size_km>km)")

    args = ap.parse_args()

    if args.source == "local":
        out = get_source("local").run(name=args.name)
    else:  # osm
        out = get_source("osm").run(city=args.city, size_km=args.size_km, name=args.name)
    print(f"✅ stage1 → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Make it executable and smoke-test**

```bash
chmod +x stage1_source.py
cp tests/fixtures/smoke_test_decl.json input/smoke_test_decl.json
python3 stage1_source.py local smoke_test
```

Expected: prints `✅ stage1 → output/smoke_test/smoke_test_decl.json` and that file exists.

- [ ] **Step 3: Clean up smoke test**

```bash
trash input/smoke_test_decl.json output/smoke_test/
```

- [ ] **Step 4: Commit**

```bash
git add stage1_source.py
git commit -m "feat(stage1): stage1_source CLI (local + osm subcommands)"
```

---

## Task 4.2: stage2_grid.py

**Files:**
- Create: `stage2_grid.py`

- [ ] **Step 1: Implement `stage2_grid.py`**

```python
#!/usr/bin/env python3
"""Stage 2: decl -> output/<name>/<name>_grid.json (with R1-R4 validation)."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pipeline.decl import read_decl
from pipeline.grid import parse_map
from pipeline.validate import validate_map


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage 2: grid + validate")
    ap.add_argument("name")
    args = ap.parse_args()

    out_dir = Path("output") / args.name
    decl = read_decl(out_dir / f"{args.name}_decl.json")

    if decl.get("kind", "single") == "single":
        grid = parse_map(decl["map"])
        errors = validate_map(grid)
        result = {
            "name": decl["name"],
            "kind": "single",
            "rows": len(grid),
            "cols": max((len(r) for r in grid), default=0),
            "grid": [[{"char": ch} for ch in row] for row in grid],
            "validation": {"ok": not errors, "rule_violations": errors},
        }
    else:  # world
        scenes = []
        all_ok = True
        for sc in decl["scenes"]:
            grid = parse_map(sc["map"])
            errors = validate_map(grid)
            scenes.append({
                "id": sc["id"],
                "grid": [[{"char": ch} for ch in row] for row in grid],
                "validation": {"ok": not errors, "rule_violations": errors},
            })
            all_ok = all_ok and not errors
        result = {
            "name": decl["name"],
            "kind": "world",
            "scenes": scenes,
            "validation": {"ok": all_ok},
        }

    out_path = out_dir / f"{args.name}_grid.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    if not result["validation"]["ok"]:
        n = sum(len(s.get("validation", {}).get("rule_violations", []))
                for s in result.get("scenes", [result]))
        print(f"⚠️  {n} R1-R4 violation(s) written to grid.json (non-blocking)")
    print(f"✅ stage2 → {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Smoke-test end-to-end on smoke_test**

```bash
cp tests/fixtures/smoke_test_decl.json input/smoke_test_decl.json
python3 stage1_source.py local smoke_test
python3 stage2_grid.py smoke_test
cat output/smoke_test/smoke_test_grid.json | head -30
```

Expected: grid.json is produced, has `kind: single` and `validation.ok: true`.

- [ ] **Step 3: Commit**

```bash
git add stage2_grid.py
git commit -m "feat(stage2): stage2_grid CLI (decl -> grid + validate)"
```

---

## Task 4.3: stage3_resolved.py

**Files:**
- Create: `stage3_resolved.py`

- [ ] **Step 1: Implement `stage3_resolved.py`**

```python
#!/usr/bin/env python3
"""Stage 3: grid -> output/<name>/<name>_resolved.json (desc + file per cell)."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pipeline.registry import parse_tile_registry
from pipeline.resolve import generate_desc_json
from pipeline.world import resolve_world_scenes


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage 3: resolve tiles")
    ap.add_argument("name")
    args = ap.parse_args()

    base = Path(__file__).parent
    registry = parse_tile_registry(str(base / "assets_map_check.json"))
    out_dir = Path("output") / args.name
    grid_doc = json.loads(
        (out_dir / f"{args.name}_grid.json").read_text(encoding="utf-8")
    )

    if grid_doc.get("kind", "single") == "single":
        char_grid = [[c["char"] for c in row] for row in grid_doc["grid"]]
        resolved = {
            "name": grid_doc["name"],
            "kind": "single",
            "rows": grid_doc["rows"],
            "cols": grid_doc["cols"],
            "grid": generate_desc_json(char_grid, registry),
        }
    else:
        resolved = resolve_world_scenes(grid_doc, registry)

    out_path = out_dir / f"{args.name}_resolved.json"
    out_path.write_text(json.dumps(resolved, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"✅ stage3 → {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Smoke-test**

```bash
python3 stage3_resolved.py smoke_test
head -5 output/smoke_test/smoke_test_resolved.json
```

Expected: each cell has `char`/`desc`/`file` keys.

- [ ] **Step 3: Commit**

```bash
git add stage3_resolved.py
git commit -m "feat(stage3): stage3_resolved CLI (grid -> resolved JSON)"
```

---

## Task 4.4: stage4_html.py

**Files:**
- Create: `stage4_html.py`

- [ ] **Step 1: Implement `stage4_html.py`**

```python
#!/usr/bin/env python3
"""Stage 4: resolved -> output/<name>/<name>_viewer.html or world_viewer.html."""
import argparse
import json
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pipeline.render import generate_map_html, generate_world_html

PORT = 8765


def _ensure_server() -> None:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=0.3)
        return  # already running
    except Exception:
        pass
    subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(0.5)


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage 4: render HTML")
    ap.add_argument("name")
    ap.add_argument("--serve", action="store_true",
                    help="Start http server and open browser")
    args = ap.parse_args()

    out_dir = Path("output") / args.name
    resolved = json.loads(
        (out_dir / f"{args.name}_resolved.json").read_text(encoding="utf-8")
    )

    if resolved.get("kind", "single") == "single":
        out_path = out_dir / f"{args.name}_viewer.html"
        generate_map_html(resolved, str(out_path))
    else:
        out_path = out_dir / "world_viewer.html"
        generate_world_html(resolved, str(out_path))

    print(f"✅ stage4 → {out_path}")
    if args.serve:
        _ensure_server()
        url = f"http://127.0.0.1:{PORT}/{out_path}"
        webbrowser.open(url)
        print(f"🌐 opened {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Smoke-test (no serve)**

```bash
python3 stage4_html.py smoke_test
ls output/smoke_test/*.html
```

Expected: `smoke_test_viewer.html` exists.

- [ ] **Step 3: Commit**

```bash
git add stage4_html.py
git commit -m "feat(stage4): stage4_html CLI (resolved -> viewer.html + optional serve)"
```

---

## Task 4.5: End-to-end test of all 4 stages

**Files:**
- Create: `tests/test_stages.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_stages.py — end-to-end smoke of all 4 stages on smoke_test
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

GAME_DIR = Path(__file__).resolve().parent.parent
FIXTURE = GAME_DIR / "tests" / "fixtures" / "smoke_test_decl.json"
NAME = "smoke_test_e2e"


@pytest.fixture
def stage_layout(tmp_path, monkeypatch):
    """Set up tmp input/ and output/, chdir into tmp_path, run all stages."""
    (tmp_path / "input").mkdir()
    monkeypatch.chdir(tmp_path)
    shutil.copy(FIXTURE, tmp_path / "input" / f"{NAME}_decl.json")
    yield tmp_path
    # cleanup handled by tmp_path


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GAME_DIR / "stage1_source.py"), *args],
        check=True, capture_output=True, text=True,
    )


def _stage(name: str, script: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GAME_DIR / script), name],
        check=True, capture_output=True, text=True,
    )


def test_full_pipeline_smoke(stage_layout) -> None:
    out = stage_layout
    _run(["local", NAME])
    assert (out / "output" / NAME / f"{NAME}_decl.json").exists()

    _stage(NAME, "stage2_grid.py")
    assert (out / "output" / NAME / f"{NAME}_grid.json").exists()

    _stage(NAME, "stage3_resolved.py")
    resolved = json.loads(
        (out / "output" / NAME / f"{NAME}_resolved.json").read_text(encoding="utf-8")
    )
    assert resolved["kind"] == "single"
    assert resolved["rows"] == 6
    assert all("desc" in c for row in resolved["grid"] for c in row)

    _stage(NAME, "stage4_html.py")
    assert (out / "output" / NAME / f"{NAME}_viewer.html").exists()
```

- [ ] **Step 2: Run the test — verify it passes**

Run: `cd /Users/lsq/env/assets/game && python3 -m pytest tests/test_stages.py -v`
Expected: 1 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/test_stages.py
git commit -m "test: end-to-end smoke of all 4 stages on smoke_test fixture"
```

---

## Task 5.1: Rewrite justfile

**Files:**
- Modify: `justfile` (replace all content)

- [ ] **Step 1: Replace justfile content**

```just
# Map Pipeline — 4 stages: source / grid / resolved / html
# Run `just` to list all commands.

PORT := "8765"

default:
    @just --list

# ============================================================
# Stage 1: source
# ============================================================

# local:  read input/<name>_decl.json, write output/<name>/<name>_decl.json
s1-local name:
    python3 stage1_source.py local {{name}}

# osm:    pull Overpass data, rasterize, write decl to output/<city>_<size>km/
s1-osm city size_km name="":
    @if [ -z "{{name}}" ]; then \
        python3 stage1_source.py osm --city {{city}} --size-km {{size_km}}; \
    else \
        python3 stage1_source.py osm --city {{city}} --size-km {{size_km}} --name {{name}}; \
    fi

# ============================================================
# Stage 2-4
# ============================================================

s2 name:
    python3 stage2_grid.py {{name}}

s3 name:
    python3 stage3_resolved.py {{name}}

s4 name:
    python3 stage4_html.py {{name}}

# ============================================================
# One-shot: full pipeline
# ============================================================

# build: stage1=local, then 2/3/4
build name: (s1-local name) (s2 name) (s3 name) (s4 name)

# build-osm: stage1=osm, then 2/3/4
build-osm city size_km: (s1-osm city size_km (city + '_' + size_km + 'km')) \
                        (s2 (city + '_' + size_km + 'km')) \
                        (s3 (city + '_' + size_km + 'km')) \
                        (s4 (city + '_' + size_km + 'km'))

# ============================================================
# View: serve + open
# ============================================================

serve:
    @python3 -m http.server {{PORT}} --bind 127.0.0.1

view name: (view-auto name)
view-auto name:
    @# Pick world_viewer.html vs <name>_viewer.html based on kind in grid.json
    @if [ -f output/{{name}}/{{name}}_grid.json ] && \
         python3 -c "import json,sys; d=json.load(open('output/{{name}}/{{name}}_grid.json')); sys.exit(0 if d.get('kind')=='world' else 1)"; then \
        HTML="output/{{name}}/world_viewer.html"; \
    else \
        HTML="output/{{name}}/{{name}}_viewer.html"; \
    fi
    @curl -sf -o /dev/null http://127.0.0.1:{{PORT}}/ 2>/dev/null || \
        (python3 -m http.server {{PORT}} --bind 127.0.0.1 >/dev/null 2>&1 &)
    @open "http://127.0.0.1:{{PORT}}/$HTML"

# ============================================================
# Cleanup
# ============================================================

clean:
    @trash output 2>/dev/null || rm -rf output

# ============================================================
# Tests
# ============================================================

test:
    python3 -m pytest tests/ -v

smoke:
    @just build smoke_test
    @just view smoke_test
```

- [ ] **Step 2: Run `just --list` to verify syntax**

Run: `cd /Users/lsq/env/assets/game && just --list`
Expected: lists all `s1-local`, `s1-osm`, `s2`, `s3`, `s4`, `build`, `build-osm`, `serve`, `view`, `clean`, `test`, `smoke` recipes.

- [ ] **Step 3: Run `just test` to confirm full pytest suite passes**

Run: `cd /Users/lsq/env/assets/game && just test`
Expected: all tests pass.

- [ ] **Step 4: Run `just smoke` end-to-end**

```bash
cp tests/fixtures/smoke_test_decl.json input/smoke_test_decl.json
just smoke
```

Expected: opens browser to `http://127.0.0.1:8765/output/smoke_test/smoke_test_viewer.html`.

If `just smoke` works visually (you can confirm the page loads), proceed.

- [ ] **Step 5: Commit**

```bash
git add justfile
git commit -m "feat(justfile): 4-stage pipeline commands (s1-s4, build, view, test, smoke)"
```

---

## Task 5.2: Delete old scripts and migrate output

**Files:**
- Delete: `map_builder.py`, `osm_to_map.py`, `osm_build.py`
- Delete: `__pycache__/`
- Modify: `output/` (trash — old artifacts not compatible with new layout)
- Optional: rename `input/world_decl.json` → `input/world_map.json`

- [ ] **Step 1: Trash old Python scripts**

```bash
cd /Users/lsq/env/assets/game
trash map_builder.py osm_to_map.py osm_build.py
```

- [ ] **Step 2: Trash `__pycache__` and old `output/` artifacts**

```bash
trash __pycache__ output
```

- [ ] **Step 3: Optional — rename world decl input**

```bash
[ -f input/world_decl.json ] && mv input/world_decl.json input/world_map.json
```

- [ ] **Step 4: Update world_map.json to be readable by stage1 (if renamed)**

If you renamed, ensure `input/world_map.json` has `kind: "world"` at the top level (or rely on auto-detect by presence of `scenes` key). Auto-detect already handles it.

- [ ] **Step 5: Verify the new pipeline still works after migration**

```bash
cd /Users/lsq/env/assets/game
cp tests/fixtures/smoke_test_decl.json input/smoke_test_decl.json
just smoke
```

Expected: works (new pipeline does not import from `map_builder.py`).

- [ ] **Step 6: Confirm nothing references old scripts**

```bash
grep -r "map_builder\|osm_to_map\|osm_build" --include="*.py" --include="*.just" --include="*.md" . 2>/dev/null || echo "✅ no references"
```

Expected: `✅ no references` (or only references inside `docs/superpowers/specs/` and `docs/superpowers/plans/` which is fine).

- [ ] **Step 7: Commit migration**

```bash
git add -A
git status
git commit -m "chore: delete old map_builder.py / osm_to_map.py / osm_build.py + migrate output"
```

---

## Task 5.3: Verify all tests pass + final smoke

**Files:** (none — verification task)

- [ ] **Step 1: Run full test suite**

```bash
cd /Users/lsq/env/assets/game
just test
```

Expected: all tests pass (count: registry 6 + grid 4 + validate 7 + resolve 12 + decl 6 + world 2 + sources_local 3 + sources_osm 8 + sources_factory 4 + render 4 + stages 1 = **57 tests**).

- [ ] **Step 2: Run smoke end-to-end**

```bash
cd /Users/lsq/env/assets/game
cp tests/fixtures/smoke_test_decl.json input/smoke_test_decl.json
just smoke
```

Expected: opens browser; viewer shows 6×6 grid with sea border + green square + red road cross.

- [ ] **Step 3: Verify all 4 stages produce expected files**

```bash
cd /Users/lsq/env/assets/game
ls -la output/smoke_test/
```

Expected: 4 files present —
- `smoke_test_decl.json`
- `smoke_test_grid.json`
- `smoke_test_resolved.json`
- `smoke_test_viewer.html`

- [ ] **Step 4: Clean up smoke artifacts**

```bash
trash input/smoke_test_decl.json output/smoke_test
```

- [ ] **Step 5: Final commit if anything new appeared**

```bash
git status
# If clean, no commit needed.
```

---

## Spec Coverage Check

| Spec section | Implemented in tasks |
|--------------|----------------------|
| §2 #1 完全替换 | Task 5.2 |
| §2 #2 仅 OSM API | Task 2.1, 2.2 |
| §2 #3 stage 划分 source→grid→resolved→html | Task 4.1-4.4 |
| §2 #4 保留两份 HTML | Task 3.1, 3.2, 4.4 |
| §2 #5 4 个独立脚本 | Task 4.1, 4.2, 4.3, 4.4 |
| §2 #6 产物统一 output/<name>/ | Task 1.5, 1.7, 2.2, 4.2, 4.3 |
| §3.1 数据流图 | Tasks 1.1-5.3 (sequential stages) |
| §3.2 <base href="/"> 加载 | Task 3.1 (templates), Task 3.2 (render) |
| §4.1 11 个 pipeline 子模块 | Tasks 1.1-1.7, 2.1-2.3, 3.1, 3.2 |
| §4.2 4 个 stage 脚本 | Tasks 4.1-4.4 |
| §5 decl schema | Task 1.5, 1.7, 2.2 |
| §5 grid schema | Task 4.2 |
| §5 resolved schema | Task 1.4, 1.7, 4.3 |
| §6 错误处理 | Task 1.3 (validate), Task 1.5 (read_decl), Task 4.2 (validation.ok) |
| §7 测试 | Tasks 1.1-5.3 (every module has TDD) |
| §8 justfile | Task 5.1 |
| §9 迁移清单 | Task 5.2 |
| §11 验收 | Task 5.3 (verification step) |

No gaps detected.
