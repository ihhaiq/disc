import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message

import config
import keyboard as keyboards
import limits
import texts as texts_module
from services.contexts import is_channel_context, is_group_context, is_shared_context
from services.ephemeral import EphemeralMessenger
from services.localization import tr
from services.premium_emoji import build_premium_entities_from_text
from services.vinyl_settings import VinylSettings
from services.wizard_preview import WizardPreviewService


@dataclass(slots=True)
class WizardHooks:
    resolve_callback_uid: Callable[..., Awaitable]
    get_pending_audio: Callable
    reply_text_variable: Callable[..., Awaitable]
    launch_job: Callable[..., Awaitable]
    channel_ctx: Callable
    user_has_premium_access: Callable[[int], bool]


class WizardRuntime:
    def __init__(
        self,
        *,
        pending_audio: dict,
        vinyl_settings: VinylSettings,
        ephemeral: EphemeralMessenger,
        preview_service: WizardPreviewService,
        hooks: WizardHooks,
        valid_vinyl_colors: frozenset[str],
        ttl_seconds: int,
    ):
        self.pending_audio = pending_audio
        self.vinyl_settings = vinyl_settings
        self.ephemeral = ephemeral
        self.preview_service = preview_service
        self.hooks = hooks
        self.valid_vinyl_colors = valid_vinyl_colors
        self.ttl_seconds = ttl_seconds
        self.state: dict[object, dict] = {}
        self.pending_confirm: dict[int, dict] = {}

    def reset(self, uid) -> None:
        self.state.pop(uid, None)

    def cancel(self, uid) -> None:
        self.state.pop(uid, None)
        if isinstance(uid, int):
            self.pending_confirm.pop(uid, None)

    def has_active(self, uid) -> bool:
        return uid in self.state

    def cleanup_orphaned(self) -> int:
        removed = 0
        for uid in list(self.state):
            if uid not in self.pending_audio:
                self.state.pop(uid, None)
                removed += 1
        return removed

    def cleanup_expired_confirm(self) -> int:
        now = time.time()
        removed = 0
        for uid, job in list(self.pending_confirm.items()):
            if now > job.get("confirm_expires_at", 0):
                self.pending_confirm.pop(uid, None)
                removed += 1
        return removed

    def color_keyboard(self, uid, chat_id=None, message_id=None):
        access_uid = uid if isinstance(uid, int) else 0
        pending = self.pending_audio.get(uid)
        if pending and isinstance(pending.get("owner_user_id"), int):
            access_uid = pending["owner_user_id"]
        return keyboards.build_wiz_color_keyboard(
            uid,
            chat_id,
            message_id,
            has_premium=self.hooks.user_has_premium_access(access_uid),
        )

    async def advance_to_segment_or_finish(self, bot: Bot, uid, send_func) -> None:
        pending = self.pending_audio.get(uid)
        if not pending:
            return
        total_duration = pending["audio"].duration or 0
        if total_duration <= config.MAX_DURATION_SECONDS:
            await self.finish(bot, uid, send_func, segment_start=0.0)
            return

        chat_id, message_id = self.hooks.channel_ctx(uid)
        sent = await send_func(
            tr("MSG_WIZ_CHOOSE_SEGMENT", uid),
            reply_markup=keyboards.build_wiz_segment_keyboard(
                total_duration,
                uid,
                chat_id,
                message_id,
            ),
        )
        if (
            is_shared_context(uid)
            and sent is not None
            and sent.message_id not in pending.get("channel_msg_ids", [])
        ):
            pending.setdefault("channel_msg_ids", []).append(sent.message_id)

    async def finish(self, bot: Bot, uid, send_func, segment_start: float) -> None:
        pending = self.pending_audio.pop(uid, None)
        self.state.pop(uid, None)
        if not pending:
            await send_func(tr("MSG_WIZ_EXPIRED", uid))
            return

        job = dict(pending)
        owner_id = pending.get("owner_user_id", uid)
        job["uid"] = owner_id
        job["context_key"] = uid
        job["segment_start"] = segment_start
        job["vinyl_choice"] = self.vinyl_settings.get_choice(uid)
        job["rotation_seconds"] = self.vinyl_settings.get_rotation_seconds(uid)

        if is_group_context(uid):
            job["status_ephemeral_message_id"] = self.ephemeral.message_id(pending)
            await self.hooks.launch_job(bot, owner_id, job)
            return

        if is_channel_context(uid):
            starting_text = tr("MSG_WIZ_STARTING", owner_id)
            entities = build_premium_entities_from_text(starting_text)
            sent = (
                await send_func(starting_text, entities=entities)
                if entities
                else await send_func(starting_text)
            )
            if sent is not None:
                job.setdefault("channel_msg_ids", [])
                if sent.message_id not in job["channel_msg_ids"]:
                    job["channel_msg_ids"].append(sent.message_id)
            await self.hooks.launch_job(bot, owner_id, job)
            return

        job["confirm_expires_at"] = time.time() + self.ttl_seconds
        self.pending_confirm[owner_id] = job
        await send_func(
            tr("MSG_WIZ_REVIEW", owner_id),
            reply_markup=keyboards.build_wiz_confirm_keyboard(owner_id),
        )

    async def handle_photo(self, message: Message, bot: Bot, uid) -> bool:
        if uid not in self.state:
            return False

        pending = self.hooks.get_pending_audio(uid)
        if not pending:
            await self.hooks.reply_text_variable(
                message, bot, "MSG_AUDIO_EXPIRED", uid
            )
            return True

        pending["thumbnail_file_id"] = message.photo[-1].file_id
        if is_group_context(uid):
            original = pending.get("message")
            await self.ephemeral.edit_wizard_text_variable(
                bot, uid, original, "MSG_IMAGE_RECEIVED"
            )
            await self.advance_to_segment_or_finish(
                bot,
                uid,
                lambda text, **kwargs: self.ephemeral.edit_wizard_text(
                    bot, uid, original, text, **kwargs
                ),
            )
        else:
            await self.hooks.reply_text_variable(
                message, bot, "MSG_IMAGE_RECEIVED", uid
            )
            await self.advance_to_segment_or_finish(bot, uid, message.reply)
        return True


