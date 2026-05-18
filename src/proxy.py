from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx
import json
import time
from src.cache import SemanticCache

app = FastAPI(title="CacheLayer - Semantic LLM Proxy")
cache = SemanticCache(threshold=0.80)

OPENAI_BASE   = "https://api.openai.com"
ANTHROPIC_BASE = "https://api.anthropic.com"

ANTHROPIC_MODELS = {"claude-3-5-sonnet", "claude-3-opus", "claude-3-haiku",
                    "claude-sonnet", "claude-opus", "claude-haiku",
                    "claude-3-5-haiku", "claude-3-7-sonnet"}

def is_anthropic(model: str) -> bool:
    return any(m in model.lower() for m in ["claude"])

def extract_query(body: dict) -> str | None:
    messages = body.get("messages", [])
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, list):
                for block in content:
                    if block.get("type") == "text":
                        return block.get("text", "")
            return content
    return None

def make_cached_response(content: str, model: str) -> dict:
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
    auth  = request.headers.get("Authorization", "")

    # Check cache first regardless of provider
    if query:
        cached = cache.get(query)
        if cached:
            return JSONResponse(make_cached_response(cached, model))

    # Cache miss — route to correct provider
    if is_anthropic(model):
        # Convert OpenAI format to Anthropic format
        anthropic_body = {
            "model": model,
            "max_tokens": body.get("max_tokens", 1024),
            "messages": body.get("messages", [])
        }
        if body.get("system"):
            anthropic_body["system"] = body["system"]

        headers = {
            "x-api-key": auth.replace("Bearer ", ""),
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{ANTHROPIC_BASE}/v1/messages",
                headers=headers,
                json=anthropic_body
            )
            result = resp.json()

        # Anthropic response format differs — extract and normalize
        if query and "content" in result:
            content = result["content"][0].get("text", "")
            cache.set(query, content)
            return JSONResponse(make_cached_response(content, model))
        return JSONResponse(result)

    else:
        # OpenAI route
        headers = {
            "Authorization": auth,
            "Content-Type": "application/json"
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{OPENAI_BASE}/v1/chat/completions",
                headers=headers,
                json=body
            )
            result = resp.json()

        if query and "choices" in result:
            content = result["choices"][0]["message"]["content"]
            cache.set(query, content)

        return JSONResponse(result)

@app.get("/stats")
def stats():
    return cache.stats()

@app.post("/seed")
async def seed(query: str, response: str):
    cache.set(query, response)
    return {"seeded": True, "query": query}

@app.get("/health")
def health():
    return {"status": "ok", "providers": ["openai", "anthropic"]}