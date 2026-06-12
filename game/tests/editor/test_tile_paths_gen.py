from pathlib import Path

from pipeline.editor.tile_paths_gen import (
    DESC_TO_TILE,
    generate_tile_paths,
)
from pipeline.resolve import resolve_tile


# ---------------------------------------------------------------------------
# Existing smoke tests
# ---------------------------------------------------------------------------


def test_generate_tile_paths_returns_dict():
    paths = generate_tile_paths()
    assert isinstance(paths, dict)
    assert len(paths) > 50
    for desc, p in paths.items():
        assert p.startswith("kenney_pixel-shmup/Tiles/"), f"{desc} -> {p}"


def test_known_descs_present():
    paths = generate_tile_paths()
    assert "G-full-land" in paths
    assert "W-full-sea" in paths
    assert "G-o-bottom-road" in paths
    assert "W-y-g-top-beach" in paths


# ---------------------------------------------------------------------------
# Issue 1: every entry's referenced file must exist on disk.
# ---------------------------------------------------------------------------


def test_paths_actually_exist():
    """Every desc->path entry must resolve to a real PNG file."""
    paths = generate_tile_paths()
    base = Path(__file__).resolve().parent.parent.parent
    missing = []
    for desc, rel in paths.items():
        full = base / rel
        if not full.exists():
            missing.append((desc, str(full)))
    assert not missing, f"missing tile files: {missing}"


# ---------------------------------------------------------------------------
# Issue 2: DESC_TO_TILE must cover every desc that resolve_tile can produce.
#
# Strategy: build a small grid where the center cell is the char of interest
# and the surrounding 8 cells are flipped between sea and land, then call
# resolve_tile on the center. We enumerate every reachable combination so that
# any future change to resolve.py that introduces a new desc causes this test
# to fail.
# ---------------------------------------------------------------------------


def _beach_canonical_descs() -> set[str]:
    """Enumerate every desc the _beach path of resolve_tile can produce.

    For a beach-producing char (G or O), the desc depends on which of the 8
    surrounding cells are sea.  There are 2^8 = 256 combinations, but the
    function only cares about cardinal-vs-sea and diagonal-vs-sea for the
    no-cardinal-sea case. We brute-force the full 256-pattern space to be
    safe; resolve_tile is fast and 512 calls (256 x 2 chars) is trivial.
    """
    descs: set[str] = set()
    chars = ["G", "O"]
    sea = "S"
    land = "G"  # any non-sea, non-road char works; use 'G'.
    for ch in chars:
        # Map bit index -> which 3x3 position it controls.
        # Bit layout: nw=0, n=1, ne=2, w=3, center=4, e=5, sw=6, s=7, se=8
        # Center bit (4) is always 0 (we set it to `ch`).
        for mask in range(256):
            bits = [(mask >> b) & 1 for b in range(9)]
            row = []
            for idx, b in enumerate(bits):
                if idx == 4:
                    row.append(ch)
                else:
                    row.append(sea if b else land)
            grid = [row[0:3], row[3:6], row[6:9]]
            descs.add(resolve_tile(grid, 1, 1))
    return descs


def _road_canonical_descs() -> set[str]:
    """Enumerate every desc the _road path of resolve_tile can produce.

    Roads only look at the 4 cardinal neighbors (which must be the same road
    char to count as connected). We enumerate 2^4 = 16 neighbor patterns
    plus the case of zero neighbors (still produces 'full-road' per the
    implementation).
    """
    descs: set[str] = set()
    for ch in ["R", "r"]:
        for mask in range(16):
            n_bit = (mask >> 0) & 1
            e_bit = (mask >> 1) & 1
            s_bit = (mask >> 2) & 1
            w_bit = (mask >> 3) & 1
            # Build a 3x3 grid where the center is `ch` and cardinal
            # neighbors are set to `ch` (road) or to a non-road land char
            # otherwise. The four corner cells are land; they only matter
            # for out-of-bounds safety in other code paths.
            other = "G"  # any non-road, non-sea char
            grid = [
                [other, ch if n_bit else other, other],
                [ch if w_bit else other, ch, ch if e_bit else other],
                [other, ch if s_bit else other, other],
            ]
            descs.add(resolve_tile(grid, 1, 1))
    return descs


def _trivial_canonical_descs() -> set[str]:
    """Descs produced for chars that ignore all neighbors."""
    return {
        resolve_tile([["S"]], 0, 0),          # any grid; S -> W-full-sea
        resolve_tile([["L"]], 0, 0),          # L -> location
    }


def test_desc_to_tile_covers_resolver_output():
    """DESC_TO_TILE must contain every desc resolve_tile can produce.

    Acts as a guard against silent regressions: if resolve.py gains a new
    desc string (e.g. a new road variant), this test fails until a tile is
    mapped for it.
    """
    canonical = (
        _trivial_canonical_descs()
        | _road_canonical_descs()
        | _beach_canonical_descs()
    )
    missing = canonical - set(DESC_TO_TILE.keys())
    assert not missing, (
        f"resolve_tile can produce these descs that DESC_TO_TILE "
        f"does not cover: {sorted(missing)}"
    )


def test_resolver_canonical_set_is_nontrivial():
    """Sanity check: enumeration should cover many descs (currently ~62)."""
    canonical = (
        _trivial_canonical_descs()
        | _road_canonical_descs()
        | _beach_canonical_descs()
    )
    # Current production set is 62 unique descs; require a healthy lower
    # bound so the test fails loudly if enumeration logic regresses.
    assert len(canonical) >= 50, (
        f"expected resolver to produce >= 50 descs, got {len(canonical)}"
    )
