"""
File utilities for atomic writes with advisory file locking.
"""

import fcntl
import json
import os
import tempfile
from typing import Any, Dict


def _atomic_write(file_path: str, write_fn) -> None:
    """Core atomic write: lock, temp file, os.replace().

    Args:
        file_path: Target file path.
        write_fn: Callable(file_obj) that writes content to the temp file.
    """
    dir_path = os.path.dirname(file_path)
    os.makedirs(dir_path, exist_ok=True)
    lock_path = file_path + ".lock"

    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)

        temp_fd, temp_path = tempfile.mkstemp(dir=dir_path, suffix='.tmp')
        try:
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                write_fn(f)
            os.replace(temp_path, file_path)
        except:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)
        try:
            os.unlink(lock_path)
        except OSError:
            pass  # Another process may have already removed it


def atomic_write_json(file_path: str, data: Dict[str, Any]) -> None:
    """Write JSON data atomically with advisory file locking."""
    _atomic_write(file_path, lambda f: json.dump(data, f, ensure_ascii=False, indent=2))


def atomic_write_text(file_path: str, text: str) -> None:
    """Write text data atomically with advisory file locking."""
    _atomic_write(file_path, lambda f: f.write(text))
