"""Source factory + preset city keys."""
from pipeline.sources.local import LocalSource
from pipeline.sources.osm import OsmSource, PRESET_CITIES

PRESET_CITY_KEYS = list(PRESET_CITIES.keys())

_SOURCES = {
    "local": LocalSource,
    "osm": OsmSource,
}


def get_source(name: str):
    if name not in _SOURCES:
        raise ValueError(
            f"unknown source '{name}', available: {list(_SOURCES)}"
        )
    return _SOURCES[name]()
