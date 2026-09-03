from services.messaging import format_rich_value, normalize_rich_blocks_for_input


def test_rich_photo_uses_largest_available_size():
    blocks = [
        {
            "photo": [
                {"file_id": "small", "width": 100, "height": 100},
                {"file_id": "large", "width": 500, "height": 500},
            ]
        }
    ]

    assert normalize_rich_blocks_for_input(blocks) == [{"photo": {"media": "large"}}]


def test_rich_placeholders_are_formatted_recursively():
    value = {"blocks": [{"text": "Welcome {name}"}], "count": 1}

    assert format_rich_value(value, name="Hussein") == {
        "blocks": [{"text": "Welcome Hussein"}],
        "count": 1,
    }
