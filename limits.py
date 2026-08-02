import json
import os

import config

FREE_LIMIT = 3
_USAGE_FILE = os.path.join(config.TEMP_DIR, "usage_limits.json")

_usage: dict[int, int] = {}


def _load() -> None:
    global _usage
    if os.path.exists(_USAGE_FILE):
        try:
            with open(_USAGE_FILE, "r", encoding="utf-8") as f:
                _usage = {int(k): v for k, v in json.load(f).items()}
        except Exception:
            _usage = {}


def _save() -> None:
    os.makedirs(os.path.dirname(_USAGE_FILE), exist_ok=True)
    try:
        with open(_USAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(_usage, f)
    except Exception:
        pass


_load()


def get_count(user_id: int) -> int:
    return _usage.get(user_id, 0)


def can_create(user_id: int, limit: int = FREE_LIMIT) -> bool:
    return get_count(user_id) < limit


def record_creation(user_id: int) -> None:
    _usage[user_id] = get_count(user_id) + 1
    _save()


def remaining(user_id: int, limit: int = FREE_LIMIT) -> int:
    return max(0, limit - get_count(user_id))