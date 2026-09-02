"""Persistent custom text overrides managed by the developer panel."""

import logging
import os
import threading
import time
from typing import Any

import config
from storage import JsonStore

logger = logging.getLogger(__name__)

_lock = threading.Lock()

CUSTOM_TEXTS_FILE = os.path.join(config.DATA_DIR, "custom_texts.json")
_store = JsonStore(CUSTOM_TEXTS_FILE)

_custom_data: dict[str, dict[str, Any]] = _store.read()


def _save() -> None:
    _store.write(_custom_data)


if _custom_data:
    logger.info("تم تحميل %s نص مخصص", len(_custom_data))


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
