import json

import pytest
from pipeline.editor.editor_server import parse_args


def test_parse_args_defaults():
    args = parse_args([])
    assert args.name == ""
    assert args.city == ""
    assert args.rows == 60
    assert args.cols == 80
    assert args.span_km is None  # only set if city preset used


def test_parse_args_with_name():
    args = parse_args(["--name", "shanghai_50km"])
    assert args.name == "shanghai_50km"


def test_parse_args_with_city():
    args = parse_args(["--name", "foo", "--city", "shanghai", "--rows", "40", "--cols", "60"])
    assert args.name == "foo"
    assert args.city == "shanghai"
    assert args.rows == 40
    assert args.cols == 60


def test_resolve_meta_with_city():
    from pipeline.editor.editor_server import resolve_meta
    meta = resolve_meta(name="foo", city="shanghai", rows=40, cols=60)
    assert meta["name"] == "foo"
    assert meta["rows"] == 40
    assert meta["cols"] == 60
    assert 30 < meta["center_lat"] < 32


def test_resolve_meta_without_city_uses_zero():
    from pipeline.editor.editor_server import resolve_meta
    meta = resolve_meta(name="foo", city="", rows=40, cols=60)
    assert meta["center_lat"] == 0.0
    assert meta["center_lng"] == 0.0
    assert meta["span_km"] == 10  # default


def test_resolve_meta_unknown_city_warns(capsys):
    from pipeline.editor.editor_server import resolve_meta
    meta = resolve_meta(name="foo", city="atlantis", rows=40, cols=60)
    captured = capsys.readouterr()
    assert "unknown city" in captured.out.lower() or meta["center_lat"] == 0.0


def test_write_meta_creates_file(tmp_path):
    from pipeline.editor.editor_server import write_meta
    meta = {"name": "foo", "center_lat": 1.0, "center_lng": 2.0, "span_km": 10, "rows": 60, "cols": 80}
    out = tmp_path / "meta.json"
    write_meta(meta, out)
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["name"] == "foo"


def test_write_tile_paths_creates_file(tmp_path):
    from pipeline.editor.editor_server import write_tile_paths_to
    out = tmp_path / "tile_paths.js"
    write_tile_paths_to(out)
    assert out.exists()
    text = out.read_text()
    assert "window.TILE_PATHS" in text
    assert "G-full-land" in text
