import argparse
import asyncio
import json
import sys
import time

import websockets


async def probe_bridge(url: str, timeout: float) -> int:
    probe_id = f"probe-{time.time_ns()}"
    try:
        async with websockets.connect(
            url,
            open_timeout=timeout,
            close_timeout=timeout,
            ping_interval=None,
        ) as websocket:
            await asyncio.wait_for(
                websocket.send(json.dumps({"event": "bridge_probe", "id": probe_id})),
                timeout=timeout,
            )
            deadline = time.time() + timeout
            while time.time() < deadline:
                remaining = max(0.1, deadline - time.time())
                raw_message = await asyncio.wait_for(websocket.recv(), timeout=remaining)
                try:
                    payload = json.loads(raw_message)
                except json.JSONDecodeError:
                    continue
                if payload.get("event") == "bridge_probe" and payload.get("id") == probe_id:
                    print("ok")
                    return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
    print("fail")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe Kai bridge readiness.")
    parser.add_argument("--url", default="ws://127.0.0.1:8765")
    parser.add_argument("--timeout", type=float, default=2.0)
    args = parser.parse_args()
    return asyncio.run(probe_bridge(args.url, args.timeout))


if __name__ == "__main__":
    raise SystemExit(main())
