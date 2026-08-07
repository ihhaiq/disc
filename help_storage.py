# -*- coding: utf-8 -*-
"""
تخزين دائم لرسالة /help الغنية (Rich Message) اللي يبنيها المطور:
- النص (HTML الخاص بالـ Rich Message)
- الأزرار (قائمة أزرار url فقط، لأن أزرار الـ Rich Message المرفقة برسالة عادية
  تكون InlineKeyboardButton عادية)

نفس فلسفة custom_texts.py: يُحفظ بملف JSON داخل DATA_DIR (المربوط بـ Railway
Volume) حتى يبقى بعد الـ Restart/Redeploy.
"""
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
    with open(HELP_MESSAGE_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_draft(uid: int) -> dict:
    """
    مسودة المطور الحالية (قبل الحفظ/النشر النهائي).
    شكلها: {"html": str, "buttons": [{"text": str, "url": str}]}
    """
    data = _read_raw()
    draft = data.get("draft", {}).get(str(uid))
    if draft is None:
        draft = {"html": _DEFAULT_HTML, "buttons": []}
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
    return data.get("published")


def publish(uid: int, draft: dict, editor_name: str = "") -> None:
    data = _read_raw()
    data["published"] = {
        "html": draft.get("html", _DEFAULT_HTML),
        "buttons": draft.get("buttons", []),
        "editor_id": uid,
        "editor_name": editor_name,
        "updated_at": time.time(),
    }
    _write_raw(data)
