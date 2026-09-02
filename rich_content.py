"""Pure helpers for extracting reusable rich-message content."""

import html
import logging
from typing import Any

logger = logging.getLogger(__name__)

MEDIA_BLOCK_TYPES = frozenset({"video", "photo", "animation", "audio", "document"})


def escape_rich_html(text: str) -> str:
    return html.escape(text, quote=False)


def _normalize_media_dict(media: dict[str, Any]) -> dict[str, Any]:
    if "media" in media:
        return media
    file_id = media.get("file_id")
    return {"media": file_id} if file_id else media


def normalize_blocks_for_input(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                _normalize_media_dict(item)
                if key in MEDIA_BLOCK_TYPES and isinstance(item, dict)
                else normalize_blocks_for_input(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [normalize_blocks_for_input(item) for item in value]
    return value


def extract_rich_content(message: Any) -> tuple[str | None, list | None]:
    """Extract rich blocks when available, otherwise return safe HTML."""
    rich = getattr(message, "rich_message", None)
    if rich is not None:
        html_value = getattr(rich, "html", None)
        if html_value:
            return html_value, None

        blocks = getattr(rich, "blocks", None)
        if blocks:
            try:
                dumped = [
                    block.model_dump(exclude_none=True)
                    if hasattr(block, "model_dump")
                    else block
                    for block in blocks
                ]
            except (AttributeError, TypeError, ValueError):
                logger.exception("Failed to extract rich-message blocks")
            else:
                if dumped:
                    return None, normalize_blocks_for_input(dumped)

    html_text = getattr(message, "html_text", None)
    if html_text:
        return html_text, None
    text = getattr(message, "text", None)
    if text:
        return escape_rich_html(text), None
    caption = getattr(message, "caption", None)
    if caption:
        return escape_rich_html(caption), None
    return None, None