def create_wizard_router(runtime: WizardRuntime) -> Router:
    router = Router(name=__name__)

    @router.callback_query(F.data.startswith("mode:custom"))
    async def on_mode_custom(callback: CallbackQuery, bot: Bot):
        resolved = await runtime.hooks.resolve_callback_uid(callback, bot)
        if resolved is None:
            return
        _, uid, _channel_chat_id = resolved
        if not runtime.hooks.get_pending_audio(uid):
            await callback.answer(tr("MSG_WIZ_EXPIRED", uid), show_alert=True)
            return
        runtime.state[uid] = {}
        chat_id, message_id = runtime.hooks.channel_ctx(uid)
        await runtime.ephemeral.edit_wizard_text(
            bot,
            uid,
            callback.message,
            tr("MSG_WIZ_CHOOSE_COLOR", uid),
            reply_markup=runtime.color_keyboard(uid, chat_id, message_id),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("wiz_color:"))
    async def on_wiz_color(callback: CallbackQuery, bot: Bot):
        resolved = await runtime.hooks.resolve_callback_uid(callback, bot)
        if resolved is None:
            return
        base, uid, _channel_chat_id = resolved
        if uid not in runtime.state or not runtime.hooks.get_pending_audio(uid):
            await callback.answer(tr("MSG_WIZ_EXPIRED", uid), show_alert=True)
            return

        choice = base.split(":", 1)[1]
        presser_id = callback.from_user.id if callback.from_user else 0
        if choice in runtime.valid_vinyl_colors:
            if limits.is_premium_color(choice) and not runtime.hooks.user_has_premium_access(
                presser_id
            ):
                await callback.answer(
                    tr("MSG_COLOR_PREMIUM_ONLY", presser_id), show_alert=True
                )
                await callback.message.reply(
                    tr("MSG_COLOR_PREMIUM_ONLY", presser_id),
                    reply_markup=keyboards.build_buy_stars_keyboard(presser_id),
                )
                return
            runtime.vinyl_settings.set_choice(uid, choice)
        else:
            runtime.vinyl_settings.set_choice(uid, None)

        chat_id, message_id = runtime.hooks.channel_ctx(uid)
        await runtime.ephemeral.edit_wizard_text(
            bot,
            uid,
            callback.message,
            tr("MSG_WIZ_CHOOSE_SPEED", uid),
            reply_markup=keyboards.build_wiz_speed_keyboard(
                uid, chat_id, message_id
            ),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("wiz_speed:"))
    async def on_wiz_speed(callback: CallbackQuery, bot: Bot):
        resolved = await runtime.hooks.resolve_callback_uid(callback, bot)
        if resolved is None:
            return
        base, uid, _channel_chat_id = resolved
        pending = runtime.hooks.get_pending_audio(uid)
        if uid not in runtime.state or not pending:
            await callback.answer(tr("MSG_WIZ_EXPIRED", uid), show_alert=True)
            return

        runtime.vinyl_settings.set_rotation_value(uid, base.split(":", 1)[1])
        has_thumb = bool(pending["audio"].thumbnail)
        chat_id, message_id = runtime.hooks.channel_ctx(uid)
        image_text = (
            texts_module.MSG_CHANNEL_ASK_IMAGE_REPLY_WITH_SKIP
            if chat_id is not None and has_thumb
            else texts_module.MSG_CHANNEL_ASK_IMAGE_REPLY
            if chat_id is not None
            else tr("MSG_WIZ_CHOOSE_IMAGE", uid)
        )
        await runtime.ephemeral.edit_wizard_text(
            bot,
            uid,
            callback.message,
            image_text,
            reply_markup=keyboards.build_wiz_image_keyboard(
                has_thumb, uid, chat_id, message_id
            ),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("wiz_image:skip"))
    async def on_wiz_image_skip(callback: CallbackQuery, bot: Bot):
        resolved = await runtime.hooks.resolve_callback_uid(callback, bot)
        if resolved is None:
            return
        _, uid, _channel_chat_id = resolved
        pending = runtime.hooks.get_pending_audio(uid)
        if uid not in runtime.state or not pending:
            await callback.answer(tr("MSG_WIZ_EXPIRED", uid), show_alert=True)
            return
        if not pending["audio"].thumbnail:
            await callback.answer(
                tr("MSG_WIZ_NO_IMAGE_TO_SKIP", uid), show_alert=True
            )
            return
        await runtime.advance_to_segment_or_finish(
            bot,
            uid,
            lambda text, **kwargs: runtime.ephemeral.edit_wizard_text(
                bot, uid, callback.message, text, **kwargs
            ),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("wiz_segment:"))
    async def on_wiz_segment(callback: CallbackQuery, bot: Bot):
        resolved = await runtime.hooks.resolve_callback_uid(callback, bot)
        if resolved is None:
            return
        base, uid, _channel_chat_id = resolved
        await runtime.finish(
            bot,
            uid,
            lambda text, **kwargs: runtime.ephemeral.edit_wizard_text(
                bot, uid, callback.message, text, **kwargs
            ),
            segment_start=float(base.split(":", 1)[1]),
        )
        await callback.answer()

    @router.callback_query(F.data == "wiz_preview_confirm")
    async def on_wiz_preview_confirm(callback: CallbackQuery, bot: Bot):
        uid = callback.from_user.id if callback.from_user else 0
        job = runtime.pending_confirm.get(uid)
        if not job:
            await callback.answer(tr("MSG_WIZ_EXPIRED", uid), show_alert=True)
            return
        await callback.answer(tr("MSG_PREVIEW_STARTING", uid))
        await runtime.preview_service.run(bot, callback.message, uid, job)

    @router.callback_query(F.data == "wiz_full_confirm")
    async def on_wiz_full_confirm(callback: CallbackQuery, bot: Bot):
        uid = callback.from_user.id if callback.from_user else 0
        job = runtime.pending_confirm.pop(uid, None)
        if not job:
            await callback.answer(tr("MSG_WIZ_EXPIRED", uid), show_alert=True)
            return
        await callback.answer()
        starting_text = tr("MSG_WIZ_STARTING", uid)
        entities = build_premium_entities_from_text(starting_text)
        if entities:
            await callback.message.reply(starting_text, entities=entities)
        else:
            await callback.message.reply(starting_text)
        await runtime.hooks.launch_job(bot, uid, job)

    return router
