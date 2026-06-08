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
