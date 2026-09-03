from routers.developer import build_dev_keyboard, router


def test_developer_router_registers_access_handlers():
    assert len(router.message.handlers) == 2
    assert len(router.callback_query.handlers) == 8


def test_developer_keyboard_contains_each_management_entry():
    callbacks = {
        button.callback_data
        for row in build_dev_keyboard().inline_keyboard
        for button in row
        if button.callback_data
    }

    assert "dev_text:page:ar:0" in callbacks
    assert "dev_text:page:en:0" in callbacks
    assert "dev_whitelist:open" in callbacks
    assert "dev_limits:open" in callbacks
