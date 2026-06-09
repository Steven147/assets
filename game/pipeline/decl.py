"""Decl JSON: unified schema for source output (single or world)."""
import json
from pathlib import Path


def write_decl(decl: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(decl, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def read_decl(path: Path) -> dict:
    if not Path(path).exists():
        raise FileNotFoundError(f"decl not found: {path}")
    return json.loads(Path(path).read_text(encoding="utf-8"))


# Module-level helper for tests + sources/local.py
def _detect_kind(decl: dict) -> str:
    if "scenes" in decl:
        return "world"
    return decl.get("kind", "single")


read_decl._detect_kind = _detect_kind  # attach for testability
