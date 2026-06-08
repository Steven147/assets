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
