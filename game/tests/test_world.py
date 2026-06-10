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
    resolved, code_to_tile = resolve_world_scenes(WORLD_GRID_DOC, registry)
    assert resolved["name"] == "test_world"
    assert resolved["kind"] == "world"
    assert len(resolved["scenes"]) == 2
    # Each scene's grid is now a "map" field: list of single-char strings
    root_map = resolved["scenes"][0]["map"]
    assert isinstance(root_map, list)
    assert all(isinstance(row, str) for row in root_map)
    assert all(len(ch) == 1 for row in root_map for ch in row)
    # First cell of root scene: 'S' -> code that maps to "W-full-sea"
    code = root_map[0][0]
    assert code_to_tile[code]["desc"] == "W-full-sea"
    # R cell of child scene -> a code whose desc contains "road"
    child_map = resolved["scenes"][1]["map"]
    # R is at (1,0) in child grid, r is at (1,1)
    r_code = child_map[1][0]
    assert "road" in code_to_tile[r_code]["desc"], (
        f"Expected road in desc at child[1][0], got {code_to_tile[r_code]['desc']}"
    )


def test_resolve_world_scenes_registry_is_shared_across_scenes() -> None:
    """All scenes in a world share one registry (union of all descs)."""
    registry = TileRegistry([])
    resolved, code_to_tile = resolve_world_scenes(WORLD_GRID_DOC, registry)
    # The union of descs across all scenes must be in code_to_tile.
    all_codes_used: set[str] = set()
    for scene in resolved["scenes"]:
        for row in scene["map"]:
            all_codes_used.update(row)
    assert all_codes_used.issubset(set(code_to_tile.keys()))
