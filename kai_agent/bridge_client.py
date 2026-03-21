import asyncio
import json

import websockets


DEFAULT_URL = "ws://127.0.0.1:8765"
CONNECT_TIMEOUT = 1.5
SEND_TIMEOUT = 1.5


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
    except Exception:
        # The companion bridge is optional for CLI usage.
        return
