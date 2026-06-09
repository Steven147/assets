# tests/test_stages.py — end-to-end smoke of all 4 stages on smoke_test
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

GAME_DIR = Path(__file__).resolve().parent.parent
FIXTURE = GAME_DIR / "tests" / "fixtures" / "smoke_test_decl.json"
NAME = "smoke_test_e2e"


@pytest.fixture
def stage_layout(tmp_path, monkeypatch):
    """Set up tmp input/ and output/, chdir into tmp_path, run all stages."""
    (tmp_path / "input").mkdir()
    monkeypatch.chdir(tmp_path)
    shutil.copy(FIXTURE, tmp_path / "input" / f"{NAME}_decl.json")
    yield tmp_path
    # cleanup handled by tmp_path


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GAME_DIR / "stage1_source.py"), *args],
        check=True, capture_output=True, text=True,
    )


def _stage(name: str, script: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GAME_DIR / script), name],
        check=True, capture_output=True, text=True,
    )


def test_full_pipeline_smoke(stage_layout) -> None:
    out = stage_layout
    _run(["local", NAME])
    assert (out / "output" / NAME / f"{NAME}_decl.json").exists()

    _stage(NAME, "stage2_grid.py")
    assert (out / "output" / NAME / f"{NAME}_grid.json").exists()

    _stage(NAME, "stage3_resolved.py")
    resolved = json.loads(
        (out / "output" / NAME / f"{NAME}_resolved.json").read_text(encoding="utf-8")
    )
    assert resolved["kind"] == "single"
    assert resolved["rows"] == 6
    assert all("desc" in c for row in resolved["grid"] for c in row)

    _stage(NAME, "stage4_html.py")
    assert (out / "output" / NAME / f"{NAME}_viewer.html").exists()
