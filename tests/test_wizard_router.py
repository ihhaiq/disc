from routers.wizard import WizardRuntime, create_wizard_router


async def _async_noop(*args, **kwargs):
    return None


def _noop(*args, **kwargs):
    return None


def _runtime():
    return WizardRuntime(
        pending_audio={},
        user_rotation_seconds={},
        developer_vinyl_choice={},
        valid_vinyl_colors=frozenset(),
        ttl_seconds=600,
        resolve_callback_uid=_async_noop,
        get_pending_audio=_noop,
        edit_wizard_text=_async_noop,
        edit_wizard_text_variable=_async_noop,
        reply_text_variable=_async_noop,
        launch_job=_async_noop,
        channel_ctx=lambda uid: (None, None),
        ephemeral_id=_noop,
        user_has_premium_access=lambda uid: False,
        download_with_retries=_async_noop,
        temp_path=lambda name: name,
        cleanup=_noop,
        get_vinyl_path=_noop,
        get_shadow_path=_noop,
        get_hole_ratio=_noop,
        get_rotation_seconds=_noop,
    )


def test_wizard_router_registers_callbacks():
    router = create_wizard_router(_runtime())
    assert len(router.callback_query.handlers) == 7


def test_wizard_runtime_owns_and_cleans_state():
    runtime = _runtime()
    runtime.state[1] = {}
    runtime.pending_confirm[1] = {"confirm_expires_at": 0}

    assert runtime.has_active(1)
    assert runtime.cleanup_orphaned() == 1
    assert runtime.cleanup_expired_confirm() == 1
    assert not runtime.has_active(1)
    assert runtime.pending_confirm == {}
