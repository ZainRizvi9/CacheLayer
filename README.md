cat > README.md << 'EOF'
# CacheLayer

LLM APIs charge per token. The problem is that users ask the same questions constantly, just worded differently. A solutions engineer asks "what is the implementation timeline for Salesforce Service Cloud." A project manager on the same team asks "how long does a typical Service Cloud deployment take." A consultant asks "what is the average delivery timeline for a Service Cloud project." Three API calls, three identical answers, three times the cost.

Exact string caching does not help because the strings do not match. CacheLayer fixes this by understanding what the query means, not just what it says.

## What it does

CacheLayer sits between your application and any LLM provider. You point your existing code at it instead of the OpenAI or Anthropic endpoint and nothing else changes. When a query comes in, it gets converted to a vector embedding and compared against everything in the cache. If something similar enough already has an answer, it returns that instantly. No API call, no tokens spent.

If nothing matches, it forwards the request to the real API as normal, caches the response, and returns it.

## Works with any LLM provider

CacheLayer is provider-agnostic. Point it at OpenAI, Anthropic, Cohere, or any OpenAI-compatible API.

```python
# OpenAI
client = OpenAI(base_url="https://cachelayer.up.railway.app")

# Anthropic via compatible wrapper
client = Anthropic(base_url="https://cachelayer.up.railway.app")

# Any OpenAI-compatible provider
client = OpenAI(base_url="https://cachelayer.up.railway.app")
```

That is it. Every existing call works identically. One line change, zero refactoring.

## Shared team cache

In enterprise deployments, CacheLayer maintains a shared cache across your entire team. When one person on your team asks a question, everyone else gets the cached answer instantly — regardless of how they phrase it. A consultant who ran an analysis last week does not cost the firm another API call when a colleague asks the same question differently on Monday morning.

This means cost savings compound with team size. A 10-person team asking semantically similar questions throughout the week can see cache hit rates far above what any individual user would generate alone.

## Live deployment
https://cachelayer.up.railway.app

Health check: `GET https://cachelayer.up.railway.app/health`
Stats: `GET https://cachelayer.up.railway.app/stats`

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

0.80 is the sweet spot. Below that you risk returning wrong answers for queries that are similar but not the same. Above it you start missing valid hits. At 0.80 you catch 93% of paraphrased duplicates while staying precise enough to be trustworthy.

At scale this compounds quickly. An enterprise tool handling 10,000 queries per day with a 70% paraphrase rate saves roughly $3/day on GPT-4o output tokens alone, over $1,000 per year for a single deployment.

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

- `POST /v1/chat/completions` — drop-in replacement for any OpenAI-compatible endpoint
- `GET /stats` — hit rate, tokens saved, cost saved in real time
- `POST /seed` — pre-load the cache with known Q&A pairs
- `GET /health` — health check

## Stack

Python, FastAPI, sentence-transformers, NumPy, SQLite, Docker
EOF
