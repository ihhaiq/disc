"""Telegram text and rich-message delivery."""

import html
import logging
import re

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InputRichMessage, InlineKeyboardMarkup, Message, ReplyParameters

import custom_texts
from services.localization import get_user_lang, tr
from services.premium_emoji import (
    build_premium_entities_from_text,
    clean_premium_emoji_tags,
    extract_premium_emojis,
)
from services.text_markup import clean_html

logger = logging.getLogger(__name__)
RICH_MEDIA_KEYS = frozenset({"photo", "video", "animation", "audio", "voice_note", "document"})


def model_dump(value):
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(exclude_none=True)
        except Exception:
            pass
    if hasattr(value, "dict"):
        try:
            return value.dict(exclude_none=True)
        except Exception:
            pass
    return value


def normalize_rich_media_for_input(value):
    if isinstance(value, list):
        return [normalize_rich_media_for_input(item) for item in value]
    if not isinstance(value, dict):
        return value

    result = {}
    for key, item in value.items():
        if key == "photo" and isinstance(item, list):
            candidates = [
                photo for photo in item if isinstance(photo, dict) and photo.get("file_id")
            ]
            if candidates:
                largest = max(
                    candidates,
                    key=lambda photo: (photo.get("width", 0) or 0)
                    * (photo.get("height", 0) or 0),
                )
                result[key] = {"media": largest["file_id"]}
            else:
                result[key] = normalize_rich_media_for_input(item)
        elif key in RICH_MEDIA_KEYS and isinstance(item, dict) and item.get("file_id"):
            result[key] = {"media": item["file_id"]}
        else:
            result[key] = normalize_rich_media_for_input(item)
    return result


def normalize_rich_blocks_for_input(blocks: list | None) -> list | None:
    return normalize_rich_media_for_input(blocks) if blocks else None


def rich_text_fallback(value) -> str:
    parts: list[str] = []

    def walk(obj):
        if isinstance(obj, dict):
            for key, child in obj.items():
                if key == "text" and isinstance(child, str):
                    parts.append(child)
                elif key in {
                    "caption",
                    "summary",
                    "title",
                    "description",
                    "content",
                    "items",
                    "blocks",
                }:
                    walk(child)
        elif isinstance(obj, list):
            for child in obj:
                walk(child)

    walk(value)
    result = "\n".join(part for part in parts if part).strip()
    return result or "🖼️" if value else ""


def format_rich_value(value, **kwargs):
    if not kwargs:
        return value
    if isinstance(value, str):
        try:
            return value.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return value
    if isinstance(value, list):
        return [format_rich_value(item, **kwargs) for item in value]
    if isinstance(value, dict):
        return {key: format_rich_value(item, **kwargs) for key, item in value.items()}
    return value


def get_text_rich_content(var_name: str, user_id: int = 0) -> dict | None:
    key = f"EN::{var_name}" if get_user_lang(user_id) == "en" else var_name
    return custom_texts.get_custom_rich(key)


def get_text_value(var_name: str, user_id: int = 0) -> str:
    return tr(var_name, user_id)


async def send_rich_message(
    bot: Bot,
    chat_id: int,
    html_content: str | None = None,
    blocks: list | None = None,
    reply_to_message_id: int | None = None,
    reply_markup: InlineKeyboardMarkup | None = None,
    is_rtl: bool | None = None,
) -> Message:
    reply_params = ReplyParameters(message_id=reply_to_message_id) if reply_to_message_id else None
    try:
        rich_message = (
            InputRichMessage(
                blocks=normalize_rich_blocks_for_input(blocks),
                is_rtl=is_rtl,
            )
            if blocks
            else InputRichMessage(html=html_content or "", is_rtl=is_rtl)
        )
        return await bot.send_rich_message(
            chat_id=chat_id,
            rich_message=rich_message,
            reply_parameters=reply_params,
            reply_markup=reply_markup,
        )
    except (AttributeError, TypeError):
        logger.warning("sendRichMessage غير مدعوم، سيتم إرسال نص عادي")
    except Exception:
        logger.exception("فشل إرسال Rich Message، سيتم إرسال نص عادي")

    if html_content:
        fallback = re.sub(r"<[^>]+>", " ", html_content)
        fallback = html.unescape(re.sub(r"\s+", " ", fallback)).strip()
    elif blocks:
        fallback = rich_text_fallback(blocks)
    else:
        fallback = "⚠️ تعذّر عرض المحتوى الغني."
    return await bot.send_message(chat_id=chat_id, text=fallback, reply_markup=reply_markup)


