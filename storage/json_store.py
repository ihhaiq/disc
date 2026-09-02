"""Small, thread-safe and atomic JSON object store."""

import json
import logging
import os
import threading
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

ResultT = TypeVar("ResultT")
JsonObject = dict[str, Any]


class JsonStore:
    """Persist a JSON object without exposing partial writes to readers."""

    def __init__(self, path: str | os.PathLike[str], *, indent: int | None = 2):
        self.path = Path(path)
        self.indent = indent
        self._lock = threading.RLock()

    def _read_unlocked(self, default: JsonObject | None = None) -> JsonObject:
        fallback = deepcopy(default) if default is not None else {}
        if not self.path.exists():
            return fallback
        try:
            with self.path.open("r", encoding="utf-8") as file:
                value = json.load(file)
            if not isinstance(value, dict):
                raise TypeError("the JSON root must be an object")
            return value
        except (OSError, ValueError, TypeError):
            logger.exception("Failed to read JSON store: %s", self.path)
            return fallback

    def read(self, default: JsonObject | None = None) -> JsonObject:
        with self._lock:
            return self._read_unlocked(default)

    def _write_unlocked(self, data: JsonObject) -> bool:
        temporary_path = self.path.with_name(f"{self.path.name}.tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with temporary_path.open("w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=self.indent)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_path, self.path)
            return True
        except (OSError, TypeError):
            logger.exception("Failed to write JSON store: %s", self.path)
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Failed to remove temporary JSON file: %s", temporary_path)
            return False

    def write(self, data: JsonObject) -> bool:
        with self._lock:
            return self._write_unlocked(data)

    def update(
        self,
        mutator: Callable[[JsonObject], ResultT],
        *,
        default: JsonObject | None = None,
    ) -> ResultT:
        """Apply a read-modify-write operation under one lock."""
        with self._lock:
            data = self._read_unlocked(default)
            result = mutator(data)
            self._write_unlocked(data)
            return result
