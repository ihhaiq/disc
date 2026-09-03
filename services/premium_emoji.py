"""Telegram custom-emoji parsing and entity creation."""

import logging
import re

from aiogram.types import MessageEntity

logger = logging.getLogger(__name__)
PREMIUM_EMOJI_REGEX = r'<tg-emoji\s+emoji-id=["\'](\d+)["\']\s*>(.+?)</tg-emoji>'


def utf16_length(character: str) -> int:
    return len(character.encode("utf-16-le")) // 2


def extract_premium_emojis(text: str) -> dict[str, str]:
    emojis = {}
    for match in re.finditer(PREMIUM_EMOJI_REGEX, text):
        emojis[match.group(2)] = match.group(1)
    return emojis


def clean_premium_emoji_tags(text: str) -> str:
    return re.sub(PREMIUM_EMOJI_REGEX, r"\2", text)


def build_premium_entities_from_text(text: str) -> list[MessageEntity] | None:
    emojis = extract_premium_emojis(text)
    if not emojis:
        return None
    entities = []
    offset = 0
    for character in clean_premium_emoji_tags(text):
        length = utf16_length(character)
        if character in emojis:
            entities.append(
                MessageEntity(
                    type="custom_emoji",
                    offset=offset,
                    length=length,
                    custom_emoji_id=emojis[character],
                )
            )
        offset += length
    return entities or None


def validate_premium_emoji_syntax(text: str) -> tuple[bool, str]:
    open_tags = len(re.findall(r"<tg-emoji", text))
    close_tags = len(re.findall(r"</tg-emoji>", text))
    if open_tags != close_tags:
        return False, f"❌ عدد tags غير متطابق: {open_tags} فتح و {close_tags} إغلاق"

    ids = re.findall(r'<tg-emoji\s+emoji-id=["\']([^"\']+)["\']', text)
    for emoji_id in ids:
        if not emoji_id.isdigit():
            return False, f"❌ emoji-id يجب أن يكون أرقام فقط: '{emoji_id}'"

    if re.findall(r"<tg-emoji[^>]*>\s*</tg-emoji>", text):
        return False, "❌ tag الإيموجي فارغ، ضع إيموجي أو نص بالداخل"
    return True, ""
