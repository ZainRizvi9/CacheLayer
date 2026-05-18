import time
import numpy as np
from src.embedder import embed, similarity
from dataclasses import dataclass, field

@dataclass
class CacheEntry:
    query: str
    response: str
    embedding: np.ndarray
    timestamp: float
    hits: int = 0

class SemanticCache:
    def __init__(self, threshold: float = 0.80, ttl: int = 3600):
        self.threshold = threshold  # similarity cutoff
        self.ttl = ttl              # seconds before entry expires
        self.entries: list[CacheEntry] = []
        self.total_queries = 0
        self.cache_hits = 0
        self.tokens_saved = 0

    def get(self, query: str) -> str | None:
        self.total_queries += 1
        q_emb = embed(query)
        now = time.time()

        for entry in self.entries:
            # skip expired entries
            if now - entry.timestamp > self.ttl:
                continue
            score = similarity(q_emb, entry.embedding)
            if score >= self.threshold:
                entry.hits += 1
                self.cache_hits += 1
                # estimate tokens saved (rough: 1 token ≈ 4 chars)
                self.tokens_saved += len(entry.response) // 4
                return entry.response
        return None

    def set(self, query: str, response: str) -> None:
        self.entries.append(CacheEntry(
            query     = query,
            response  = response,
            embedding = embed(query),
            timestamp = time.time()
        ))

    def stats(self) -> dict:
        hit_rate = self.cache_hits / self.total_queries if self.total_queries else 0
        return {
            "total_queries": self.total_queries,
            "cache_hits":    self.cache_hits,
            "hit_rate":      round(hit_rate, 3),
            "tokens_saved":  self.tokens_saved,
            "cost_saved_usd": round(self.tokens_saved * 0.000002, 4),  # GPT-4o rate
            "entries":       len(self.entries)
        }