import asyncio
import json
import os
from pathlib import Path

import websockets

from kai_agent.logger import KaiLogger


DEFAULT_URL = "ws://127.0.0.1:8765"
CONNECT_TIMEOUT = 1.5
SEND_TIMEOUT = 1.5
_LOGGED_BRIDGE_ERRORS: set[str] = set()


def _resolve_log_root() -> Path:
    log_root = os.environ.get("KAI_LOG_ROOT", "").strip()
    if log_root:
        return Path(log_root).expanduser().resolve()
    data_root = os.environ.get("KAI_DATA_ROOT", "").strip()
    if data_root:
        return Path(data_root).expanduser().resolve() / "logs"
    return Path(__file__).resolve().parents[1] / "logs"


def _log_bridge_warning(message: str) -> None:
    if not message or message in _LOGGED_BRIDGE_ERRORS:
        return
    _LOGGED_BRIDGE_ERRORS.add(message)
    try:
        KaiLogger(_resolve_log_root()).log("bridge_client_warning", error=message, url=DEFAULT_URL)
    except Exception:
        return


async def send_event(event_name: str, url: str = DEFAULT_URL) -> None:
    if not event_name:
        return
    payload = json.dumps({"event": event_name})
    try:
        async with websockets.connect(
            url,
            open_timeout=CONNECT_TIMEOUT,
            close_timeout=CONNECT_TIMEOUT,
            ping_interval=None,
        ) as websocket:
            await asyncio.wait_for(websocket.send(payload), timeout=SEND_TIMEOUT)
    except Exception as exc:
        # The companion bridge is optional for CLI usage.
        _log_bridge_warning(str(exc))
        return
