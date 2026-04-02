import json
import os
from urllib import error, request


class OllamaClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434", model: str = "qwen3:4b-q4_K_M"):
        self.base_url = base_url.rstrip("/")
        self.model = os.environ.get("KAI_MODEL", "").strip() or model
        self.default_timeout = int(os.environ.get("KAI_OLLAMA_TIMEOUT", "180"))
        self.temperature = float(os.environ.get("KAI_TEMPERATURE", "0.7"))
        self.repeat_penalty = float(os.environ.get("KAI_REPEAT_PENALTY", "1.15"))
        self.num_predict = int(os.environ.get("KAI_NUM_PREDICT", "512"))
        self.num_ctx = int(os.environ.get("KAI_NUM_CTX", "4096"))

    def chat(self, messages: list[dict], timeout: int | None = None) -> str:
        if timeout is None:
            timeout = self.default_timeout
        payload = json.dumps(
            {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "repeat_penalty": self.repeat_penalty,
                    "num_predict": self.num_predict,
                    "num_ctx": self.num_ctx,
                },
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
