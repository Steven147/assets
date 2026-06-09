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
    assert out.name == expected.name
    assert out.parts[-2:] == expected.parts[-2:]
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
