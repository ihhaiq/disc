import os
import time

import config
from storage import JsonStore

HELP_MESSAGE_FILE_PATH = os.path.join(config.DATA_DIR, "help_message.json")
_store = JsonStore(HELP_MESSAGE_FILE_PATH)
_DEFAULT_HTML = "النص"


def _read_raw() -> dict:
    return _store.read()


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
    def update(data: dict) -> None:
        data.setdefault("draft", {})[str(uid)] = draft

    _store.update(update)


def get_published() -> dict | None:
    """Return the published `/help` message, if one exists."""
    data = _read_raw()
    published = data.get("published")
    return _normalize_draft(published) if published is not None else None


def publish(uid: int, draft: dict, editor_name: str = "") -> None:
    def update(data: dict) -> None:
        data["published"] = {
            "html": draft.get("html", _DEFAULT_HTML),
            "blocks": draft.get("blocks"),
            "buttons": draft.get("buttons", []),
            "editor_id": uid,
            "editor_name": editor_name,
            "updated_at": time.time(),
        }

    _store.update(update)
