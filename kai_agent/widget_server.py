import argparse
import asyncio
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from kai_agent.assistant import KaiAssistant


ROOT = Path(__file__).resolve().parents[1]
WIDGET_DIR = ROOT / "widget"
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
}


class KaiWidgetServer(ThreadingHTTPServer):
    def __init__(self, server_address, handler_class, assistant: KaiAssistant) -> None:
        super().__init__(server_address, handler_class)
        self.assistant = assistant


class Handler(BaseHTTPRequestHandler):
    server: KaiWidgetServer

    def do_GET(self) -> None:
        route = urlparse(self.path).path
        if route == "/api/health":
            self._send_json({"ok": True})
            return

        target = STATIC_FILES.get(route)
        if not target:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        filename, content_type = target
        body = (WIDGET_DIR / filename).read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        route = urlparse(self.path).path
        if route != "/api/chat":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length)
        payload = json.loads(raw_body.decode("utf-8") or "{}")
        message = str(payload.get("message", "")).strip()

        if not message:
            self._send_json({"error": "Message is required."}, status=HTTPStatus.BAD_REQUEST)
            return

        try:
            reply = asyncio.run(self.server.assistant.ask(message))
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_GATEWAY)
            return

        self._send_json({"reply": reply})

    def log_message(self, format: str, *args) -> None:
        return

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Kai Pip-Boy widget server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8127)
    parser.add_argument("--model", default="qwen3:4b-q4_K_M")
    parser.add_argument("--workspace", default=str(ROOT))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    assistant = KaiAssistant(model=args.model, workspace=Path(args.workspace))
    server = KaiWidgetServer((args.host, args.port), Handler, assistant)
    print(f"Kai widget ready at http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
