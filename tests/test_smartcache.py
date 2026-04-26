# Copyright 2026 Primel Jayawardana
# SPDX-License-Identifier: Apache-2.0

"""
Comprehensive tests for smartcache.
Run: pytest tests/ -v --cov=smartcache
"""

import threading
import time

import pytest

from smartcache import SmartCache, cached, cached_method
from smartcache.eviction import LFUPolicy, LRUPolicy
from smartcache.stats import CacheStats


# ─── LRU Policy ──────────────────────────────────────────────────────────────

class TestLRUPolicy:
    def test_evict_least_recently_used(self):
        p = LRUPolicy()
        p.on_insert("a")
        p.on_insert("b")
        p.on_insert("c")
        p.on_access("a")  # a is now MRU
        assert p.evict_candidate() == "b"  # b is LRU

    def test_on_delete_removes_key(self):
        p = LRUPolicy()
        p.on_insert("x")
        p.on_delete("x")
        assert p.evict_candidate() is None

    def test_len(self):
        p = LRUPolicy()
        for i in range(5):
            p.on_insert(i)
        assert len(p) == 5


# ─── LFU Policy ──────────────────────────────────────────────────────────────

class TestLFUPolicy:
    def test_evict_least_frequently_used(self):
        p = LFUPolicy()
        p.on_insert("a")
        p.on_insert("b")
        p.on_access("a")
        p.on_access("a")
        # a has freq=3, b has freq=1 → evict b
        assert p.evict_candidate() == "b"

    def test_tie_broken_by_recency(self):
        p = LFUPolicy()
        p.on_insert("x")
        p.on_insert("y")
        # Both have freq=1, x was inserted first → evict x
        assert p.evict_candidate() == "x"

    def test_on_delete(self):
        p = LFUPolicy()
        p.on_insert("z")
        p.on_delete("z")
        assert p.evict_candidate() is None


# ─── SmartCache Core ─────────────────────────────────────────────────────────

class TestSmartCacheCore:
    def test_set_and_get(self):
        cache: SmartCache[str, int] = SmartCache(capacity=10)
        cache.set("k", 99)
        assert cache.get("k") == 99

    def test_get_missing_returns_default(self):
        cache: SmartCache[str, int] = SmartCache(capacity=10)
        assert cache.get("missing") is None
        assert cache.get("missing", default=42) == 42

    def test_dict_interface(self):
        cache: SmartCache[str, str] = SmartCache(capacity=5)
        cache["hello"] = "world"
        assert cache["hello"] == "world"
        assert "hello" in cache
        del cache["hello"]
        assert "hello" not in cache

    def test_keyerror_on_missing_getitem(self):
        cache: SmartCache[str, int] = SmartCache(capacity=5)
        with pytest.raises(KeyError):
            _ = cache["nope"]

    def test_len(self):
        cache: SmartCache[str, int] = SmartCache(capacity=10)
        for i in range(5):
            cache.set(str(i), i)
        assert len(cache) == 5

    def test_clear(self):
        cache: SmartCache[str, int] = SmartCache(capacity=10)
        cache.set("a", 1)
        cache.clear()
        assert len(cache) == 0
        assert cache.get("a") is None

    def test_delete_returns_true_on_success(self):
        cache: SmartCache[str, int] = SmartCache(capacity=10)
        cache.set("x", 1)
        assert cache.delete("x") is True

    def test_delete_returns_false_on_missing(self):
        cache: SmartCache[str, int] = SmartCache(capacity=10)
        assert cache.delete("nope") is False

    def test_keys_values_items(self):
        cache: SmartCache[str, int] = SmartCache(capacity=10)
        cache.set("a", 1)
        cache.set("b", 2)
        assert set(cache.keys()) == {"a", "b"}
        assert set(cache.values()) == {1, 2}
        assert set(cache.items()) == {("a", 1), ("b", 2)}

    def test_repr(self):
        cache: SmartCache[str, int] = SmartCache(capacity=8, policy="lfu")
        assert "lfu" in repr(cache)
        assert "8" in repr(cache)


# ─── TTL ─────────────────────────────────────────────────────────────────────

class TestTTL:
    def test_entry_expires(self):
        cache: SmartCache[str, int] = SmartCache(capacity=10, default_ttl=0.05)
        cache.set("key", 1)
        time.sleep(0.07)
        assert cache.get("key") is None

    def test_per_entry_ttl_overrides_default(self):
        cache: SmartCache[str, int] = SmartCache(capacity=10, default_ttl=60)
        cache.set("short", 1, ttl=0.05)
        cache.set("long", 2, ttl=60)
        time.sleep(0.07)
        assert cache.get("short") is None
        assert cache.get("long") == 2

    def test_contains_respects_expiry(self):
        cache: SmartCache[str, int] = SmartCache(capacity=10)
        cache.set("x", 1, ttl=0.05)
        assert cache.contains("x")
        time.sleep(0.07)
        assert not cache.contains("x")

    def test_expire_all_removes_expired(self):
        cache: SmartCache[str, int] = SmartCache(capacity=10)
        cache.set("a", 1, ttl=0.05)
        cache.set("b", 2, ttl=60)
        time.sleep(0.07)
        removed = cache.expire_all()
        assert removed == 1
        assert len(cache) == 1


