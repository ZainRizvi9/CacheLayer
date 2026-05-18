import sys
sys.path.insert(0, '.')

from src.cache import SemanticCache
from src.embedder import similarity, embed
import json
import time

# 50 realistic LLM queries across 3 domains
# Each group has paraphrased versions of the same question
QUERIES = [
    # NBA / Sports (10 unique questions, 2 phrasings each)
    ("what are the best NBA players right now", "who are the top players in the NBA currently"),
    ("how many championships did LeBron James win", "how many NBA titles does LeBron have"),
    ("who won the NBA finals last year", "which team was NBA champion most recently"),
    ("what is Nikola Jokic's playing style", "how does Nikola Jokic play basketball"),
    ("who is the highest paid NBA player", "which NBA player earns the most money"),

    # Finance (10 unique questions, 2 phrasings each)
    ("what is the current interest rate in Canada", "what is the Bank of Canada interest rate"),
    ("how do I open a TFSA account", "what are the steps to open a TFSA"),
    ("what is the difference between RRSP and TFSA", "RRSP vs TFSA which is better"),
    ("how does compound interest work", "explain compound interest to me"),
    ("what stocks should I invest in right now", "which stocks are good investments today"),

    # General Tech (10 unique questions, 2 phrasings each)
    ("what is a REST API", "explain what REST APIs are"),
    ("how does machine learning work", "what is machine learning and how does it work"),
    ("what is the difference between SQL and NoSQL", "SQL vs NoSQL databases comparison"),
    ("how do I reverse a linked list", "what is the algorithm to reverse a linked list"),
    ("what is Docker and why use it", "explain Docker containers and their purpose"),
]

FAKE_RESPONSES = {
    "what are the best NBA players right now": "LeBron James, Nikola Jokic, and Stephen Curry are widely considered the best NBA players.",
    "how many championships did LeBron James win": "LeBron James has won 4 NBA championships: 2012, 2013 with Miami Heat, 2016 with Cleveland, and 2020 with Lakers.",
    "who won the NBA finals last year": "The Boston Celtics won the 2024 NBA Finals, defeating the Dallas Mavericks 4-1.",
    "what is Nikola Jokic's playing style": "Nikola Jokic is a pass-first center with elite playmaking, shooting, and basketball IQ.",
    "who is the highest paid NBA player": "Stephen Curry is one of the highest paid NBA players at over $50 million per year.",
    "what is the current interest rate in Canada": "The Bank of Canada's policy rate is 4.25% as of late 2024.",
    "how do I open a TFSA account": "You can open a TFSA at any major Canadian bank or credit union with valid ID and SIN.",
    "what is the difference between RRSP and TFSA": "RRSP contributions are tax-deductible but withdrawals are taxed. TFSA contributions are after-tax but withdrawals are tax-free.",
    "how does compound interest work": "Compound interest means you earn interest on your interest. $1000 at 5% compounded annually becomes $1628 after 10 years.",
    "what stocks should I invest in right now": "Diversified index funds like VFV or XEQT are generally recommended for long-term investing.",
    "what is a REST API": "A REST API is a web service that uses HTTP methods (GET, POST, PUT, DELETE) to perform operations on resources identified by URLs.",
    "how does machine learning work": "Machine learning trains models on data to find patterns, then uses those patterns to make predictions on new data.",
    "what is the difference between SQL and NoSQL": "SQL databases are relational with fixed schemas. NoSQL databases are flexible and scale horizontally for unstructured data.",
    "how do I reverse a linked list": "Iterate through the list keeping track of previous, current, and next nodes. Reverse each pointer as you go. O(n) time, O(1) space.",
    "what is Docker and why use it": "Docker packages applications into containers that run consistently across any environment, solving the 'works on my machine' problem.",
}

def run_benchmark(threshold: float) -> dict:
    cache = SemanticCache(threshold=threshold, ttl=86400)

    # Seed cache with first phrasing of each question
    for q1, q2 in QUERIES:
        cache.set(q1, FAKE_RESPONSES[q1])

    # Query with second phrasing — these are paraphrases, should hit cache
    hits = 0
    misses = 0
    latencies_hit = []
    latencies_miss = []

    for q1, q2 in QUERIES:
        start = time.time()
        result = cache.get(q2)
        elapsed = (time.time() - start) * 1000  # ms

        if result is not None:
            hits += 1
            latencies_hit.append(elapsed)
        else:
            misses += 1
            latencies_miss.append(elapsed)

    total = hits + misses
    hit_rate = hits / total
    avg_latency_hit  = sum(latencies_hit)  / len(latencies_hit)  if latencies_hit  else 0
    avg_latency_miss = sum(latencies_miss) / len(latencies_miss) if latencies_miss else 0

    # Cost calculation: GPT-4o is $0.000005 per token output
    # Average response ~50 tokens, average query ~10 tokens
    tokens_per_query = 60
    cost_per_query   = tokens_per_query * 0.000005
    cost_saved       = hits * cost_per_query
    cost_full        = total * cost_per_query

    return {
        "threshold":        threshold,
        "total_queries":    total,
        "hits":             hits,
        "misses":           misses,
        "hit_rate":         round(hit_rate, 3),
        "tokens_saved":     hits * tokens_per_query,
        "cost_saved_usd":   round(cost_saved, 4),
        "cost_full_usd":    round(cost_full, 4),
        "savings_pct":      round(hit_rate * 100, 1),
        "avg_latency_hit_ms":  round(avg_latency_hit, 1),
        "avg_latency_miss_ms": round(avg_latency_miss, 1),
    }

if __name__ == "__main__":
    thresholds = [0.70, 0.75, 0.80, 0.85, 0.90, 0.95]

    print("\n" + "="*80)
    print("SEMANTIC CACHE BENCHMARK — Threshold vs Hit Rate Analysis")
    print("="*80)
    print(f"{'Threshold':>10} {'Hit Rate':>10} {'Hits':>6} {'Misses':>8} {'Tokens Saved':>14} {'Cost Saved':>12} {'Savings %':>10}")
    print("-"*80)

    results = []
    for t in thresholds:
        r = run_benchmark(t)
        results.append(r)
        print(f"{r['threshold']:>10.2f} {r['hit_rate']:>10.3f} {r['hits']:>6} {r['misses']:>8} {r['tokens_saved']:>14} ${r['cost_saved_usd']:>11.4f} {r['savings_pct']:>9.1f}%")

    print("="*80)

    # Save results
    with open("experiments/results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nResults saved to experiments/results.json")