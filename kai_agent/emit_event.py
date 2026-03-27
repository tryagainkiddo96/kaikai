import argparse
import asyncio
import json

import websockets


DEFAULT_URL = "ws://127.0.0.1:8765"


async def send_event(url: str, event_name: str, text: str | None = None) -> None:
    async with websockets.connect(url) as websocket:
        payload_obj = {"event": event_name}
        if text:
            payload_obj["text"] = text
        payload = json.dumps(payload_obj)
        await websocket.send(payload)
        print(f"sent {payload} -> {url}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send Kai companion events to the websocket bridge.")
    parser.add_argument(
        "event",
        choices=["kai_thinking", "kai_walk", "kai_sleep", "kai_wag_tail", "kai_notice"],
        help="Event name for the companion.",
    )
    parser.add_argument("--url", default=DEFAULT_URL, help="Websocket bridge URL.")
    parser.add_argument("--text", default="", help="Optional text for notice events.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(send_event(args.url, args.event, args.text or None))
