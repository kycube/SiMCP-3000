"""Run a list of MCP tool calls against one of this repo's servers over stdio, the way any MCP client would, print
each result and save returned images.

    python live/mcp_run.py bat STEPS [OUTDIR]       # buildingarchitect server (python -m bat_mcp)
    python live/mcp_run.py game STEPS [OUTDIR]      # simcity3000 server (python -m sc3k_mcp)

STEPS is a .json file ([["tool", {args}], ...]) or a .py file defining STEPS (a list of (tool, args)). A step
whose args contain "_expect_error": true is counted as an expected error. Images go to OUTDIR (default
%TEMP%/sc3k-mcp/run) as NN_tool.png. Set MCP_RUN_ERRLOG=1 to see the server's own log (stderr).
"""
import asyncio
import base64
import json
import os
import runpy
import sys
import tempfile
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULES = {"bat": "bat_mcp", "game": "sc3k_mcp"}


def load_steps(path: str) -> list:
    if path.endswith(".py"):
        return list(runpy.run_path(path)["STEPS"])
    return [tuple(s) for s in json.load(open(path, encoding="utf-8"))]


async def main(server: str, steps_path: str, out: str, width: int = 300) -> int:
    os.makedirs(out, exist_ok=True)
    steps = load_steps(steps_path)
    env = dict(os.environ, PYTHONPATH=ROOT, PYTHONIOENCODING="utf-8")
    params = StdioServerParameters(command=sys.executable, args=["-m", MODULES[server]], env=env)
    errors = unexpected = 0
    errlog = sys.stderr if os.environ.get("MCP_RUN_ERRLOG") else open(os.devnull, "w")
    async with stdio_client(params, errlog=errlog) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            for k, (tool, args) in enumerate(steps):
                args = dict(args)
                expect = args.pop("_expect_error", False)
                t = time.time()
                res = await s.call_tool(tool, args)
                texts = [c.text for c in res.content if c.type == "text"]
                for c in res.content:
                    if c.type == "image":
                        p = os.path.join(out, f"{k:02d}_{tool}.png")
                        open(p, "wb").write(base64.b64decode(c.data))
                        texts.append(f"[image {p}]")
                errors += res.isError
                unexpected += res.isError and not expect
                tag = "ERR" if res.isError else "ok "
                print(f"{tag} {k:02d} {tool} ({time.time() - t:.1f}s) {json.dumps(args)[:100]}\n    "
                      f"{' '.join(texts)[:width]}", flush=True)
    print(f"{errors} errors, {unexpected} unexpected")
    return unexpected


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in MODULES:
        sys.exit(__doc__)
    outdir = sys.argv[3] if len(sys.argv) > 3 else os.path.join(tempfile.gettempdir(), "sc3k-mcp", "run")
    w = int(os.environ.get("MCP_RUN_WIDTH", "300"))
    sys.exit(1 if asyncio.run(main(sys.argv[1], sys.argv[2], outdir, w)) else 0)
