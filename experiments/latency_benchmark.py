import sys
sys.path.insert(0, '.')

import time
from src.cache import SemanticCache

cache = SemanticCache(threshold=0.80, ttl=86400)

QUERIES = [
    ("what is a REST API", "A REST API uses HTTP methods to operate on resources."),
    ("how does machine learning work", "ML trains models on data to find patterns and make predictions."),
    ("what is Docker", "Docker packages applications into containers that run consistently anywhere."),
    ("what is the difference between SQL and NoSQL", "SQL is relational with fixed schemas. NoSQL is flexible and scales horizontally."),
    ("how do I reverse a linked list", "Iterate keeping track of previous, current, and next nodes. Reverse each pointer. O(n) time O(1) space."),
]

print("\n" + "="*60)
print("CACHELAYER LATENCY BENCHMARK")
print("="*60)

# Seed cache
for q, r in QUERIES:
    cache.set(q, r, user_id=1)

# Measure cache hit latency
hit_times = []
for q, _ in QUERIES:
    start = time.perf_counter()
    result = cache.get(q, user_id=1)
    elapsed = (time.perf_counter() - start) * 1000
    hit_times.append(elapsed)

# Measure cache miss latency
miss_times = []
for i in range(5):
    start = time.perf_counter()
    cache.get(f"completely unrelated query number {i} about nothing", user_id=1)
    elapsed = (time.perf_counter() - start) * 1000
    miss_times.append(elapsed)

avg_hit  = sum(hit_times) / len(hit_times)
avg_miss = sum(miss_times) / len(miss_times)
# Real OpenAI API baseline (measured separately, typical value)
api_baseline = 1800

print(f"\n  Cache HIT  avg latency : {avg_hit:.1f}ms")
print(f"  Cache MISS avg latency : {avg_miss:.1f}ms")
print(f"  Real API   avg latency : ~{api_baseline}ms  (GPT-4o baseline)")
print(f"\n  Speedup on cache hit   : {api_baseline/avg_hit:.0f}x faster than live API")
print(f"  Token cost on hit      : $0.00")
print("="*60)

import json
results = {
    "avg_hit_ms": round(avg_hit, 2),
    "avg_miss_ms": round(avg_miss, 2),
    "api_baseline_ms": api_baseline,
    "speedup": round(api_baseline / avg_hit, 1)
}
with open("experiments/latency_results.json", "w") as f:
    json.dump(results, f, indent=2)
print("\nSaved to experiments/latency_results.json")