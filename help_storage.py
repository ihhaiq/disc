
import json
import logging
import os
import threading
import time

import config

logger = logging.getLogger(__name__)

_lock = threading.Lock()

HELP_MESSAGE_FILE_PATH = os.path.join(config.DATA_DIR, "help_message.json")
_DEFAULT_HTML = "النص"


def _read_raw() -> dict:
    if not os.path.exists(HELP_MESSAGE_FILE_PATH):
        return {}
    try:
        with open(HELP_MESSAGE_FILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError, TypeError):
        logger.exception("فشل قراءة help_message.json")
        return {}


def _write_raw(data: dict) -> None:
    os.makedirs(os.path.dirname(HELP_MESSAGE_FILE_PATH), exist_ok=True)
    tmp_path = HELP_MESSAGE_FILE_PATH + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, HELP_MESSAGE_FILE_PATH)
    except (OSError, TypeError):
        logger.exception("فشل حفظ ملف help_message.json")


def _normalize_draft(draft: dict | None) -> dict:
    normalized = draft or {}
    normalized.setdefault("html", _DEFAULT_HTML)
    normalized.setdefault("blocks", None)
    normalized.setdefault("buttons", [])
    return normalized


def get_draft(uid: int) -> dict:
    """Return the developer's current `/help` draft."""
    data = _read_raw()
    return _normalize_draft(data.get("draft", {}).get(str(uid)))


def save_draft(uid: int, draft: dict) -> None:
    with _lock:
        data = _read_raw()
        data.setdefault("draft", {})[str(uid)] = draft
        _write_raw(data)


def get_published() -> dict | None:
    """Return the published `/help` message, if one exists."""
    data = _read_raw()
    published = data.get("published")
    return _normalize_draft(published) if published is not None else None


def publish(uid: int, draft: dict, editor_name: str = "") -> None:
    with _lock:
        data = _read_raw()
        data["published"] = {
            "html": draft.get("html", _DEFAULT_HTML),
            "blocks": draft.get("blocks"),
            "buttons": draft.get("buttons", []),
            "editor_id": uid,
            "editor_name": editor_name,
            "updated_at": time.time(),
        }
        _write_raw(data)
