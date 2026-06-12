from pipeline.editor.tile_paths_gen import generate_tile_paths
from pathlib import Path


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


def test_paths_actually_exist():
    paths = generate_tile_paths()
    base = Path(__file__).resolve().parent.parent.parent
    # Just verify at least one path resolves to an existing file
    some_path = next(iter(paths.values()))
    full = base / some_path
    assert full.exists(), f"missing: {full}"
