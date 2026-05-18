import time
import sqlite3
import numpy as np
import json
import os
from src.embedder import embed, similarity
from dataclasses import dataclass

DB_PATH = os.getenv("CACHE_DB", "cache.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            query     TEXT NOT NULL,
            response  TEXT NOT NULL,
            embedding TEXT NOT NULL,
            timestamp REAL NOT NULL,
            hits      INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            id             INTEGER PRIMARY KEY CHECK (id = 1),
            total_queries  INTEGER DEFAULT 0,
            cache_hits     INTEGER DEFAULT 0,
            tokens_saved   INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        INSERT OR IGNORE INTO stats (id, total_queries, cache_hits, tokens_saved)
        VALUES (1, 0, 0, 0)
    """)
    conn.commit()
    conn.close()

init_db()

class SemanticCache:
    def __init__(self, threshold: float = 0.80, ttl: int = 3600):
        self.threshold = threshold
        self.ttl = ttl

    def _conn(self):
        return sqlite3.connect(DB_PATH)

    def get(self, query: str) -> str | None:
        q_emb = embed(query)
        now = time.time()

        with self._conn() as conn:
            conn.execute(
                "UPDATE stats SET total_queries = total_queries + 1 WHERE id = 1"
            )
            rows = conn.execute(
                "SELECT id, response, embedding, timestamp FROM cache"
            ).fetchall()

            for row_id, response, emb_json, timestamp in rows:
                if now - timestamp > self.ttl:
                    continue
                emb = np.array(json.loads(emb_json))
                score = similarity(q_emb, emb)
                if score >= self.threshold:
                    tokens = len(response) // 4
                    conn.execute(
                        "UPDATE cache SET hits = hits + 1 WHERE id = ?", (row_id,)
                    )
                    conn.execute("""
                        UPDATE stats
                        SET cache_hits   = cache_hits + 1,
                            tokens_saved = tokens_saved + ?
                        WHERE id = 1
                    """, (tokens,))
                    return response
        return None

    def set(self, query: str, response: str) -> None:
        emb = embed(query)
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO cache (query, response, embedding, timestamp)
                VALUES (?, ?, ?, ?)
            """, (query, response, json.dumps(emb.tolist()), time.time()))

    def stats(self) -> dict:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT total_queries, cache_hits, tokens_saved FROM stats WHERE id = 1"
            ).fetchone()
            entries = conn.execute(
                "SELECT COUNT(*) FROM cache"
            ).fetchone()[0]
            top = conn.execute(
                "SELECT query, hits FROM cache ORDER BY hits DESC LIMIT 5"
            ).fetchall()

        total, hits, tokens = row
        hit_rate = hits / total if total else 0
        return {
            "total_queries":  total,
            "cache_hits":     hits,
            "hit_rate":       round(hit_rate, 3),
            "tokens_saved":   tokens,
            "cost_saved_usd": round(tokens * 0.000002, 4),
            "entries":        entries,
            "top_queries":    [{"query": q, "hits": h} for q, h in top]
        }

    def clear(self) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM cache")
            conn.execute(
                "UPDATE stats SET total_queries=0, cache_hits=0, tokens_saved=0 WHERE id=1"
            )