import json
import logging
import os
import time

import config

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(config.BASE_DIR, "data")
DATA_PATH = os.path.join(DATA_DIR, "usage.json")

DAY_SECONDS = 24 * 60 * 60

_data: dict[str, dict] = {}


def _load() -> None:
    global _data
    if os.path.exists(DATA_PATH):
        try:
            with open(DATA_PATH, "r", encoding="utf-8") as f:
                _data = json.load(f)
        except Exception:
            logger.exception("فشل تحميل ملف بيانات الاستخدام، سيتم البدء بملف جديد")
            _data = {}
    else:
        _data = {}


def _save() -> None:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp_path = DATA_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(_data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, DATA_PATH)
    except Exception:
        logger.exception("فشل حفظ ملف بيانات الاستخدام")


_load()


def _entry(uid: int) -> dict:
    key = str(uid)
    e = _data.get(key)
    if e is None:
        e = {"count": 0, "window_start": time.time(), "premium_until": 0}
        _data[key] = e
    return e


def _reset_window_if_needed(entry: dict) -> None:
    if time.time() - entry.get("window_start", 0) >= DAY_SECONDS:
        entry["count"] = 0
        entry["window_start"] = time.time()


def is_premium(uid: int) -> bool:
    return time.time() < _entry(uid).get("premium_until", 0)


def get_daily_limit(uid: int) -> int:
    return config.PREMIUM_DAILY_LIMIT if is_premium(uid) else config.FREE_DAILY_LIMIT


def get_remaining(uid: int) -> int:
    entry = _entry(uid)
    _reset_window_if_needed(entry)
    return max(0, get_daily_limit(uid) - entry["count"])


def get_reset_seconds(uid: int) -> int:
    entry = _entry(uid)
    elapsed = time.time() - entry.get("window_start", 0)
    return max(0, int(DAY_SECONDS - elapsed))


def can_create(uid: int) -> bool:
    return get_remaining(uid) > 0


def record_usage(uid: int) -> None:
    entry = _entry(uid)
    _reset_window_if_needed(entry)
    entry["count"] += 1
    _save()


def activate_subscription(uid: int, days: int) -> None:
    entry = _entry(uid)
    now = time.time()
    base = entry.get("premium_until", 0)
    start = base if base > now else now
    entry["premium_until"] = start + days * DAY_SECONDS
    _save()
