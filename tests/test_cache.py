"""
Tests for the SQLite response cache.
"""

import time
from concurrent.futures import ThreadPoolExecutor

from aeris.exposure.cache import ResponseCache


class TestResponseCache:
    """Test ResponseCache get/put/clear/TTL."""

    def test_put_and_get(self, tmp_path):
        db = str(tmp_path / "test.db")
        cache = ResponseCache(db_path=db)
        cache.put({"hello": "world"}, endpoint="test", key="abc")
        result = cache.get(endpoint="test", key="abc")
        assert result == {"hello": "world"}
        cache.close()

    def test_get_miss(self, tmp_path):
        db = str(tmp_path / "test.db")
        cache = ResponseCache(db_path=db)
        result = cache.get(endpoint="test", key="nonexistent")
        assert result is None
        cache.close()

    def test_ttl_expiry(self, tmp_path):
        db = str(tmp_path / "test.db")
        cache = ResponseCache(db_path=db, ttl_hours=0)  # 0 hour TTL = immediate expiry
        cache.put("value", endpoint="test", key="expire")
        time.sleep(0.1)
        result = cache.get(endpoint="test", key="expire")
        assert result is None
        cache.close()

    def test_clear(self, tmp_path):
        db = str(tmp_path / "test.db")
        cache = ResponseCache(db_path=db)
        cache.put("a", endpoint="test", key="1")
        cache.put("b", endpoint="test", key="2")
        cache.clear()
        assert cache.get(endpoint="test", key="1") is None
        assert cache.get(endpoint="test", key="2") is None
        cache.close()

    def test_key_determinism(self, tmp_path):
        """Same kwargs produce the same cache key."""
        key1 = ResponseCache._make_key(endpoint="test", lat=1.0, lon=2.0)
        key2 = ResponseCache._make_key(endpoint="test", lat=1.0, lon=2.0)
        assert key1 == key2

    def test_key_different_for_different_params(self, tmp_path):
        key1 = ResponseCache._make_key(endpoint="test", lat=1.0)
        key2 = ResponseCache._make_key(endpoint="test", lat=2.0)
        assert key1 != key2

    def test_pickle_roundtrip_list(self, tmp_path):
        db = str(tmp_path / "test.db")
        cache = ResponseCache(db_path=db)
        data = [{"a": 1}, {"b": [2, 3]}]
        cache.put(data, endpoint="list_test")
        result = cache.get(endpoint="list_test")
        assert result == data
        cache.close()

    def test_pickle_roundtrip_none_value(self, tmp_path):
        db = str(tmp_path / "test.db")
        cache = ResponseCache(db_path=db)
        cache.put(None, endpoint="none_test")
        # None is a valid cached value — should return None but from cache
        # We can verify by checking the DB has the row
        row = cache._conn.execute(
            "SELECT key FROM cache WHERE key = ?",
            (ResponseCache._make_key(endpoint="none_test"),),
        ).fetchone()
        assert row is not None
        cache.close()

    def test_overwrite_existing_key(self, tmp_path):
        db = str(tmp_path / "test.db")
        cache = ResponseCache(db_path=db)
        cache.put("first", endpoint="overwrite")
        cache.put("second", endpoint="overwrite")
        result = cache.get(endpoint="overwrite")
        assert result == "second"
        cache.close()

    def test_background_worker_can_share_cache(self, tmp_path):
        cache = ResponseCache(db_path=str(tmp_path / "test.db"))

        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(cache.put, "value", endpoint="threaded").result()
            result = executor.submit(cache.get, endpoint="threaded").result()

        assert result == "value"
        cache.close()
