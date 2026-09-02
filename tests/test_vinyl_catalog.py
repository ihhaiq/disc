from vinyl_catalog import VINYL_STYLES, get_vinyl_style, validate_assets


def test_catalog_has_unique_keys_and_existing_assets():
    keys = [style.key for style in VINYL_STYLES]

    assert len(keys) == len(set(keys))
    assert validate_assets() == []


def test_catalog_defaults_and_keeps_template_override():
    assert get_vinyl_style("unknown").key == "default"
    assert get_vinyl_style("KISS").hole_ratio_override == 0.39
