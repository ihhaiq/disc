"""
إدارة النصوص المخصصة (Custom Texts) — يحفظها بـ JSON دائم (لا تختفي بعد Restart).

الفكرة:
- المطور يعدّل النصوص عن طريق لوحة /dev
- التعديلات تُحفظ بـ DATA_DIR/custom_texts.json (دائم، مربوط بـ Railway Volume)
- عند الوصول لنص: نتحقق من custom_texts.json أولاً، لو ما فيه ننرجع الافتراضي من texts.py
"""

import json
import logging
import os
import threading
import time
from typing import Any

import config

logger = logging.getLogger(__name__)

# يحمي _custom_data + الحفظ للملف من تداخل تعديلين متزامنين (مثلاً المطور
# يعدّل نص عربي بنفس اللحظة اللي load_custom_texts_into_memory شغالة، أو
# عدة workers تقرأ/تكتب بالتوازي).
_lock = threading.Lock()

CUSTOM_TEXTS_FILE = os.path.join(config.DATA_DIR, "custom_texts.json")

# البنية:
# {
#   "VAR_NAME": {
#     "value": "القيمة المخصصة",
#     "updated_at": 1735900000.0,
#     "editor_id": 123456,
#     "editor_name": "أحمد"
#   },
#   ...
# }

_custom_data: dict[str, dict[str, Any]] = {}


def _load() -> None:
    """تحميل البيانات من الملف."""
    global _custom_data
    if os.path.exists(CUSTOM_TEXTS_FILE):
        try:
            with open(CUSTOM_TEXTS_FILE, "r", encoding="utf-8") as f:
                _custom_data = json.load(f)
                logger.info(f"✅ تم تحميل {len(_custom_data)} نص مخصص")
        except Exception:
            logger.exception("❌ فشل تحميل ملف النصوص المخصصة")
            _custom_data = {}
    else:
        _custom_data = {}


def _save() -> None:
    """حفظ البيانات للملف."""
    os.makedirs(os.path.dirname(CUSTOM_TEXTS_FILE), exist_ok=True)
    tmp_path = CUSTOM_TEXTS_FILE + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(_custom_data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, CUSTOM_TEXTS_FILE)
    except Exception:
        logger.exception("❌ فشل حفظ ملف النصوص المخصصة")


_load()


def get_custom(var_name: str, default: str | None = None) -> str | None:
    """
    احصل على قيمة النص المخصصة (النسخة النصية الاحتياطية).
    المحتوى الغني، إن وجد، محفوظ بشكل منفصل داخل entry["rich"].
    """
    entry = _custom_data.get(var_name)
    if entry:
        return entry.get("value", default)
    return default


def get_custom_rich(var_name: str) -> dict | None:
    """أرجع محتوى Rich Message المحفوظ للمتغير، أو None للنص العادي."""
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
    """
    احفظ نص مخصص.

    ``value`` يبقى دائمًا كنسخة نصية احتياطية حتى تبقى كل أجزاء البوت
    التي تتوقع ``str`` متوافقة. إذا كان المحتوى Rich Message، يُحفظ تمثيله
    الخام في ``rich`` ويُستخدم عند الإرسال في سياق يدعم Rich Messages.
    """
    entry = {
        "value": value,
        "updated_at": time.time(),
        "editor_id": editor_id,
        "editor_name": editor_name,
    }
    if rich is not None:
        entry["rich"] = rich
    else:
        # عند تحويل الرسالة من Rich إلى نص عادي لا نبقي المحتوى القديم.
        entry.pop("rich", None)
    with _lock:
        _custom_data[var_name] = entry
        _save()
    logger.info(f"✅ تم حفظ نص مخصص: {var_name}")


def delete_custom(var_name: str) -> bool:
    """احذف نص مخصص (أعده للافتراضي)."""
    with _lock:
        existed = var_name in _custom_data
        _custom_data.pop(var_name, None)
        if existed:
            _save()
    if existed:
        logger.info(f"🗑️ تم حذف النص المخصص: {var_name}")
    return existed


def list_custom() -> dict[str, Any]:
    """أرجع قائمة كل النصوص المخصصة."""
    return dict(_custom_data)


def reset_all() -> None:
    """احذف كل النصوص المخصصة (أعدها للافتراضي)."""
    with _lock:
        _custom_data.clear()
        _save()
    logger.info("🔄 تم حذف كل النصوص المخصصة")


def get_custom_or_default(var_name: str, texts_module_ref) -> str:
    """
    احصل على النص — أولاً من custom_texts.json، لو ما موجود من texts.py
    
    الاستخدام:
        from custom_texts import get_custom_or_default
        from texts import MSG_WELCOME  # الافتراضي
        
        text = get_custom_or_default("MSG_WELCOME", texts_module)
    """
    # جرّب من المخصصة أولاً
    custom_value = get_custom(var_name)
    if custom_value is not None:
        return custom_value
    
    # لو ما موجودة، استرجع من texts.py
    try:
        return getattr(texts_module_ref, var_name, "")
    except AttributeError:
        logger.warning(f"⚠️ المتغيّر {var_name} غير موجود بـ texts.py")
        return ""
