import sys
sys.path.insert(0, '.')

import time
import pytest
from src.cache import SemanticCache

TEST_USER = 1

@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DB", str(tmp_path / "test_cache.db"))
    from src import cache as cache_module
    import importlib
    importlib.reload(cache_module)
    return cache_module.SemanticCache(threshold=0.80, ttl=3600)

def test_cache_miss_on_empty(cache):
    result = cache.get("what is the implementation timeline for Salesforce", TEST_USER)
    assert result is None

def test_cache_hit_exact(cache):
    cache.set("what is a REST API", "A REST API uses HTTP methods to operate on resources.", TEST_USER)
    result = cache.get("what is a REST API", TEST_USER)
    assert result == "A REST API uses HTTP methods to operate on resources."

def test_cache_hit_paraphrase(cache):
    cache.set("what is a REST API", "A REST API uses HTTP methods to operate on resources.", TEST_USER)
    result = cache.get("explain what REST APIs are", TEST_USER)
    assert result is not None

def test_cache_miss_unrelated(cache):
    cache.set("what is a REST API", "A REST API uses HTTP methods to operate on resources.", TEST_USER)
    result = cache.get("what is the capital of France", TEST_USER)
    assert result is None

def test_cache_stats_hit_rate(cache):
    cache.set("how do I open a TFSA account", "Visit any major Canadian bank with valid ID.", TEST_USER)
    cache.get("how do I open a TFSA account", TEST_USER)
    cache.get("steps to open a TFSA", TEST_USER)
    stats = cache.stats(TEST_USER)
    assert stats["cache_hits"] >= 1
    assert stats["hit_rate"] > 0

def test_cache_stats_tokens_saved(cache):
    response = "Visit any major Canadian bank with valid ID and your SIN number."
    cache.set("how do I open a TFSA account", response, TEST_USER)
    cache.get("how do I open a TFSA", TEST_USER)
    stats = cache.stats(TEST_USER)
    assert stats["tokens_saved"] > 0

def test_cache_ttl_expiry(cache, tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DB", str(tmp_path / "ttl_cache.db"))
    from src import cache as cache_module
    import importlib
    importlib.reload(cache_module)
    short_cache = cache_module.SemanticCache(threshold=0.80, ttl=1)
    short_cache.set("what is compound interest", "Interest earned on interest.", TEST_USER)
    time.sleep(2)
    result = short_cache.get("what is compound interest", TEST_USER)
    assert result is None

def test_cache_multiple_entries(cache):
    cache.set("what is a REST API", "A REST API uses HTTP methods to operate on resources.", TEST_USER)
    cache.set("how does Docker work", "Docker packages apps into containers.", TEST_USER)
    cache.set("what is machine learning", "ML trains models on data to find patterns.", TEST_USER)
    stats = cache.stats(TEST_USER)
    assert stats["entries"] == 3

def test_cache_high_threshold_miss(cache, tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DB", str(tmp_path / "strict_cache.db"))
    from src import cache as cache_module
    import importlib
    importlib.reload(cache_module)
    strict = cache_module.SemanticCache(threshold=0.99, ttl=3600)
    strict.set("what is the implementation timeline for Salesforce", "Typically 3 to 6 months.", TEST_USER)
    result = strict.get("how long does a Salesforce deployment take", TEST_USER)
    assert result is None

def test_cache_low_threshold_hit(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DB", str(tmp_path / "loose_cache.db"))
    from src import cache as cache_module
    import importlib
    importlib.reload(cache_module)
    loose = cache_module.SemanticCache(threshold=0.70, ttl=3600)
    loose.set("what is a REST API", "A REST API uses HTTP methods to operate on resources.", TEST_USER)
    result = loose.get("explain what REST APIs are", TEST_USER)
    assert result is not None