"""SQLite-backed response cache for API calls."""

import hashlib
import json
import pickle
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Optional


class ResponseCache:
    """Cache API responses in SQLite for resume-on-failure."""

    def __init__(self, db_path: Optional[str] = None, ttl_hours: float = 24 * 7):
        self.db_path = db_path or str(Path.cwd() / ".aeris_exposure_cache.db")
        self.ttl_seconds = ttl_hours * 3600
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._create_table()

    def _create_table(self):
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value BLOB,
                    created_at REAL
                )
            """)
            self._conn.commit()

    @staticmethod
    def _make_key(**kwargs) -> str:
        raw = json.dumps(kwargs, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, **kwargs) -> Optional[Any]:
        key = self._make_key(**kwargs)
        with self._lock:
            row = self._conn.execute(
                "SELECT value, created_at FROM cache WHERE key = ?", (key,)
            ).fetchone()
            if row is None:
                return None
            if time.time() - row[1] <= self.ttl_seconds:
                return pickle.loads(row[0])
            self._conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            self._conn.commit()
        return None

    def put(self, value: Any, **kwargs):
        key = self._make_key(**kwargs)
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, created_at) VALUES (?, ?, ?)",
                (key, pickle.dumps(value), time.time()),
            )
            self._conn.commit()

    def clear(self):
        with self._lock:
            self._conn.execute("DELETE FROM cache")
            self._conn.commit()

    def close(self):
        with self._lock:
            self._conn.close()
