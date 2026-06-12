from pipeline.editor.city_presets import get_preset, list_presets, CITY_PRESETS


def test_known_city_returns_preset():
    p = get_preset("shanghai")
    assert p["name"] == "shanghai"
    assert 30 < p["center_lat"] < 32
    assert 120 < p["center_lng"] < 122
    assert p["span_km"] > 0


def test_unknown_city_raises_keyerror():
    import pytest
    with pytest.raises(KeyError):
        get_preset("atlantis")


def test_list_presets_contains_known():
    names = list_presets()
    assert "shanghai" in names
    assert "syracuse" in names
    assert len(names) >= 5
