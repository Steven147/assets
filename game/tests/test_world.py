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
