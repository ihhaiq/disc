from services.premium_emoji import (
    build_premium_entities_from_text,
    clean_premium_emoji_tags,
    validate_premium_emoji_syntax,
)


def test_premium_emoji_entity_uses_utf16_offsets():
    text = 'A😀<tg-emoji emoji-id="123">🎶</tg-emoji>'
    entities = build_premium_entities_from_text(text)

    assert clean_premium_emoji_tags(text) == "A😀🎶"
    assert entities is not None
    assert entities[0].offset == 3
    assert entities[0].length == 2
    assert entities[0].custom_emoji_id == "123"


def test_premium_emoji_validation_rejects_invalid_ids():
    valid, error = validate_premium_emoji_syntax('<tg-emoji emoji-id="wrong">🎶</tg-emoji>')

    assert not valid
    assert "أرقام" in error
