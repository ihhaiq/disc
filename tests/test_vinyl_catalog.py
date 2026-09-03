import texts as texts_module
from locales.en import TEXTS_EN
from vinyl_catalog import (
    VINYL_STYLES,
    get_vinyl_style,
    get_vinyl_style_rows,
    validate_assets,
)


def test_catalog_has_unique_keys_and_existing_assets():
    keys = [style.key for style in VINYL_STYLES]

    assert len(keys) == len(set(keys))
    assert validate_assets() == []


def test_catalog_defaults_and_keeps_template_override():
    assert get_vinyl_style("unknown").key == "default"
    assert get_vinyl_style("KISS").hole_ratio_override == 0.39


def test_catalog_button_rows_cover_every_style_once():
    rows = get_vinyl_style_rows()
    flattened = [style.key for row in rows for style in row]
    keys = [style.key for style in VINYL_STYLES]

    assert sorted(flattened) == sorted(keys)
    assert len(flattened) == len(keys)
    assert all(style.button_row >= 0 for style in VINYL_STYLES)


def test_every_vinyl_style_has_arabic_and_english_button_text():
    for style in VINYL_STYLES:
        assert isinstance(getattr(texts_module, style.text_key, None), str)
        assert isinstance(TEXTS_EN.get(style.text_key), str)
