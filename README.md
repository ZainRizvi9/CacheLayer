# CacheLayer

LLM APIs charge per token. The problem is that users ask the same questions constantly, just worded differently. A solutions engineer asks "what is the implementation timeline for Salesforce Service Cloud." A project manager on the same team asks "how long does a typical Service Cloud deployment take." A consultant asks "what is the average delivery timeline for a Service Cloud project." Three API calls, three identical answers, three times the cost.

Exact string caching does not help because the strings do not match. CacheLayer fixes this by understanding what the query means, not just what it says.

## What it does

CacheLayer sits between your application and OpenAI. You point your existing code at it instead of the OpenAI endpoint and nothing else changes. When a query comes in, it gets converted to a vector embedding and compared against everything in the cache. If something similar enough already has an answer, it returns that instantly. No API call, no tokens spent.

If nothing matches, it forwards the request to OpenAI as normal, caches the response, and returns it.

## Plug it in

```python
# Before
client = OpenAI(base_url="https://api.openai.com")

# After
client = OpenAI(base_url="http://localhost:8000")
```

That is it. Every existing call works identically.

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

## Run it

```bash
git clone https://github.com/ZainRizvi9/CacheLayer
cd CacheLayer
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn src.proxy:app --port 8000
```

## Endpoints

- `POST /v1/chat/completions` — drop-in OpenAI replacement
- `GET /stats` — hit rate, tokens saved, cost saved in real time
- `POST /seed` — pre-load the cache with known Q&A pairs
- `GET /health` — health check

## Stack

Python, FastAPI, sentence-transformers, NumPy, SQLite
