import time
import sqlite3
import numpy as np
import json
import os
import secrets
from src.embedder import embed, similarity

DB_PATH = os.getenv("CACHE_DB", "cache.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            api_key     TEXT UNIQUE NOT NULL,
            email       TEXT UNIQUE NOT NULL,
            created_at  REAL NOT NULL,
            is_active   INTEGER DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER NOT NULL,
            query     TEXT NOT NULL,
            response  TEXT NOT NULL,
            embedding TEXT NOT NULL,
            timestamp REAL NOT NULL,
            hits      INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            user_id        INTEGER PRIMARY KEY,
            total_queries  INTEGER DEFAULT 0,
            cache_hits     INTEGER DEFAULT 0,
            tokens_saved   INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()

init_db()

def create_user(email: str) -> str:
    api_key = f"cl_{secrets.token_urlsafe(24)}"
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO users (api_key, email, created_at) VALUES (?, ?, ?)",
            (api_key, email, time.time())
        )
        user_id = conn.execute(
            "SELECT id FROM users WHERE api_key = ?", (api_key,)
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO stats (user_id) VALUES (?)", (user_id,)
        )
    return api_key

def get_user_id(api_key: str) -> int | None:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE api_key = ? AND is_active = 1",
            (api_key,)
        ).fetchone()
    return row[0] if row else None

class SemanticCache:
    def __init__(self, threshold: float = 0.80, ttl: int = 3600):
        self.threshold = threshold
        self.ttl = ttl

    def _conn(self):
        return sqlite3.connect(DB_PATH)

    def get(self, query: str, user_id: int) -> str | None:
        q_emb = embed(query)
        now = time.time()

        with self._conn() as conn:
            conn.execute(
                "UPDATE stats SET total_queries = total_queries + 1 WHERE user_id = ?",
                (user_id,)
            )
            rows = conn.execute(
                "SELECT id, response, embedding, timestamp FROM cache WHERE user_id = ?",
                (user_id,)
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
                        WHERE user_id = ?
                    """, (tokens, user_id))
                    return response
        return None

    def set(self, query: str, response: str, user_id: int) -> None:
        emb = embed(query)
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO cache (user_id, query, response, embedding, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, query, response, json.dumps(emb.tolist()), time.time()))

    def stats(self, user_id: int) -> dict:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT total_queries, cache_hits, tokens_saved FROM stats WHERE user_id = ?",
                (user_id,)
            ).fetchone()
            entries = conn.execute(
                "SELECT COUNT(*) FROM cache WHERE user_id = ?", (user_id,)
            ).fetchone()[0]
            top = conn.execute(
                "SELECT query, hits FROM cache WHERE user_id = ? ORDER BY hits DESC LIMIT 5",
                (user_id,)
            ).fetchall()

        if not row:
            return {}
        total, hits, tokens = row
        return {
            "total_queries":  total,
            "cache_hits":     hits,
            "hit_rate":       round(hits / total, 3) if total else 0,
            "tokens_saved":   tokens,
            "cost_saved_usd": round(tokens * 0.000002, 4),
            "entries":        entries,
            "top_queries":    [{"query": q, "hits": h} for q, h in top]
        }

    def clear(self, user_id: int) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM cache WHERE user_id = ?", (user_id,))
            conn.execute(
                "UPDATE stats SET total_queries=0, cache_hits=0, tokens_saved=0 WHERE user_id=?",
                (user_id,)
            )