# Copyright 2026 Primel Jayawardana
# SPDX-License-Identifier: Apache-2.0

"""
smartcache — Usage examples.
Run: python examples/usage.py
"""

import time
from smartcache import SmartCache, cached, cached_method

# ─── 1. Basic get/set ────────────────────────────────────────────────────────

print("=== 1. Basic Usage ===")
cache: SmartCache[str, int] = SmartCache(capacity=128, policy="lru")

cache.set("user:42:score", 9500)
print(cache.get("user:42:score"))  # 9500

cache["user:99:score"] = 8200       # dict-style set
print(cache["user:99:score"])       # 8200

print("user:42:score" in cache)     # True
del cache["user:42:score"]
print("user:42:score" in cache)     # False

# ─── 2. TTL ──────────────────────────────────────────────────────────────────

print("\n=== 2. TTL ===")
ttl_cache: SmartCache[str, str] = SmartCache(capacity=64, default_ttl=1.0)

ttl_cache.set("session:abc", "user-data")
print(ttl_cache.get("session:abc"))  # user-data

time.sleep(1.1)
print(ttl_cache.get("session:abc"))  # None — expired

# Override default TTL per entry
ttl_cache.set("session:xyz", "persistent", ttl=None)
time.sleep(0.2)
print(ttl_cache.get("session:xyz"))  # still there

# ─── 3. Statistics ───────────────────────────────────────────────────────────

print("\n=== 3. Statistics ===")
stats_cache: SmartCache[str, int] = SmartCache(capacity=10)
for i in range(5):
    stats_cache.set(f"key:{i}", i)
for i in range(3):
    stats_cache.get(f"key:{i}")   # 3 hits
stats_cache.get("missing")        # 1 miss

s = stats_cache.stats()
print(s)
print(f"Hit rate: {s.hit_rate_pct}")

# ─── 4. LFU policy ───────────────────────────────────────────────────────────

print("\n=== 4. LFU Eviction ===")
lfu: SmartCache[str, int] = SmartCache(capacity=3, policy="lfu")
lfu.set("a", 1)
lfu.set("b", 2)
lfu.set("c", 3)

# Access a and b more frequently
for _ in range(5):
    lfu.get("a")
for _ in range(3):
    lfu.get("b")

# Adding d will evict c (lowest frequency)
lfu.set("d", 4)
print(lfu.get("c"))  # None — evicted
print(lfu.get("a"))  # 1 — still there

# ─── 5. @cached decorator ────────────────────────────────────────────────────

print("\n=== 5. @cached Decorator ===")

@cached(ttl=60, capacity=512, policy="lru")
def fetch_weather(city: str) -> dict:
    print(f"  [API call] fetching weather for {city}")
    time.sleep(0.01)  # simulate network
    return {"city": city, "temp": 18}

result1 = fetch_weather("Calgary")   # API called
result2 = fetch_weather("Calgary")   # served from cache
result3 = fetch_weather("Edmonton")  # API called (different key)

print(f"Requests saved: {fetch_weather.cache_stats().hits}")

# Manual cache invalidation
fetch_weather.cache_delete("Calgary")
result4 = fetch_weather("Calgary")  # API called again

# ─── 6. @cached_method ───────────────────────────────────────────────────────

print("\n=== 6. @cached_method ===")

class ProductService:
    def __init__(self, name: str):
        self.name = name
        self._calls = 0

    @cached_method(ttl=120)
    def get_price(self, product_id: int) -> float:
        self._calls += 1
        return product_id * 9.99

svc1 = ProductService("store-A")
svc2 = ProductService("store-B")

print(svc1.get_price(101))  # computed
print(svc1.get_price(101))  # cached
print(svc2.get_price(101))  # computed — separate instance cache

print(f"svc1 DB calls: {svc1._calls}")  # 1
print(f"svc2 DB calls: {svc2._calls}")  # 1

# ─── 7. get_or_set (cache-aside pattern) ─────────────────────────────────────

print("\n=== 7. Cache-Aside Pattern ===")
aside_cache: SmartCache[int, dict] = SmartCache(capacity=256)

def load_user_from_db(user_id: int) -> dict:
    print(f"  [DB] loading user {user_id}")
    return {"id": user_id, "name": f"User {user_id}"}

user = aside_cache.get_or_set(42, lambda: load_user_from_db(42), ttl=300)
print(user)
user_again = aside_cache.get_or_set(42, lambda: load_user_from_db(42))
print(user_again)  # served from cache, no DB call

# ─── 8. Background expiry ────────────────────────────────────────────────────

print("\n=== 8. Auto-Expire Background Thread ===")
with SmartCache(capacity=100, default_ttl=0.1, auto_expire_interval=0.05) as bg_cache:
    for i in range(10):
        bg_cache.set(f"tmp:{i}", i)
    print(f"Size before expiry: {len(bg_cache)}")  # 10
    time.sleep(0.2)
    print(f"Size after auto-expiry: {len(bg_cache)}")  # 0
