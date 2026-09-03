from routers.payments import create_payment_router


async def _reply_text_variable(*args, **kwargs):
    return None


def test_payment_router_registers_each_payment_update_type_once():
    router = create_payment_router(_reply_text_variable)

    assert len(router.callback_query.handlers) == 1
    assert len(router.pre_checkout_query.handlers) == 1
    assert len(router.message.handlers) == 1
