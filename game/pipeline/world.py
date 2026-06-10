"""Helpers for multi-scene (world) documents."""
from pipeline.resolve import build_compact_grid, CODE_CHARS
from pipeline.registry import TileRegistry


def iter_scenes(grid_doc: dict):
    """Yield (scene_id, char_grid, validation_meta) for each scene."""
    for sc in grid_doc["scenes"]:
        char_grid = [[c["char"] for c in row] for row in sc["grid"]]
        yield sc["id"], char_grid, sc.get("validation", {})


def resolve_world_scenes(grid_doc: dict, registry: TileRegistry) -> tuple[dict, dict]:
    """Resolve every scene in a world to a compact char-grid map.

    Returns ``(resolved_doc, code_to_tile)`` where ``resolved_doc`` has
    ``scenes[i].map`` (a list of strings, one per row) and ``code_to_tile``
    is the global code→{desc,file} table covering all descs across all scenes.

    Because different scenes may share the same descs, we first resolve each
    scene independently via ``build_compact_grid``, then re-encode everything
    into one globally consistent code table.
    """
    # 1. Resolve each scene independently to get per-scene desc→code mappings.
    per_scene: list[tuple[str, list[str], dict]] = []  # (sid, encoded, local code_to_tile)
    for sid, char_grid, _meta in iter_scenes(grid_doc):
        code_to_tile, encoded = build_compact_grid(char_grid, registry)
        per_scene.append((sid, encoded, code_to_tile))

    # 2. Collect all unique descs across scenes, sorted → global code assignment.
    all_descs = sorted({
        tile["desc"]
        for _, _, code_to_tile in per_scene
        for tile in code_to_tile.values()
    })
    global_code_to_tile: dict[str, dict] = {
        CODE_CHARS[i]: {"desc": d, "file": registry.get(d, "")}
        for i, d in enumerate(all_descs)
    }
    desc_to_global_code = {tile["desc"]: code for code, tile in global_code_to_tile.items()}

    # 3. Re-encode each scene's map using the global codes.
    scenes_out = []
    for sid, encoded, local_code_to_tile in per_scene:
        # Build local code → global code translation
        local_to_global = {}
        for local_code, tile in local_code_to_tile.items():
            local_to_global[local_code] = desc_to_global_code[tile["desc"]]
        # Re-encode: translate each char in each row
        re_encoded = [
            "".join(local_to_global[ch] for ch in row)
            for row in encoded
        ]
        scenes_out.append({
            "id": sid,
            "rows": len(re_encoded),
            "cols": max((len(r) for r in re_encoded), default=0),
            "map": re_encoded,
        })

    resolved = {
        "name": grid_doc["name"],
        "kind": "world",
        "scenes": scenes_out,
    }
    return resolved, global_code_to_tile
