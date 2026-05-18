from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx
import json
import time
from src.cache import SemanticCache

app = FastAPI(title="CacheLayer - Semantic LLM Proxy")
cache = SemanticCache(threshold=0.80)

OPENAI_BASE = "https://api.openai.com"

def extract_query(body: dict) -> str | None:
    """Pull the last user message from an OpenAI chat request."""
    messages = body.get("messages", [])
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return msg.get("content", "")
    return None

def make_cached_response(content: str, model: str) -> dict:
    """Wrap a cached string in OpenAI response format."""
    return {
        "id": f"cache-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop"
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "cached": True
    }

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    query = extract_query(body)
    model = body.get("model", "gpt-4o")

    # Check cache first
    if query:
        cached = cache.get(query)
        if cached:
            return JSONResponse(make_cached_response(cached, model))

    # Cache miss — forward to real OpenAI
    headers = {
        "Authorization": request.headers.get("Authorization", ""),
        "Content-Type": "application/json"
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{OPENAI_BASE}/v1/chat/completions",
            headers=headers,
            json=body
        )
        result = resp.json()

    # Store response in cache
    if query and "choices" in result:
        content = result["choices"][0]["message"]["content"]
        cache.set(query, content)

    return JSONResponse(result)

@app.get("/stats")
def stats():
    return cache.stats()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/seed")
async def seed(query: str, response: str):
    """Manually seed the cache for testing and demos."""
    cache.set(query, response)
    return {"seeded": True, "query": query}