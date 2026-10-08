"""LIVE: a non-Claude agent plays through SiMCP 3000. A minimal agent loop: an MCP stdio client hands the server's
tool schemas, unchanged, to a local model served by Ollama (http://127.0.0.1:11434, no API key), runs every tool
the model calls and feeds the results back, until the model answers.

    python live/other_agent.py [model] [task]
    (defaults: qwen3:0.6b; "Load the saved city 'Madison, WI' and tell me its population and funds.")

Set TOOLS=all to offer every tool instead of the small default set, SERVER=bat for the Building Architect server.
"""
import asyncio
import json
import os
import sys
import time
import urllib.request

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_TOOLS = {"game": ["guide", "game_status", "list_cities", "load_city", "city_status", "metrics",
                          "advance_time", "get_budget"],
                 "bat": ["guide", "bat_status", "projects", "project_image", "library", "rendered_buildings",
                         "photo_buildings"]}


def chat(model: str, messages: list, tools: list) -> dict:
    body = {"model": model, "messages": messages, "tools": tools, "stream": False, "think": False,
            "options": {"num_ctx": 32768, "temperature": 0}}
    req = urllib.request.Request(OLLAMA + "/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())


async def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "qwen3:0.6b"
    task = sys.argv[2] if len(sys.argv) > 2 else "Load the saved city 'Madison, WI' and tell me its population and funds."
    env = dict(os.environ, PYTHONPATH=ROOT, PYTHONIOENCODING="utf-8")
    server = os.environ.get("SERVER", "game")
    params = StdioServerParameters(command=sys.executable, args=["-m", {"game": "sc3k_mcp", "bat": "bat_mcp"}[server]],
                                   env=env)
    async with stdio_client(params, errlog=open(os.devnull, "w")) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            listed = (await s.list_tools()).tools
            pick = None if os.environ.get("TOOLS") == "all" else set(DEFAULT_TOOLS[server])
            tools = [{"type": "function", "function": {"name": t.name, "description": t.description,
                                                         "parameters": t.inputSchema}}
                     for t in listed if pick is None or t.name in pick]
            print(f"{model}: {len(tools)} of {len(listed)} tools offered (schemas as the server publishes them)")
            if server == "game":
                await s.call_tool("game_launch", {})              # the harness starts the game; the model does the rest
            what = "SimCity 3000" if server == "game" else "SimCity 3000's Building Architect"
            messages = [{"role": "system", "content": f"You control {what} through tools. Call tools to get "
                                                      "facts; never guess numbers. Answer briefly when done."},
                        {"role": "user", "content": task}]
            for step in range(12):
                t0 = time.time()
                out = chat(model, messages, tools)["message"]
                messages.append(out)
                calls = out.get("tool_calls") or []
                if not calls:
                    print(f"[{step}] answer ({time.time() - t0:.1f}s): {out.get('content', '').strip()}")
                    return
                for c in calls:
                    fn = c["function"]
                    args = fn.get("arguments") or {}
                    if isinstance(args, str):
                        args = json.loads(args or "{}")
                    res = await s.call_tool(fn["name"], args)
                    text = " ".join(x.text for x in res.content if x.type == "text")
                    print(f"[{step}] {fn['name']}({json.dumps(args)}) -> {'ERROR ' if res.isError else ''}{text[:220]}")
                    messages.append({"role": "tool", "tool_name": fn["name"], "content": text[:6000]})
            print("no answer within 12 steps")


if __name__ == "__main__":
    asyncio.run(main())
