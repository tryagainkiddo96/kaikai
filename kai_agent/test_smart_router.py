#!/usr/bin/env python3
"""Tests for Smart Router."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kai_agent.smart_router import SmartRouter


def test_direct_time():
    r = SmartRouter(cache_path=Path(tempfile.mktemp()))
    result = r.route("what time is it")
    assert result["handler"] == "direct"
    assert result["type"] == "time"


def test_direct_greeting():
    r = SmartRouter(cache_path=Path(tempfile.mktemp()))
    result = r.route("hello")
    assert result["handler"] == "direct"
    assert result["type"] == "greeting"


def test_direct_math():
    r = SmartRouter(cache_path=Path(tempfile.mktemp()))
    result = r.route("2 + 2")
    assert result["handler"] == "direct"
    assert result["type"] == "math"


def test_web_search():
    r = SmartRouter(cache_path=Path(tempfile.mktemp()))
    result = r.route("what is a proxy chain")
    assert result["handler"] == "web"
    assert "query" in result["data"]


def test_web_explicit():
    r = SmartRouter(cache_path=Path(tempfile.mktemp()))
    result = r.route("search for quantum computing")
    assert result["handler"] == "web"


def test_web_who():
    r = SmartRouter(cache_path=Path(tempfile.mktemp()))
    result = r.route("who is Elon Musk")
    assert result["handler"] == "web"


def test_ollama_opinion():
    r = SmartRouter(cache_path=Path(tempfile.mktemp()))
    result = r.route("what do you think about dogs")
    assert result["handler"] == "ollama"


def test_ollama_explain():
    r = SmartRouter(cache_path=Path(tempfile.mktemp()))
    result = r.route("explain how TCP works")
    assert result["handler"] == "ollama"


def test_ollama_personal():
    r = SmartRouter(cache_path=Path(tempfile.mktemp()))
    result = r.route("I feel stressed")
    assert result["handler"] == "ollama"


def test_ollama_default():
    r = SmartRouter(cache_path=Path(tempfile.mktemp()))
    result = r.route("hey kai can you run a command for me")
    assert result["handler"] == "ollama"


def test_caching():
    r = SmartRouter(cache_path=Path(tempfile.mktemp()))
    r.cache_response("what is 2+2", "4")
    result = r.route("what is 2+2")
    assert result["handler"] == "cached"
    assert result["data"]["response"] == "4"


def test_stats():
    r = SmartRouter(cache_path=Path(tempfile.mktemp()))
    r.route("hello")
    r.route("what time is it")
    r.route("what is Python")
    r.route("explain AI")
    stats = r.get_stats()
    assert stats["total_routed"] == 4


def test_breakdown():
    r = SmartRouter(cache_path=Path(tempfile.mktemp()))
    r.route("hello")
    r.route("what is AI")
    breakdown = r.get_route_breakdown()
    assert "Direct" in breakdown
    assert "Web" in breakdown


def main():
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  ✅ {t.__name__}")
            passed += 1
        except Exception as exc:
            print(f"  ❌ {t.__name__}: {exc}")
            import traceback
            traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"Passed: {passed}  Failed: {failed}  Total: {passed + failed}")
    if failed == 0:
        print("✅ All tests passed!")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
