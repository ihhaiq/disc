
import json
import logging
import os
import time

import config

logger = logging.getLogger(__name__)

_DATA_DIR = getattr(config, "DATA_DIR", config.BASE_DIR)
HELP_MESSAGE_FILE_PATH = os.path.join(_DATA_DIR, "help_message.json")

_DEFAULT_HTML = "النص"


def _read_raw() -> dict:
    if not os.path.exists(HELP_MESSAGE_FILE_PATH):
        return {}
    try:
        with open(HELP_MESSAGE_FILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logger.exception("فشل قراءة help_message.json")
        return {}


def _write_raw(data: dict) -> None:
    os.makedirs(os.path.dirname(HELP_MESSAGE_FILE_PATH), exist_ok=True)
    tmp_path = HELP_MESSAGE_FILE_PATH + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, HELP_MESSAGE_FILE_PATH)
    except Exception:
        logger.exception("فشل حفظ ملف help_message.json")


def get_draft(uid: int) -> dict:
    """
    مسودة المطور الحالية (قبل الحفظ/النشر النهائي).
    شكلها: {"html": str | None, "blocks": list | None, "buttons": [{"text": str, "url": str}]}
    - لو "blocks" موجودة (غير None) ← هذا المصدر الأساسي، ويُرسَل كما هو.
    - لو "blocks" فاضية ← نستخدم "html" كبديل.
    """
    data = _read_raw()
    draft = data.get("draft", {}).get(str(uid))
    if draft is None:
        draft = {"html": _DEFAULT_HTML, "blocks": None, "buttons": []}
    draft.setdefault("blocks", None)
    draft.setdefault("html", _DEFAULT_HTML)
    draft.setdefault("buttons", [])
    return draft


def save_draft(uid: int, draft: dict) -> None:
    data = _read_raw()
    data.setdefault("draft", {})[str(uid)] = draft
    _write_raw(data)


def get_published() -> dict | None:
    """
    النسخة المنشورة فعليًا اللي يشوفها المستخدمين عند إرسال /help.
    None لو المطور ما نشر شي بعد (نرجع للنص الافتراضي القديم MSG_START_HELP).
    """
    data = _read_raw()
    published = data.get("published")
    if published is not None:
        published.setdefault("blocks", None)
    return published


def publish(uid: int, draft: dict, editor_name: str = "") -> None:
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
