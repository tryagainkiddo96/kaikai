"""
Kai Smart Router
Decides HOW to answer a question instead of always hitting Ollama.
Routes to the cheapest/fastest/most appropriate handler.

Route map:
  Web search → factual questions (what, when, where, who)
  Direct answer → simple math, time, greetings
  Ollama → personality, opinions, conversation, complex reasoning
  Tool → commands, file ops, code analysis
  Cached → repeated questions

This saves RAM, time, and money.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Optional


class SmartRouter:
    """
    Routes user input to the best handler instead of always using Ollama.
    """

    # Patterns that can be answered directly (no LLM needed)
    DIRECT_PATTERNS = [
        (re.compile(r"^what time is it", re.I), "time"),
        (re.compile(r"^what(?:'s| is) the (?:date|day)", re.I), "date"),
        (re.compile(r"^(\d+\s*[\+\-\*\/\%\^]\s*\d+.*=?\s*)$", re.I), "math"),
        (re.compile(r"^what is (\d+)", re.I), "math"),
        (re.compile(r"^calculate", re.I), "math"),
        (re.compile(r"^convert \d+", re.I), "conversion"),
    ]

    # Patterns that should go to web search
    WEB_PATTERNS = [
        (re.compile(r"^what (?:is|are|was|were) (?:the |a )?([\w\s]+)", re.I), "factual"),
        (re.compile(r"^who (?:is|are|was|were) ", re.I), "person"),
        (re.compile(r"^when (?:did|was|is|were) ", re.I), "historical"),
        (re.compile(r"^where (?:is|are|was|were|do|does) ", re.I), "location"),
        (re.compile(r"^how (?:many|much|old|far|long|tall|fast) ", re.I), "measurement"),
        (re.compile(r"^latest (?:news|price|stock|weather)", re.I), "current"),
        (re.compile(r"^search (?:for )?", re.I), "explicit_search"),
        (re.compile(r"^look up ", re.I), "explicit_search"),
        (re.compile(r"^find (?:out )?(?:about |info )?", re.I), "explicit_search"),
        (re.compile(r"^google ", re.I), "explicit_search"),
    ]

    # Patterns that should use Ollama (personality/conversation)
    OLLAMA_PATTERNS = [
        (re.compile(r"^tell me (?:a |about )?", re.I), "conversation"),
        (re.compile(r"^what do you think", re.I), "opinion"),
        (re.compile(r"^explain", re.I), "explanation"),
        (re.compile(r"^help me (?:with |understand)", re.I), "help"),
        (re.compile(r"^how (?:do|can|should|would) (?:I|we)", re.I), "howto"),
        (re.compile(r"^why", re.I), "reasoning"),
        (re.compile(r"^can you", re.I), "request"),
        (re.compile(r"^would you", re.I), "request"),
        (re.compile(r"^I (?:feel|think|want|need|wish)", re.I), "personal"),
        (re.compile(r"^let(?:'s| us)", re.I), "collaboration"),
    ]

    def __init__(self, cache_path: Path | None = None):
        self.cache_path = cache_path or Path.cwd() / "memory" / "answer_cache.json"
        self._cache: dict[str, dict] = {}
        self._cache_ttl = 3600  # 1 hour
        self._stats = {"direct": 0, "web": 0, "ollama": 0, "cached": 0}
        self._load_cache()

    def _load_cache(self):
        if self.cache_path.exists():
            try:
                data = json.loads(self.cache_path.read_text(encoding="utf-8"))
                self._cache = data
            except Exception:
                pass

    def save_cache(self):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self._cache, indent=2), encoding="utf-8")

    # -- Routing --

    def route(self, text: str) -> dict[str, Any]:
        """
        Decide how to handle this input.
        Returns: {"handler": "direct"|"web"|"ollama"|"cached", "type": "...", "data": {...}}
        """
        text_clean = text.strip()

        # 1. Check cache first
        cache_key = hashlib.md5(text_clean.lower().encode()).hexdigest()
        cached = self._cache.get(cache_key)
        if cached and (time.time() - cached.get("time", 0)) < self._cache_ttl:
            self._stats["cached"] += 1
            return {
                "handler": "cached",
                "type": "cached_response",
                "data": {"response": cached["response"]},
            }

        # 2. Check direct answers
        for pattern, answer_type in self.DIRECT_PATTERNS:
            if pattern.search(text_clean):
                self._stats["direct"] += 1
                return {
                    "handler": "direct",
                    "type": answer_type,
                    "data": self._get_direct_answer(answer_type, text_clean),
                }

        # 3. Check web search
        for pattern, query_type in self.WEB_PATTERNS:
            match = pattern.search(text_clean)
            if match:
                self._stats["web"] += 1
                # Extract the search query
                query = text_clean
                if query_type == "explicit_search":
                    query = re.sub(r"^(?:search|look up|find|google)\s*(?:for|about|info)?\s*", "", text_clean, flags=re.I)
                return {
                    "handler": "web",
                    "type": query_type,
                    "data": {"query": query.strip()},
                }

        # 4. Check Ollama (personality/conversation)
        for pattern, conv_type in self.OLLAMA_PATTERNS:
            if pattern.search(text_clean):
                self._stats["ollama"] += 1
                return {
                    "handler": "ollama",
                    "type": conv_type,
                    "data": {"prompt": text_clean},
                }

        # 5. Default — Ollama for anything else
        self._stats["ollama"] += 1
        return {
            "handler": "ollama",
            "type": "general",
            "data": {"prompt": text_clean},
        }

    # -- Direct answers --

    def _get_direct_answer(self, answer_type: str, text: str) -> dict[str, Any]:
        """Generate a direct answer without any LLM. Only for factual/time/math."""
        from datetime import datetime

        if answer_type == "time":
            now = datetime.now().strftime("%I:%M %p")
            return {"response": f"It's {now}."}

        elif answer_type == "date":
            now = datetime.now().strftime("%A, %B %d, %Y")
            return {"response": f"Today is {now}."}

        elif answer_type == "math":
            try:
                expr = re.search(r"(\d+\s*[\+\-\*\/\%\^]\s*\d+[\d\s\+\-\*\/\%\^\.]*)", text)
                if expr:
                    result = eval(expr.group(1).replace("^", "**"))
                    return {"response": f"{result}"}
            except Exception:
                pass
            return {"response": "I'd need to calculate that. Let me think..."}

        elif answer_type == "conversion":
            return {"response": "I can look that up. What units?"}

        return {"response": ""}

    # -- Cache --

    def cache_response(self, question: str, response: str) -> None:
        """Cache a Q&A pair."""
        key = hashlib.md5(question.lower().strip().encode()).hexdigest()
        self._cache[key] = {"response": response, "time": time.time()}
        # Keep cache small
        if len(self._cache) > 500:
            oldest = sorted(self._cache.items(), key=lambda x: x[1].get("time", 0))
            for k, _ in oldest[:100]:
                del self._cache[k]
        self.save_cache()

    # -- Stats --

    def get_stats(self) -> dict[str, Any]:
        return {
            **self._stats,
            "cache_size": len(self._cache),
            "total_routed": sum(self._stats.values()),
        }

    def get_route_breakdown(self) -> str:
        total = sum(self._stats.values()) or 1
        return (
            f"Direct: {self._stats['direct']} ({self._stats['direct']*100//total}%) · "
            f"Web: {self._stats['web']} ({self._stats['web']*100//total}%) · "
            f"Ollama: {self._stats['ollama']} ({self._stats['ollama']*100//total}%) · "
            f"Cached: {self._stats['cached']} ({self._stats['cached']*100//total}%)"
        )
