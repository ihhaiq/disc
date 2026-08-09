"""
حدود الاستخدام اليومي المجاني + إدارة اشتراك نجوم تليكرام (Stars/XTR)
+ القائمة البيضاء (استثناء أشخاص من كل القيود).

يخزّن كل شيء بملف JSON بسيط داخل config.DATA_DIR (لازم يكون مجلد دائم
مربوط بـ Railway Volume، وإلا البيانات تنمسح مع كل ديبلوي).
"""

import json
import logging
import os
import time

import config

logger = logging.getLogger(__name__)

_USAGE_FILE = os.path.join(config.DATA_DIR, "usage_limits.json")

DAY_SECONDS = 24 * 60 * 60

# البنية بالذاكرة:
# {
#   "123456": {"count": 2, "window_start": 1735900000.0, "premium_until": 0.0},
#   "_whitelist": {"987654": {"added_at": 1735900000.0, "note": ""}},
#   ...
# }
_data: dict[str, dict] = {}

_WHITELIST_KEY = "_whitelist"


def _load() -> None:
    global _data
    if os.path.exists(_USAGE_FILE):
        try:
            with open(_USAGE_FILE, "r", encoding="utf-8") as f:
                _data = json.load(f)
        except Exception:
            logger.exception("فشل تحميل ملف حدود الاستخدام، سيتم البدء بملف جديد")
            _data = {}
    else:
        _data = {}


def _save() -> None:
    os.makedirs(os.path.dirname(_USAGE_FILE), exist_ok=True)
    tmp_path = _USAGE_FILE + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(_data, f)
        os.replace(tmp_path, _USAGE_FILE)
    except Exception:
        logger.exception("فشل حفظ ملف حدود الاستخدام")


_load()


def _entry(uid: int) -> dict:
    key = str(uid)
    e = _data.get(key)
    if e is None:
        e = {"count": 0, "window_start": time.time(), "premium_until": 0.0}
        _data[key] = e
    return e


def _reset_if_needed(uid: int) -> dict:
    e = _entry(uid)
    now = time.time()
    if now - e.get("window_start", 0.0) >= DAY_SECONDS:
        e["count"] = 0
        e["window_start"] = now
    return e


def is_premium(uid: int) -> bool:
    e = _entry(uid)
    return time.time() < e.get("premium_until", 0.0)


def get_daily_limit(uid: int) -> int:
    return config.PREMIUM_DAILY_LIMIT if is_premium(uid) else config.FREE_DAILY_LIMIT


def get_count(uid: int) -> int:
    e = _reset_if_needed(uid)
    return e.get("count", 0)


def can_create(uid: int) -> bool:
    if is_whitelisted(uid):
        return True
    return get_count(uid) < get_daily_limit(uid)


def get_reset_seconds(uid: int) -> float:
    """كم ثانية باقية إلى ما تتصفّر الحصة اليومية."""
    e = _reset_if_needed(uid)
    remaining = DAY_SECONDS - (time.time() - e.get("window_start", 0.0))
    return max(0.0, remaining)


def record_usage(uid: int) -> None:
    e = _reset_if_needed(uid)
    e["count"] = e.get("count", 0) + 1
    _save()


def activate_subscription(uid: int, days: int) -> None:
    """يفعّل/يمدّد الاشتراك المدفوع بنجوم تليكرام لعدد أيام معيّن."""
    e = _entry(uid)
    now = time.time()
    current_until = e.get("premium_until", 0.0)
    base = current_until if current_until > now else now
    e["premium_until"] = base + days * DAY_SECONDS
    _save()


def get_subscription_remaining_seconds(uid: int) -> float:
    e = _entry(uid)
    return max(0.0, e.get("premium_until", 0.0) - time.time())


# --- القائمة البيضاء ---

def _whitelist_dict() -> dict:
    return _data.setdefault(_WHITELIST_KEY, {})


def is_whitelisted(uid: int) -> bool:
    return str(uid) in _whitelist_dict()


def add_whitelist(uid: int, note: str = "") -> None:
    wl = _whitelist_dict()
    wl[str(uid)] = {"added_at": time.time(), "note": note}
    _save()


def remove_whitelist(uid: int) -> bool:
    wl = _whitelist_dict()
    existed = str(uid) in wl
    wl.pop(str(uid), None)
    if existed:
        _save()
    return existed


def list_whitelist() -> list[int]:
    wl = _whitelist_dict()
    return [int(k) for k in wl.keys()]


# --- الألوان المدفوعة (Premium-only vinyl colors) ---
# نفس فكرة القائمة البيضاء بالضبط: قاموس بمفتاح ثابت داخل نفس ملف JSON
# الدائم، يخزّن أسماء ألوان الأقراص (قيم developer_vinyl_choice، مثل
# "pink"، "kiss"، "default"...) اللي المطور قفلها بحيث ما تشتغل إلا
# للمستخدمين المشتركين (is_premium) أو القائمة البيضاء أو المطور نفسه.

_PREMIUM_COLORS_KEY = "_premium_colors"


def _premium_colors_dict() -> dict:
    return _data.setdefault(_PREMIUM_COLORS_KEY, {})


def is_premium_color(color: str) -> bool:
    return color in _premium_colors_dict()


def toggle_premium_color(color: str) -> bool:
    """يبدّل حالة اللون بين مجاني/مدفوع. يرجّع الحالة الجديدة (True = صار مدفوع)."""
    pc = _premium_colors_dict()
    if color in pc:
        pc.pop(color, None)
        _save()
        return False
    pc[color] = {"added_at": time.time()}
    _save()
    return True


def list_premium_colors() -> list[str]:
    return list(_premium_colors_dict().keys())