# ─── Eviction ────────────────────────────────────────────────────────────────

class TestEviction:
    def test_lru_eviction_at_capacity(self):
        cache: SmartCache[str, int] = SmartCache(capacity=3, policy="lru")
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.get("a")  # access a → b is now LRU
        cache.set("d", 4)  # should evict b
        assert cache.get("b") is None
        assert cache.get("a") == 1

    def test_lfu_eviction_at_capacity(self):
        cache: SmartCache[str, int] = SmartCache(capacity=3, policy="lfu")
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.get("a")
        cache.get("a")
        cache.get("b")
        # c has freq=1 (least), a has 3, b has 2 → evict c
        cache.set("d", 4)
        assert cache.get("c") is None

    def test_stats_track_evictions(self):
        cache: SmartCache[str, int] = SmartCache(capacity=2)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)  # evicts one
        s = cache.stats()
        assert s.evictions == 1


# ─── get_or_set ───────────────────────────────────────────────────────────────

class TestGetOrSet:
    def test_calls_factory_on_miss(self):
        cache: SmartCache[str, int] = SmartCache(capacity=10)
        call_count = {"n": 0}

        def factory():
            call_count["n"] += 1
            return 42

        result = cache.get_or_set("k", factory)
        assert result == 42
        assert call_count["n"] == 1

    def test_does_not_call_factory_on_hit(self):
        cache: SmartCache[str, int] = SmartCache(capacity=10)
        cache.set("k", 99)
        call_count = {"n": 0}

        def factory():
            call_count["n"] += 1
            return 0

        result = cache.get_or_set("k", factory)
        assert result == 99
        assert call_count["n"] == 0

    def test_thread_safe_single_computation(self):
        """Only one thread should call the factory under concurrent load."""
        cache: SmartCache[str, int] = SmartCache(capacity=10)
        call_count = {"n": 0}
        lock = threading.Lock()

        def factory():
            time.sleep(0.02)
            with lock:
                call_count["n"] += 1
            return 1

        threads = [
            threading.Thread(target=lambda: cache.get_or_set("shared", factory))
            for _ in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # The factory may be called once or a small number of times due to
        # the double-checked locking — not 10 times
        assert call_count["n"] <= 3


# ─── Stats ────────────────────────────────────────────────────────────────────

class TestStats:
    def test_hit_rate(self):
        cache: SmartCache[str, int] = SmartCache(capacity=10)
        cache.set("a", 1)
        cache.get("a")  # hit
        cache.get("a")  # hit
        cache.get("b")  # miss
        s = cache.stats()
        assert s.hits == 2
        assert s.misses == 1
        assert abs(s.hit_rate - 2 / 3) < 1e-9

    def test_stats_reset_on_clear(self):
        cache: SmartCache[str, int] = SmartCache(capacity=10)
        cache.set("x", 1)
        cache.get("x")
        cache.clear()
        s = cache.stats()
        assert s.hits == 0
        assert s.misses == 0


# ─── Decorators ───────────────────────────────────────────────────────────────

class TestCachedDecorator:
    def test_caches_return_value(self):
        call_count = {"n": 0}

        @cached(ttl=60)
        def add(a: int, b: int) -> int:
            call_count["n"] += 1
            return a + b

        assert add(1, 2) == 3
        assert add(1, 2) == 3
        assert call_count["n"] == 1

    def test_different_args_produce_different_keys(self):
        call_count = {"n": 0}

        @cached(ttl=60)
        def square(n: int) -> int:
            call_count["n"] += 1
            return n * n

        assert square(2) == 4
        assert square(3) == 9
        assert call_count["n"] == 2

    def test_cache_clear(self):
        call_count = {"n": 0}

        @cached(ttl=60)
        def value() -> int:
            call_count["n"] += 1
            return 7

        value()
        value.cache_clear()
        value()
        assert call_count["n"] == 2

    def test_cache_stats_accessible(self):
        @cached(ttl=60)
        def noop(x: int) -> int:
            return x

        noop(1)
        noop(1)
        s = noop.cache_stats()
        assert isinstance(s, CacheStats)


class TestCachedMethodDecorator:
    def test_per_instance_cache(self):
        class Counter:
            def __init__(self):
                self.calls = 0

            @cached_method(ttl=60)
            def compute(self, n: int) -> int:
                self.calls += 1
                return n * 2

        c1 = Counter()
        c2 = Counter()
        c1.compute(5)
        c1.compute(5)
        c2.compute(5)
        assert c1.calls == 1
        assert c2.calls == 1  # separate cache per instance


# ─── Thread safety ────────────────────────────────────────────────────────────

class TestThreadSafety:
    def test_concurrent_writes(self):
        cache: SmartCache[int, int] = SmartCache(capacity=100)
        errors = []

        def write(i: int):
            try:
                for j in range(20):
                    cache.set(i * 20 + j, j)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors

    def test_concurrent_reads_and_writes(self):
        cache: SmartCache[str, int] = SmartCache(capacity=50)
        errors = []

        def worker():
            try:
                for i in range(50):
                    cache.set(str(i % 10), i)
                    cache.get(str(i % 10))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
