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
    assert "fetch" in text  # template uses {{ name }}


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
