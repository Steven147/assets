"""Pytest config: ensure game/ and tests/fixtures/ are importable."""
import sys
from pathlib import Path

GAME_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GAME_DIR))
sys.path.insert(0, str(GAME_DIR / "tests"))
