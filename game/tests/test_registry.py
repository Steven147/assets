# tests/test_registry.py
import json
from pathlib import Path
import pytest
from pipeline.registry import parse_tile_registry, TileRegistry


def write_fixture(tmp_path: Path) -> Path:
    data = [
     {"file": "Tiles/a.png", "description": "W-full-sea"},
     {"file": "Tiles/b.png", "description": "w-y-g"}, # lowercase variant
     {"file": "Tiles/c.png", "description": ""}, # skipped
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
    # Empty description was item index2; should be skipped, not registered as "".
    assert reg.get("") == ""
