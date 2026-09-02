from string import Formatter
import texts

USER_TEXT_PREFIXES = ("BTN_", "MSG_", "SPEED_", "STAGE_")


def _fields(value: str) -> set[str]:
    return {name for _, name, _, _ in Formatter().parse(value) if name}


def test_english_catalog_covers_all_user_facing_texts():
    base = {
        name: value
        for name, value in vars(texts).items()
        if name.startswith(USER_TEXT_PREFIXES) and isinstance(value, str)
    }

    assert set(base) - set(texts.TEXTS_EN) == set()


def test_translation_placeholders_match_arabic_source():
    for name, translated in texts.TEXTS_EN.items():
        source = getattr(texts, name, None)
        if isinstance(source, str):
            assert _fields(translated) == _fields(source), name
