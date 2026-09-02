"""Persistent custom text overrides managed by the developer panel."""

import json
import logging
import os
import threading
import time
from typing import Any

import config

logger = logging.getLogger(__name__)

_lock = threading.Lock()

CUSTOM_TEXTS_FILE = os.path.join(config.DATA_DIR, "custom_texts.json")

_custom_data: dict[str, dict[str, Any]] = {}


def _load() -> None:
    global _custom_data
    if os.path.exists(CUSTOM_TEXTS_FILE):
        try:
            with open(CUSTOM_TEXTS_FILE, "r", encoding="utf-8") as f:
                _custom_data = json.load(f)
                logger.info("تم تحميل %s نص مخصص", len(_custom_data))
        except (OSError, ValueError, TypeError):
            logger.exception("فشل تحميل ملف النصوص المخصصة")
            _custom_data = {}
    else:
        _custom_data = {}


def _save() -> None:
    os.makedirs(os.path.dirname(CUSTOM_TEXTS_FILE), exist_ok=True)
    tmp_path = CUSTOM_TEXTS_FILE + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(_custom_data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, CUSTOM_TEXTS_FILE)
    except (OSError, TypeError):
        logger.exception("فشل حفظ ملف النصوص المخصصة")


_load()


def get_custom_rich(var_name: str) -> dict | None:
    """Return the saved rich-message value for a text override."""
    entry = _custom_data.get(var_name)
    if not entry:
        return None
    rich = entry.get("rich")
    return rich if isinstance(rich, dict) else None


def set_custom(
    var_name: str,
    value: str,
    editor_id: int = 0,
    editor_name: str = "",
    rich: dict | None = None,
) -> None:
    """Store a text override and its optional rich-message representation."""
    entry = {
        "value": value,
        "updated_at": time.time(),
        "editor_id": editor_id,
        "editor_name": editor_name,
    }
    if rich is not None:
        entry["rich"] = rich
    with _lock:
        _custom_data[var_name] = entry
        _save()
    logger.info("تم حفظ نص مخصص: %s", var_name)


def list_custom() -> dict[str, Any]:
    with _lock:
        return dict(_custom_data)
