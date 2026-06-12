"""City presets: name -> center_lat, center_lng, span_km."""

CITY_PRESETS = {
    "shanghai": {
        "center_lat": 31.2304,
        "center_lng": 121.4737,
        "span_km": 50,
    },
    "beijing": {
        "center_lat": 39.9042,
        "center_lng": 116.4074,
        "span_km": 50,
    },
    "hangzhou": {
        "center_lat": 30.2741,
        "center_lng": 120.1551,
        "span_km": 40,
    },
    "syracuse": {
        "center_lat": 43.0481,
        "center_lng": -76.1474,
        "span_km": 25,
    },
    "tokyo": {
        "center_lat": 35.6762,
        "center_lng": 139.6503,
        "span_km": 40,
    },
}


def get_preset(name: str) -> dict:
    if name not in CITY_PRESETS:
        raise KeyError(f"unknown city preset: {name}")
    p = dict(CITY_PRESETS[name])
    p["name"] = name
    return p


def list_presets() -> list[str]:
    return list(CITY_PRESETS.keys())
