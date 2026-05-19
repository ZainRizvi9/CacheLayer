# CacheLayer

LLM APIs charge per token. The problem is that users ask the same questions constantly, just worded differently. A solutions engineer asks "what is the implementation timeline for Salesforce Service Cloud." A project manager asks "how long does a typical Service Cloud deployment take." A consultant asks "what is the average delivery timeline for a Service Cloud project." Three API calls, three identical answers, three times the cost.

Exact string caching does not help because the strings do not match. CacheLayer fixes this by understanding what the query means, not just what it says.

## What it does

CacheLayer sits between your application and OpenAI or Anthropic. You point your existing code at it instead of the provider endpoint and nothing else changes. When a query comes in, it gets converted to a vector embedding and compared against everything in the cache. If something similar enough already has an answer, it returns that instantly. No API call, no tokens spent.

If nothing matches, it forwards the request to the real API as normal, caches the response, and returns it.

## Plug it in

```python
# Before
client = OpenAI(base_url="https://api.openai.com")

# After — works identically, now with caching
client = OpenAI(base_url="https://cachelayer.up.railway.app")
```

Every existing call works identically. One line change, zero refactoring.

## Headers

```bash
# Register for a key first
curl -X POST "https://cachelayer.up.railway.app/register?email=you@example.com"

# Then pass both headers on every request
-H "Authorization: Bearer cl_your_key_here"   # your CacheLayer key
-H "X-Upstream-Key: sk_your_openai_key"        # your actual provider key
```

## Architecture

```
Client App
    │
    │  POST /v1/chat/completions
    ▼
CacheLayer Proxy  (FastAPI, Railway)
    │
    │  embed query → cosine similarity search
    ▼
SQLite Cache (per-user isolated)
    │
    ├── HIT  → return in ~8ms, $0.00 tokens
    │
    └── MISS → forward to OpenAI / Anthropic → cache → return
```

## Providers

Supports OpenAI, Anthropic, and any OpenAI-compatible API. CacheLayer automatically detects which provider to route to based on the model name — no configuration needed.

```python
# OpenAI
client = OpenAI(base_url="https://cachelayer.up.railway.app")
response = client.chat.completions.create(model="gpt-4o", ...)

# Anthropic
client = Anthropic(base_url="https://cachelayer.up.railway.app")
response = client.messages.create(model="claude-3-5-sonnet-20241022", ...)
```

## Demo

```bash
# 1. Register
curl -X POST "https://cachelayer.up.railway.app/register?email=you@example.com"
# → {"api_key": "cl_...", "message": "Store this key securely."}

# 2. Seed the cache
curl -X POST "https://cachelayer.up.railway.app/seed?query=what+is+a+REST+API&response=A+REST+API+uses+HTTP+methods+to+operate+on+resources." -H "Authorization: Bearer cl_..."
# → {"seeded": true}

# 3. Query with a paraphrase — different wording, same meaning
curl -X POST https://cachelayer.up.railway.app/v1/chat/completions -H "Content-Type: application/json" -H "Authorization: Bearer cl_..." -d '{"model":"gpt-4o","messages":[{"role":"user","content":"explain what REST APIs are"}]}'
# → {"cached": true, "usage": {"total_tokens": 0}, ...}

# 4. Check your savings
curl https://cachelayer.up.railway.app/stats -H "Authorization: Bearer cl_..."
# → {"cache_hits": 4, "tokens_saved": 70, "hit_rate": 0.571, "cost_saved_usd": 0.0001}
```

## Results

Evaluated across 15 paraphrased query pairs spanning enterprise software, finance, and consulting domains:

| Threshold | Hit Rate | Tokens Saved | Cost Saved |
|-----------|----------|--------------|------------|
| 0.70      | 100.0%   | 900          | $0.0045    |
| 0.75      | 93.3%    | 840          | $0.0042    |
| **0.80**  | **93.3%**| **840**      | **$0.0042**|
| 0.85      | 66.7%    | 600          | $0.0030    |
| 0.90      | 33.3%    | 300          | $0.0015    |
| 0.95      | 0.0%     | 0            | $0.0000    |

**0.80 is the sweet spot.** Below that you risk returning wrong answers for queries that are similar but not identical. Above it you start missing valid hits.

## Latency

| Metric | Value |
|--------|-------|
| Cache hit avg latency | 8.3ms |
| Cache miss avg latency | 8.5ms |
| Live API baseline (GPT-4o) | ~1,800ms |
| Speedup on cache hit | **216x** |
| Token cost on cache hit | **$0.00** |

## When to use semantic caching

Semantic caching works best for:
- Knowledge-style queries with stable, deterministic answers
- Internal tools, support assistants, and pre-sales AI where users rephrase the same questions
- High-traffic applications where query paraphrase rates are significant

Avoid caching for:
- Queries that are highly user-specific or personalized
- Time-sensitive prompts where the correct answer changes frequently
- Queries involving private user data that should never be shared across sessions

## Enterprise: shared team cache

In multi-tenant deployments, each user gets an isolated cache scoped to their API key. One person's cached queries are never returned to another user. When a team works in the same domain, each member benefits from their own cache growing independently.

## Run it locally

```bash
git clone https://github.com/ZainRizvi9/CacheLayer
cd CacheLayer
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn src.proxy:app --port 8000
```

Or with Docker:

```bash
docker build -t cachelayer .
docker run -p 8000:8000 -v cachelayer_data:/data cachelayer
```

## Endpoints

- `POST /v1/chat/completions` — drop-in replacement for OpenAI and Anthropic
- `POST /register` — register and receive a `cl_` API key
- `GET /stats` — hit rate, tokens saved, cost saved, top queries (per user)
- `POST /seed` — pre-load the cache with known Q&A pairs
- `POST /warm` — pre-embed a list of expected queries before traffic arrives
- `GET /health` — health check

## Tests

```bash
pytest tests/test_cache.py -v
```

10 tests covering cache hits, misses, TTL expiry, threshold boundaries, per-user isolation, and stats accuracy. CI runs on every push via GitHub Actions.

## Stack

Python, FastAPI, sentence-transformers, NumPy, SQLite, Docker, Railway, slowapi

## Live

[cachelayer.up.railway.app](https://cachelayer.up.railway.app)