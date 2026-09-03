import keyboard as keyboards
from vinyl_catalog import VINYL_STYLES


def _callbacks(markup, prefix: str) -> set[str]:
    return {
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data and button.callback_data.startswith(prefix)
    }


def test_main_vinyl_keyboard_contains_every_catalog_style():
    markup = keyboards.build_vinyl_color_keyboard(has_premium=True)

    assert _callbacks(markup, "vinyl:") == {
        f"vinyl:{style.key}" for style in VINYL_STYLES
    }


def test_wizard_vinyl_keyboard_contains_every_catalog_style():
    markup = keyboards.build_wiz_color_keyboard(has_premium=True)

    assert _callbacks(markup, "wiz_color:") == {
        f"wiz_color:{style.key}" for style in VINYL_STYLES
    }


def test_developer_keyboard_contains_every_catalog_style():
    markup = keyboards.build_dev_keyboard()

    assert _callbacks(markup, "vinyl:") == {
        f"vinyl:{style.key}" for style in VINYL_STYLES
    }


def test_custom_emoji_ids_come_from_catalog():
    markup = keyboards.build_vinyl_color_keyboard(has_premium=True)
    buttons = {
        button.callback_data: button
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data and button.callback_data.startswith("vinyl:")
    }

    for style in VINYL_STYLES:
        assert buttons[f"vinyl:{style.key}"].icon_custom_emoji_id == style.icon_custom_emoji_id
