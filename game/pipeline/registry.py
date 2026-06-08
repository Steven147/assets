"""Tile registry: maps tile description -> file path (case-insensitive)."""
import json
from pathlib import Path


class TileRegistry:
    def __init__(self, items: list) -> None:
        self._lower_to_file: dict[str, str] = {}
        self._lower_to_orig: dict[str, str] = {}
        for it in items:
            desc = (it.get("description") or "").strip()
            if not desc:
                continue
            key = desc.lower()
            if key not in self._lower_to_file:
                self._lower_to_file[key] = it["file"]
                self._lower_to_orig[key] = desc

    def get(self, desc: str, default: str = "") -> str:
        return self._lower_to_file.get(desc.lower(), default)

    def __contains__(self, desc: str) -> bool:
        return desc.lower() in self._lower_to_file


def parse_tile_registry(json_path: str) -> TileRegistry:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return TileRegistry(data)
