from routers.developer_texts import router
from services.text_markup import process_text_markup


def test_developer_text_router_registers_editor_handlers():
    assert len(router.message.handlers) == 4
    assert len(router.callback_query.handlers) == 3


def test_developer_markup_conversion_keeps_supported_formatting():
    value = process_text_markup("**عريض** و *مائل* و `كود`")

    assert value == "<b>عريض</b> و <i>مائل</i> و <code>كود</code>"
