import sys
sys.path.insert(0, '.')

import time
import pytest
from src.cache import SemanticCache


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DB", str(tmp_path / "test_cache.db"))
    from src import cache as cache_module
    import importlib
    importlib.reload(cache_module)
    return cache_module.SemanticCache(threshold=0.80, ttl=3600)


def test_cache_miss_on_empty(cache):
    result = cache.get("what is the implementation timeline for Salesforce")
    assert result is None


def test_cache_hit_exact(cache):
    cache.set("what is the implementation timeline for Salesforce", "Typically 3 to 6 months.")
    result = cache.get("what is the implementation timeline for Salesforce")
    assert result == "Typically 3 to 6 months."


def test_cache_hit_paraphrase(cache):
    cache.set("what is a REST API", "A REST API uses HTTP methods to operate on resources.")
    result = cache.get("explain what REST APIs are")
    assert result is not None


def test_cache_miss_unrelated(cache):
    cache.set("what is the implementation timeline for Salesforce", "Typically 3 to 6 months.")
    result = cache.get("what is the capital of France")
    assert result is None


def test_cache_stats_hit_rate(cache):
    cache.set("how do I open a TFSA account", "Visit any major Canadian bank with valid ID.")
    cache.get("how do I open a TFSA account")
    cache.get("steps to open a TFSA")
    stats = cache.stats()
    assert stats["cache_hits"] >= 1
    assert stats["hit_rate"] > 0


def test_cache_stats_tokens_saved(cache):
    response = "Visit any major Canadian bank with valid ID and your SIN number."
    cache.set("how do I open a TFSA account", response)
    cache.get("how do I open a TFSA")
    stats = cache.stats()
    assert stats["tokens_saved"] > 0


def test_cache_ttl_expiry(cache, monkeypatch):
    short_cache = __import__('src.cache', fromlist=['SemanticCache']).SemanticCache(threshold=0.80, ttl=1)
    short_cache.set("what is compound interest", "Interest earned on interest.")
    time.sleep(2)
    result = short_cache.get("what is compound interest")
    assert result is None


def test_cache_multiple_entries(cache):
    cache.set("what is a REST API", "A REST API uses HTTP methods to operate on resources.")
    cache.set("how does Docker work", "Docker packages apps into containers.")
    cache.set("what is machine learning", "ML trains models on data to find patterns.")
    stats = cache.stats()
    assert stats["entries"] == 3


def test_cache_high_threshold_miss(cache, tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DB", str(tmp_path / "strict_cache.db"))
    from src import cache as cache_module
    import importlib
    importlib.reload(cache_module)
    strict = cache_module.SemanticCache(threshold=0.99, ttl=3600)
    strict.set("what is the implementation timeline for Salesforce", "Typically 3 to 6 months.")
    result = strict.get("how long does a Salesforce deployment take")
    assert result is None


def test_cache_low_threshold_hit(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DB", str(tmp_path / "loose_cache.db"))
    from src import cache as cache_module
    import importlib
    importlib.reload(cache_module)
    loose = cache_module.SemanticCache(threshold=0.70, ttl=3600)
    loose.set("what is a REST API", "A REST API uses HTTP methods to operate on resources.")
    result = loose.get("explain what REST APIs are")
    assert result is not None
