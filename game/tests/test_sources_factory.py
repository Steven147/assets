# tests/test_sources_factory.py
import pytest
from pipeline.sources import get_source, PRESET_CITY_KEYS
from pipeline.sources.local import LocalSource
from pipeline.sources.osm import OsmSource


def test_get_source_local() -> None:
    assert isinstance(get_source("local"), LocalSource)


def test_get_source_osm() -> None:
    assert isinstance(get_source("osm"), OsmSource)


def test_get_source_unknown_raises() -> None:
    with pytest.raises(ValueError):
        get_source("nope")


def test_preset_city_keys_contains_expected() -> None:
    assert "shanghai" in PRESET_CITY_KEYS
    assert "beijing" in PRESET_CITY_KEYS
    assert "tokyo" in PRESET_CITY_KEYS