def sanitize_text(text: str) -> str:
    if not text:
        return ""
    return clean_html(text) if "<" in text and ">" in text else text


async def safe_reply(message: Message, text: str, **kwargs) -> Message:
    text = sanitize_text(text)
    try:
        return await message.reply(text, **kwargs)
    except TelegramBadRequest as exc:
        if "can't parse entities" not in str(exc).lower():
            raise
        logger.warning("فشل تفسير HTML، سيتم إرسال النص الخام: %s", exc)
        clean_kwargs = {key: value for key, value in kwargs.items() if key != "parse_mode"}
        return await message.reply(
            html.escape(text),
            parse_mode=None,
            **clean_kwargs,
        )


async def reply_with_premium_emoji(message: Message, text: str, **kwargs) -> Message:
    text = sanitize_text(text)
    emojis = extract_premium_emojis(text)
    if emojis:
        clean_text = clean_premium_emoji_tags(text)
        entities = build_premium_entities_from_text(text)
        try:
            if entities:
                return await message.reply(clean_text, entities=entities, **kwargs)
            return await message.reply(clean_text, **kwargs)
        except TelegramBadRequest as exc:
            logger.warning(
                "فشل إرسال رسالة مع إيموجي بريميوم: %s, سيتم الإرسال بدونها",
                exc,
            )
            return await message.reply(clean_text, **kwargs)

    try:
        return await message.reply(text, **kwargs)
    except TelegramBadRequest as exc:
        if "can't parse entities" not in str(exc).lower():
            raise
        logger.warning("فشل تفسير HTML، سيُرسل كنص خام: %s", exc)
        clean_kwargs = {key: value for key, value in kwargs.items() if key != "entities"}
        return await message.reply(html.escape(text), **clean_kwargs)


async def reply_text_variable(
    message: Message,
    bot: Bot,
    var_name: str,
    user_id: int = 0,
    reply_markup: InlineKeyboardMarkup | None = None,
    **format_kwargs,
) -> Message:
    rich = get_text_rich_content(var_name, user_id)
    if rich:
        blocks = format_rich_value(rich.get("blocks"), **format_kwargs)
        html_content = format_rich_value(rich.get("html"), **format_kwargs)
        if blocks or html_content:
            return await send_rich_message(
                bot,
                message.chat.id,
                html_content=html_content,
                blocks=blocks,
                reply_to_message_id=message.message_id,
                reply_markup=reply_markup,
                is_rtl=rich.get("is_rtl"),
            )
    text = get_text_value(var_name, user_id)
    return await safe_reply(
        message,
        text.format(**format_kwargs) if format_kwargs else text,
        reply_markup=reply_markup,
    )


async def edit_text_variable(
    message: Message,
    bot: Bot,
    var_name: str,
    user_id: int = 0,
    reply_markup: InlineKeyboardMarkup | None = None,
    **format_kwargs,
) -> Message:
    rich = get_text_rich_content(var_name, user_id)
    if rich:
        blocks = format_rich_value(rich.get("blocks"), **format_kwargs)
        html_content = format_rich_value(rich.get("html"), **format_kwargs)
        if blocks or html_content:
            return await message.edit_text(
                rich_message=InputRichMessage(
                    blocks=normalize_rich_blocks_for_input(blocks),
                    html=html_content,
                    is_rtl=rich.get("is_rtl"),
                ),
                reply_markup=reply_markup,
            )
    text = get_text_value(var_name, user_id)
    return await message.edit_text(
        text.format(**format_kwargs) if format_kwargs else text,
        reply_markup=reply_markup,
    )


async def send_text_variable(
    bot: Bot,
    chat_id: int,
    var_name: str,
    user_id: int = 0,
    reply_to_message_id: int | None = None,
    reply_markup: InlineKeyboardMarkup | None = None,
    **format_kwargs,
) -> Message:
    rich = get_text_rich_content(var_name, user_id)
    if rich:
        blocks = format_rich_value(rich.get("blocks"), **format_kwargs)
        html_content = format_rich_value(rich.get("html"), **format_kwargs)
        if blocks or html_content:
            return await send_rich_message(
                bot,
                chat_id,
                html_content=html_content,
                blocks=blocks,
                reply_to_message_id=reply_to_message_id,
                reply_markup=reply_markup,
                is_rtl=rich.get("is_rtl"),
            )
    text = get_text_value(var_name, user_id)
    if format_kwargs:
        text = text.format(**format_kwargs)
    reply_parameters = (
        ReplyParameters(message_id=reply_to_message_id) if reply_to_message_id else None
    )
    return await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_parameters=reply_parameters,
        reply_markup=reply_markup,
    )
