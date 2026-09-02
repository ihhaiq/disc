from types import SimpleNamespace

from rich_content import extract_rich_content, normalize_blocks_for_input


class Block:
    def model_dump(self, *, exclude_none):
        assert exclude_none
        return {"photo": {"file_id": "photo-id"}}


def test_extracts_and_normalizes_rich_blocks():
    message = SimpleNamespace(
        rich_message=SimpleNamespace(html=None, blocks=[Block()]),
        html_text=None,
        text=None,
        caption=None,
    )

    assert extract_rich_content(message) == (None, [{"photo": {"media": "photo-id"}}])


def test_plain_text_is_escaped_for_rich_html():
    message = SimpleNamespace(rich_message=None, html_text=None, text="A < B & C", caption=None)

    assert extract_rich_content(message) == ("A &lt; B &amp; C", None)


def test_normalizer_preserves_existing_media_value():
    value = {"document": {"media": "existing"}}

    assert normalize_blocks_for_input(value) == value
