"""Both MCP servers: every tool is registered with a full JSON schema and annotations, the generated tool
references are current, and the servers answer over the MCP stdio protocol (no game needed for these calls)."""
import asyncio
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_tool_docs_current():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "gen_tool_docs.py"), "--check"],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("module, expected", [("sc3k_mcp", "simcity3000"), ("bat_mcp", "buildingarchitect")])
def test_stdio_handshake(module, expected):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def run():
        env = dict(os.environ, PYTHONPATH=ROOT, PYTHONIOENCODING="utf-8")
        params = StdioServerParameters(command=sys.executable, args=["-m", module], env=env)
        async with stdio_client(params, errlog=open(os.devnull, "w")) as (r, w):
            async with ClientSession(r, w) as s:
                init = await s.initialize()
                tools = (await s.list_tools()).tools
                guide = await s.call_tool("guide", {"topic": ""})
                return init, tools, guide

    init, tools, guide = asyncio.run(run())
    assert init.serverInfo.name == expected
    assert len(tools) > 40
    for t in tools:
        assert t.description and t.inputSchema.get("type") == "object", t.name
        assert "$ref" not in json.dumps(t.inputSchema), t.name
        assert t.annotations is not None, t.name
    assert not guide.isError and len(guide.content[0].text) > 1000
