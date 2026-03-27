import json
import os
from urllib import error, request


class OllamaClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434", model: str = "xploiter/the-xploiter:latest"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.default_timeout = int(os.environ.get("KAI_OLLAMA_TIMEOUT", "20"))

    def chat(self, messages: list[dict], timeout: int | None = None) -> str:
        if timeout is None:
            timeout = self.default_timeout
        payload = json.dumps(
            {
                "model": self.model,
                "messages": messages,
                "stream": False,
            }
        ).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            raise RuntimeError(f"Ollama HTTP error {exc.code}") from exc
        except error.URLError as exc:
            raise RuntimeError("Ollama is not reachable on http://127.0.0.1:11434") from exc

        message = data.get("message", {})
        content = message.get("content", "").strip()
        if not content:
            raise RuntimeError("Ollama returned an empty response")
        return content
