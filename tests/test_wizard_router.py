from routers.wizard import WizardHooks, WizardRuntime, create_wizard_router
from services.ephemeral import EphemeralMessenger
from services.vinyl_settings import VinylSettings
from services.wizard_preview import WizardPreviewService


async def _async_noop(*args, **kwargs):
    return None


def _noop(*args, **kwargs):
    return None


def _runtime():
    pending_audio = {}
    vinyl_settings = VinylSettings()
    ephemeral = EphemeralMessenger(pending_audio)
    preview_service = WizardPreviewService(
        vinyl_settings=vinyl_settings,
        download_with_retries=_async_noop,
        temp_path=lambda name: name,
        cleanup=_noop,
    )
    hooks = WizardHooks(
        resolve_callback_uid=_async_noop,
        get_pending_audio=_noop,
        reply_text_variable=_async_noop,
        launch_job=_async_noop,
        channel_ctx=lambda uid: (None, None),
        user_has_premium_access=lambda uid: False,
    )
    return WizardRuntime(
        pending_audio=pending_audio,
        vinyl_settings=vinyl_settings,
        ephemeral=ephemeral,
        preview_service=preview_service,
        hooks=hooks,
        valid_vinyl_colors=frozenset(),
        ttl_seconds=600,
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
