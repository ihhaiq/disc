"""Usage limits, Telegram Stars access, and the developer whitelist."""

import os
import threading
import time

import config
from storage import JsonStore

_lock = threading.RLock()

_USAGE_FILE = os.path.join(config.DATA_DIR, "usage_limits.json")
_store = JsonStore(_USAGE_FILE, indent=None)

DAY_SECONDS = 24 * 60 * 60

_data: dict[str, dict] = _store.read()
_reserved_counts: dict[int, int] = {}

_WHITELIST_KEY = "_whitelist"


def _save() -> None:
    _store.write(_data)


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
    with _lock:
        return time.time() < _entry(uid).get("premium_until", 0.0)


def get_daily_limit(uid: int) -> int:
    return config.PREMIUM_DAILY_LIMIT if is_premium(uid) else config.FREE_DAILY_LIMIT


def get_count(uid: int) -> int:
    with _lock:
        e = _reset_if_needed(uid)
        return e.get("count", 0)


def can_create(uid: int) -> bool:
    with _lock:
        used_and_reserved = get_count(uid) + _reserved_counts.get(uid, 0)
        return is_whitelisted(uid) or used_and_reserved < get_daily_limit(uid)


def get_reset_seconds(uid: int) -> float:
    """كم ثانية باقية إلى ما تتصفّر الحصة اليومية."""
    with _lock:
        e = _reset_if_needed(uid)
        remaining = DAY_SECONDS - (time.time() - e.get("window_start", 0.0))
        return max(0.0, remaining)


def reserve_usage(uid: int) -> bool:
    """Reserve capacity for an accepted job without charging failed work."""
    with _lock:
        if is_whitelisted(uid):
            return True
        if not can_create(uid):
            return False
        _reserved_counts[uid] = _reserved_counts.get(uid, 0) + 1
        return True


def commit_reserved_usage(uid: int) -> bool:
    """Convert one live reservation into a persisted successful use."""
    with _lock:
        reserved = _reserved_counts.get(uid, 0)
        if reserved <= 0:
            return False
        if reserved == 1:
            _reserved_counts.pop(uid, None)
        else:
            _reserved_counts[uid] = reserved - 1
        e = _reset_if_needed(uid)
        e["count"] = e.get("count", 0) + 1
        _save()
        return True


def release_reserved_usage(uid: int) -> bool:
    """Release one reservation after cancellation or failed processing."""
    with _lock:
        reserved = _reserved_counts.get(uid, 0)
        if reserved <= 0:
            return False
        if reserved == 1:
            _reserved_counts.pop(uid, None)
        else:
            _reserved_counts[uid] = reserved - 1
        return True


def activate_subscription(uid: int, days: int) -> None:
    """Activate a subscription or extend its current expiry."""
    with _lock:
        e = _entry(uid)
        now = time.time()
        current_until = e.get("premium_until", 0.0)
        base = current_until if current_until > now else now
        e["premium_until"] = base + days * DAY_SECONDS
        _save()


def _whitelist_dict() -> dict:
    return _data.setdefault(_WHITELIST_KEY, {})


def is_whitelisted(uid: int) -> bool:
    with _lock:
        return str(uid) in _whitelist_dict()


def add_whitelist(uid: int, note: str = "") -> None:
    with _lock:
        wl = _whitelist_dict()
        wl[str(uid)] = {"added_at": time.time(), "note": note}
        _save()


def remove_whitelist(uid: int) -> bool:
    with _lock:
        wl = _whitelist_dict()
        existed = str(uid) in wl
        wl.pop(str(uid), None)
        if existed:
            _save()
        return existed


def list_whitelist() -> list[int]:
    with _lock:
        return [int(key) for key in _whitelist_dict()]


_PREMIUM_COLORS_KEY = "_premium_colors"


def _premium_colors_dict() -> dict:
    return _data.setdefault(_PREMIUM_COLORS_KEY, {})


def is_premium_color(color: str) -> bool:
    with _lock:
        return color in _premium_colors_dict()


def toggle_premium_color(color: str) -> bool:
    """Toggle a color and return whether it is now premium-only."""
    with _lock:
        pc = _premium_colors_dict()
        if color in pc:
            pc.pop(color, None)
            _save()
            return False
        pc[color] = {"added_at": time.time()}
        _save()
        return True
