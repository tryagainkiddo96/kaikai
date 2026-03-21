from __future__ import annotations

import json
import os
from urllib import error, request


class TavilyClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("TAVILY_API_KEY", "").strip()

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, max_results: int = 5) -> dict:
        if not self.configured:
            return {
                "action": "web_research",
                "ok": False,
                "error": "TAVILY_API_KEY is not set.",
                "query": query,
            }

        payload = {
            "query": query,
            "search_depth": "advanced",
            "topic": "general",
            "max_results": max(1, min(max_results, 10)),
            "include_answer": True,
            "include_raw_content": False,
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            "https://api.tavily.com/search",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=45) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            return {
                "action": "web_research",
                "ok": False,
                "error": f"Tavily HTTP {exc.code}",
                "details": details[:4000],
                "query": query,
            }
        except Exception as exc:
            return {
                "action": "web_research",
                "ok": False,
                "error": str(exc),
                "query": query,
            }

        results = []
        for item in data.get("results", [])[: max_results]:
            results.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                }
            )

        return {
            "action": "web_research",
            "ok": True,
            "query": query,
            "answer": data.get("answer", ""),
            "results": results,
        }
