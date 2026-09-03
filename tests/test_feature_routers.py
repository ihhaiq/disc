from routers.language import create_language_router
from routers.start import create_start_router


async def _message_sender(*args, **kwargs):
    return None


def _keyboard(*args, **kwargs):
    return None


def test_language_router_registers_one_callback_handler():
    router = create_language_router(
        _message_sender,
        _keyboard,
        _keyboard,
        _keyboard,
    )

    assert len(router.callback_query.handlers) == 1


def test_start_router_registers_entry_and_input_handlers():
    router = create_start_router(_message_sender, _keyboard)

    assert len(router.message.handlers) == 2
