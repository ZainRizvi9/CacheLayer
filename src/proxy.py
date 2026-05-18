from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import httpx
import time
import os
from src.cache import SemanticCache, get_user_id, create_user

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="CacheLayer")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

cache = SemanticCache(threshold=0.80)

OPENAI_BASE    = "https://api.openai.com"
ANTHROPIC_BASE = "https://api.anthropic.com"

@app.get("/", response_class=HTMLResponse)
async def landing():
    with open("landing.html", "r") as f:
        return f.read()

def is_anthropic(model: str) -> bool:
    return "claude" in model.lower()

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

def get_cachelayer_key(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer cl_"):
        return auth.replace("Bearer ", "")
    return request.headers.get("X-CacheLayer-Key")

def get_upstream_key(request: Request) -> str:
    return request.headers.get("X-Upstream-Key", "")

@app.post("/v1/chat/completions")
@limiter.limit("60/minute")
async def chat_completions(request: Request):
    body = await request.json()
    model = body.get("model", "gpt-4o")

    cl_key = get_cachelayer_key(request)
    if not cl_key:
        raise HTTPException(status_code=401, detail="Missing CacheLayer API key.")
    user_id = get_user_id(cl_key)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key.")

    query = extract_query(body)
    upstream_key = get_upstream_key(request)

    if query:
        cached = cache.get(query, user_id)
        if cached:
            return JSONResponse(make_cached_response(cached, model))

    if is_anthropic(model):
        headers = {
            "x-api-key": upstream_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        anthropic_body = {
            "model": model,
            "max_tokens": body.get("max_tokens", 1024),
            "messages": body.get("messages", [])
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{ANTHROPIC_BASE}/v1/messages", headers=headers, json=anthropic_body)
            result = resp.json()
        if query and "content" in result:
            content = result["content"][0].get("text", "")
            cache.set(query, content, user_id)
            return JSONResponse(make_cached_response(content, model))
        return JSONResponse(result)

    else:
        headers = {
            "Authorization": f"Bearer {upstream_key}",
            "Content-Type": "application/json"
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{OPENAI_BASE}/v1/chat/completions", headers=headers, json=body)
            result = resp.json()
        if query and "choices" in result:
            content = result["choices"][0]["message"]["content"]
            cache.set(query, content, user_id)
        return JSONResponse(result)

@app.post("/register")
@limiter.limit("5/minute")
async def register(request: Request, email: str):
    try:
        api_key = create_user(email)
        return {
            "api_key": api_key,
            "email": email,
            "message": "Store this key securely. It will not be shown again."
        }
    except Exception:
        raise HTTPException(status_code=400, detail="Email already registered.")

@app.post("/warm")
@limiter.limit("10/minute")
async def warm(request: Request, queries: list[str]):
    cl_key = get_cachelayer_key(request)
    if not cl_key:
        raise HTTPException(status_code=401, detail="Missing API key.")
    user_id = get_user_id(cl_key)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid API key.")
    from src.embedder import embed
    warmed = []
    for q in queries:
        embed(q)
        warmed.append(q)
    return {"warmed": len(warmed), "queries": warmed}

@app.get("/stats")
@limiter.limit("30/minute")
async def stats(request: Request):
    cl_key = get_cachelayer_key(request)
    if not cl_key:
        raise HTTPException(status_code=401, detail="Missing API key.")
    user_id = get_user_id(cl_key)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid API key.")
    return cache.stats(user_id)

@app.post("/seed")
@limiter.limit("30/minute")
async def seed(request: Request, query: str, response: str):
    cl_key = get_cachelayer_key(request)
    if not cl_key:
        raise HTTPException(status_code=401, detail="Missing API key.")
    user_id = get_user_id(cl_key)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid API key.")
    cache.set(query, response, user_id)
    return {"seeded": True, "query": query}

@app.get("/health")
def health():
    return {"status": "ok", "providers": ["openai", "anthropic"]}