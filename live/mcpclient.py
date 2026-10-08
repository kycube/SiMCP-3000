"""LIVE: drive the sc3k MCP server over stdio like an MCP host would.

    python live/mcpclient.py list
    python live/mcpclient.py call <tool> '<json args>' [<tool> '<json args>' ...]
Images are saved to live/shots/mcp_<n>.png.
"""
import asyncio
import base64
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTS = os.path.join(ROOT, "live", "shots")


async def main():
    env = dict(os.environ, PYTHONPATH=ROOT, PYTHONIOENCODING="utf-8")
    params = StdioServerParameters(command=sys.executable, args=["-m", "sc3k_mcp"], env=env)
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            if sys.argv[1] == "list":
                for t in (await s.list_tools()).tools:
                    print(f"{t.name}: {(t.description or '').splitlines()[0][:110]}")
                return
            args = sys.argv[2:]
            n = 0
            for i in range(0, len(args), 2):
                tool, a = args[i], json.loads(args[i + 1]) if i + 1 < len(args) else {}
                res = await s.call_tool(tool, a)
                for c in res.content:
                    if c.type == "text":
                        print(f"[{tool}] {c.text}")
                    elif c.type == "image":
                        os.makedirs(SHOTS, exist_ok=True)
                        path = os.path.join(SHOTS, f"mcp_{n}.png")
                        n += 1
                        with open(path, "wb") as f:
                            f.write(base64.b64decode(c.data))
                        print(f"[{tool}] image -> {path}")
                if res.isError:
                    print(f"[{tool}] ERROR")


if __name__ == "__main__":
    asyncio.run(main())
