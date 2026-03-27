import asyncio
from typing import Set

import websockets
from websockets.server import WebSocketServerProtocol


HOST = "127.0.0.1"
PORT = 8765
MAX_QUEUE_SIZE = 200
MAX_MESSAGE_CHARS = 4000

CLIENTS: Set[WebSocketServerProtocol] = set()
QUEUE: asyncio.Queue[str] = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)


def _trim_message(message: str) -> str:
    if len(message) > MAX_MESSAGE_CHARS:
        return message[:MAX_MESSAGE_CHARS]
    return message


async def _enqueue(message: str) -> None:
    message = _trim_message(message)
    try:
        QUEUE.put_nowait(message)
    except asyncio.QueueFull:
        try:
            QUEUE.get_nowait()
        except asyncio.QueueEmpty:
            return
        try:
            QUEUE.put_nowait(message)
        except asyncio.QueueFull:
            return


async def register_client(websocket: WebSocketServerProtocol) -> None:
    CLIENTS.add(websocket)
    try:
        async for message in websocket:
            await _enqueue(message)
    finally:
        CLIENTS.discard(websocket)


async def broadcaster() -> None:
    while True:
        message = await QUEUE.get()
        if not CLIENTS:
            continue

        dead = []
        for client in list(CLIENTS):
            try:
                await client.send(message)
            except Exception:
                dead.append(client)

        for client in dead:
            CLIENTS.discard(client)


async def main() -> None:
    async with websockets.serve(
        register_client,
        HOST,
        PORT,
        ping_interval=20,
        ping_timeout=20,
        max_size=2**20,
    ):
        await broadcaster()
