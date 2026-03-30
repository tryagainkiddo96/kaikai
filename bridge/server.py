import asyncio

from kai_agent.bridge_server import HOST, PORT, main


if __name__ == "__main__":
    print(f"Kai bridge listening on ws://{HOST}:{PORT}")
    asyncio.run(main())
