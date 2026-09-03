import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, InputRichMessage, Message, MessageEntity

import texts as texts_module
from services.contexts import is_group_context
from services.messaging import (
    format_rich_value,
    get_text_rich_content,
    get_text_value,
    normalize_rich_blocks_for_input,
)

logger = logging.getLogger(__name__)
STATUS_UPDATE_INTERVAL_SECONDS = 2.2


async def send_ephemeral_text(
    bot: Bot,
    chat_id: int,
    user_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    entities: list[MessageEntity] | None = None,
    callback_query_id: str | None = None,
) -> Message:
    return await bot.send_message(
        chat_id=chat_id,
        text=text,
        receiver_user_id=user_id,
        callback_query_id=callback_query_id,
        reply_markup=reply_markup,
        entities=entities,
    )


async def edit_ephemeral_text(
    bot: Bot,
    chat_id: int,
    user_id: int,
    ephemeral_message_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    entities: list[MessageEntity] | None = None,
) -> bool:
    return await bot.edit_ephemeral_message_text(
        chat_id=chat_id,
        receiver_user_id=user_id,
        ephemeral_message_id=ephemeral_message_id,
        text=text,
        reply_markup=reply_markup,
        entities=entities,
    )


async def delete_ephemeral_text(
    bot: Bot,
    chat_id: int,
    user_id: int,
    ephemeral_message_id: int,
) -> bool:
    return await bot.delete_ephemeral_message(
        chat_id=chat_id,
        receiver_user_id=user_id,
        ephemeral_message_id=ephemeral_message_id,
    )


def ephemeral_id(pending: dict | None) -> int | None:
    if not pending:
        return None
    value = pending.get("ephemeral_message_id")
    return int(value) if value is not None else None


class EphemeralMessenger:
    def __init__(self, pending_audio: dict):
        self.pending_audio = pending_audio

    def message_id(self, pending: dict | None) -> int | None:
        return ephemeral_id(pending)

    async def send_text(self, *args, **kwargs) -> Message:
        return await send_ephemeral_text(*args, **kwargs)

    async def edit_text(self, *args, **kwargs) -> bool:
        return await edit_ephemeral_text(*args, **kwargs)

    async def delete_text(self, *args, **kwargs) -> bool:
        return await delete_ephemeral_text(*args, **kwargs)

    async def edit_wizard_text(
        self,
        bot: Bot,
        context_key,
        target_message: Message,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
        entities: list[MessageEntity] | None = None,
    ) -> Message | None:
        if is_group_context(context_key):
            pending = self.pending_audio.get(context_key)
            message_id = self.message_id(pending)
            if message_id is None:
                return None
            original = pending.get("message") if pending else None
            owner_id = (pending or {}).get("owner_user_id") or (
                original.from_user.id if original and original.from_user else 0
            )
            await self.edit_text(
                bot,
                target_message.chat.id,
                owner_id,
                message_id,
                text,
                reply_markup=reply_markup,
                entities=entities,
            )
            return target_message

        return await target_message.edit_text(
            text,
            reply_markup=reply_markup,
            entities=entities,
        )

    async def edit_wizard_text_variable(
        self,
        bot: Bot,
        context_key,
        target_message: Message,
        var_name: str,
        reply_markup: InlineKeyboardMarkup | None = None,
        **format_kwargs,
    ):
        rich = get_text_rich_content(var_name, context_key)
        if rich and not is_group_context(context_key):
            blocks = format_rich_value(rich.get("blocks"), **format_kwargs)
            html_content = format_rich_value(rich.get("html"), **format_kwargs)
            if blocks or html_content:
                return await target_message.edit_text(
                    rich_message=InputRichMessage(
                        blocks=normalize_rich_blocks_for_input(blocks),
                        html=html_content,
                        is_rtl=rich.get("is_rtl"),
                    ),
                    reply_markup=reply_markup,
                )

        text = get_text_value(var_name, context_key)
        if format_kwargs:
            text = text.format(**format_kwargs)
        return await self.edit_wizard_text(
            bot,
            context_key,
            target_message,
            text,
            reply_markup=reply_markup,
        )


class EphemeralStatusAnimator:
    def __init__(self, bot: Bot, chat_id: int, user_id: int, ephemeral_message_id: int):
        self.bot = bot
        self.chat_id = chat_id
        self.user_id = user_id
        self.ephemeral_message_id = ephemeral_message_id
        self.stage_text = texts_module.STAGE_PREPARING
        self.percent: float = 0.0
        self._last_rendered: str | None = None
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None

    def set_stage(self, stage_text: str, percent: float | None = None) -> None:
        self.stage_text = stage_text
        if percent is not None:
            self.percent = percent

    async def _push_update(self) -> None:
        text = self.stage_text + (f" {int(self.percent)}%" if self.percent is not None else "…")
        if text == self._last_rendered:
            return
        try:
            await edit_ephemeral_text(
                self.bot,
                self.chat_id,
                self.user_id,
                int(self.ephemeral_message_id),
                text,
            )
            self._last_rendered = text
        except TelegramBadRequest:
            pass
        except Exception:
            logger.exception(texts_module.LOG_PROGRESS_UPDATE_FAILED)

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            await self._push_update()
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=STATUS_UPDATE_INTERVAL_SECONDS
                )
            except asyncio.TimeoutError:
                pass

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            try:
                await self._task
            except Exception:
                pass
