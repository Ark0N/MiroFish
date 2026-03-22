"""
File utilities for atomic writes with advisory file locking.
"""

import fcntl
import json
import os
import tempfile
from typing import Any, Dict


def atomic_write_json(file_path: str, data: Dict[str, Any]) -> None:
    """Write JSON data atomically with advisory file locking.

    Uses a lock file to prevent concurrent writes, then writes to a
    temp file and atomically replaces the target via os.replace().
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
                json.dump(data, f, ensure_ascii=False, indent=2)
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
