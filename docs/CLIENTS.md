# Connecting an agent

This repository has two servers, set up the same way: `simcity3000` (`python -m sc3k_mcp`, plays the game) and
`buildingarchitect` (`python -m bat_mcp`, creates buildings with the Building Architect). Every example below shows
the game server; for the Building Architect use the same entry with the name `buildingarchitect` and
`-m bat_mcp` (or the `bat-mcp` command; HTTP default port 8766). Both can be registered at once.

The servers speak the standard Model Context Protocol, so any MCP client can use them: Claude Code / Claude Desktop,
OpenAI Codex CLI and the OpenAI Agents SDK, Gemini CLI and Google's Agent Development Kit, editors with MCP support,
or your own code using an MCP SDK. Nothing in the server depends on a particular model.

- [Requirements and install](#requirements-and-install)
- [What every client needs to know](#what-every-client-needs-to-know)
- [Claude Code](#claude-code) · [Claude Desktop](#claude-desktop)
- [OpenAI Codex CLI](#openai-codex-cli) · [OpenAI Agents SDK](#openai-agents-sdk-python)
- [Gemini CLI](#gemini-cli) · [Google ADK](#google-agent-development-kit-python)
- [Local models with Ollama](#local-models-with-ollama)
- [HTTP transport](#http-transport) · [MCP Inspector](#mcp-inspector) · [Your own code](#your-own-code-python-mcp-sdk)

In the examples, replace `C:\path\to\SiMCP-3000` with this folder and `C:\Python313\python.exe` with your Python.

## Requirements and install

- Windows with SimCity 3000 Unlimited (GOG build 2.0.949) installed. The default install folder is
  `C:\Program Files\GOG Galaxy\Games\SimCity 3000 Unlimited`; for another location set the environment variable
  `SC3K_GAME_DIR` in the client's server config.
- Python 3.10 or newer.
- From this folder: `python -m pip install -e .` (editable install: the server finds its bridge DLL in `bridge\build`
  next to the package, so keep the folder where it is). This also installs the `sc3k-mcp` command.
  Without installing, set `PYTHONPATH` to this folder in the client config instead (the examples show both).
- The bridge DLL: run `bridge\build.bat` once (Visual Studio or its free Build Tools with "Desktop development
  with C++"), which writes `bridge\build\sc3kbridge.dll`; or download the `bridge-dlls` artifact of a CI run and
  set `SC3K_BRIDGE_DLL` to its `sc3kbridge.dll`. Nothing has to be copied into the game folder: the server
  injects the DLL into the running game.

The server is started by the client (stdio transport) as `python -m sc3k_mcp`. It does not touch the game until a
tool is called; `game_launch` starts the game.

## What every client needs to know

**Timeouts.** Some calls take longer than typical client defaults: `start_trial` about 12 s, loading a large city
10-30 s, `game_launch` up to a minute, `advance_time` up to `max_seconds` (default 50 s), `run_realtime` as long as
asked. Set the client's tool timeout to at least 120 s (600 s is comfortable). If a client cannot raise its timeout,
pass a smaller `max_seconds` to `advance_time`; it then returns early with `remaining_days` and the next call
continues (the result is the same as one long call).

| client | default tool timeout | setting |
|---|---|---|
| Claude Code | ~28 hours | `"timeout"` (ms) per server in `.mcp.json`, or `MCP_TOOL_TIMEOUT` |
| OpenAI Codex CLI | 60 s | `tool_timeout_sec` |
| OpenAI Agents SDK | 5 s | `client_session_timeout_seconds` |
| Gemini CLI | 600 s | `"timeout"` (ms) |
| Google ADK | short (5 s in the docs' examples) | `StdioConnectionParams(timeout=...)` |

**One game, one client.** The server drives one running game. Run one client (and one agent) per game; calls are
executed one at a time.

**Instructions.** The server sends usage instructions at initialization, but some clients do not pass them to the
model. The `guide` tool returns the full guide (`sc3k_mcp/guide.md`); tell your agent to call it first, or paste
the guide into the agent's system prompt.

**Tool count.** There are 81 tools. If your model handles fewer tools better, expose a subset with the client's
tool filter. A practical core set:
`guide, game_launch, game_status, list_cities, load_city, start_trial, save_city, metrics, city_status, get_budget,
population_details, zone_summary, map_text, tile_info, building_info, query, find_empty_area, tool_catalog, build,
bulldoze, building_options, place_building, set_tax, set_department_funding, ordinances, set_ordinance, petitions,
answer_petition, advance_time, set_auto_mode, dialog_status, close_dialog`.

**Results and errors.** Every tool returns compact JSON text, except `guide` (markdown), `map_text` (an ASCII map) and `screenshot` /
`map_image`, which return a PNG (and are not needed: all data is available as text). Failures are MCP tool errors (`isError: true`) whose text is JSON
`{"error": "...", "hint": "..."}`. Tool annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`) are set on
every tool, so clients that ask for confirmation before destructive actions can do so (`docs/TOOLS.md` lists the
kind of each tool).

**Output size.** Most results are small. `map_text` / `map_data` over a whole 256x256 map are large; use a region or
`step` (Claude Code caps a tool result at 25,000 tokens by default, `MAX_MCP_OUTPUT_TOKENS`).

**Schemas.** Parameters use only strings, integers, numbers, booleans, arrays and "T or null"; no `$ref`. Gemini
CLI's schema sanitizing and OpenAI's strict-schema conversion both handle them.

## Claude Code

```bash
claude mcp add --scope project --transport stdio simcity3000 -- C:\Python313\python.exe -m sc3k_mcp
```

or `.mcp.json` in the project folder:

```json
{
  "mcpServers": {
    "simcity3000": {
      "type": "stdio",
      "command": "C:\\Python313\\python.exe",
      "args": ["-m", "sc3k_mcp"],
      "env": { "PYTHONPATH": "C:\\path\\to\\SiMCP-3000" },
      "timeout": 600000
    }
  }
}
```

## Claude Desktop

`%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "simcity3000": {
      "command": "C:\\Python313\\python.exe",
      "args": ["-m", "sc3k_mcp"],
      "env": { "PYTHONPATH": "C:\\path\\to\\SiMCP-3000" }
    }
  }
}
```

## OpenAI Codex CLI

`~/.codex/config.toml` (or `.codex/config.toml` in a trusted project):

```toml
[mcp_servers.simcity3000]
command = 'C:\Python313\python.exe'
args = ["-m", "sc3k_mcp"]
cwd = 'C:\path\to\SiMCP-3000'
startup_timeout_sec = 30
tool_timeout_sec = 600

[mcp_servers.simcity3000.env]
PYTHONPATH = 'C:\path\to\SiMCP-3000'
```

or `codex mcp add simcity3000 --env PYTHONPATH=C:\path\to\SiMCP-3000 -- C:\Python313\python.exe -m sc3k_mcp` and then
raise `tool_timeout_sec` in the file. `enabled_tools = [...]` limits the tools.

## OpenAI Agents SDK (Python)

```python
import asyncio
from agents import Agent, Runner
from agents.mcp import MCPServerStdio

async def main():
    async with MCPServerStdio(
        name="simcity3000",
        params={
            "command": r"C:\Python313\python.exe",
            "args": ["-m", "sc3k_mcp"],
            "env": {"PYTHONPATH": r"C:\path\to\SiMCP-3000"},
        },
        client_session_timeout_seconds=600,   # the default 5 s is too short for loads and advance_time
        cache_tools_list=True,                # the tool list does not change while running
    ) as server:
        agent = Agent(
            name="Mayor",
            instructions="You run a SimCity 3000 city through the simcity3000 tools. Call guide first.",
            mcp_servers=[server],
        )
        result = await Runner.run(agent, "Launch the game, load 'Berlin, Germany' and summarise its finances.",
                                  max_turns=30)
        print(result.final_output)

asyncio.run(main())
```

`tool_filter=create_static_tool_filter(allowed_tool_names=[...])` (from `agents.mcp`) limits the tools;
`mcp_config={"convert_schemas_to_strict": True}` on the Agent enables strict schemas.

## Gemini CLI

`~/.gemini/settings.json` (or `.gemini/settings.json` in a project). Use a server name without underscores; the
tools then appear as `mcp_simcity3000_<tool>`.

```json
{
  "mcpServers": {
    "simcity3000": {
      "command": "C:\\Python313\\python.exe",
      "args": ["-m", "sc3k_mcp"],
      "cwd": "C:\\path\\to\\SiMCP-3000",
      "env": { "PYTHONPATH": "C:\\path\\to\\SiMCP-3000" },
      "timeout": 600000
    }
  }
}
```

or `gemini mcp add -s user -e PYTHONPATH=C:\path\to\SiMCP-3000 --timeout 600000 simcity3000 C:\Python313\python.exe -m sc3k_mcp`.
`includeTools` / `excludeTools` limit the tools; `"trust": true` skips the per-call confirmations.

## Google Agent Development Kit (Python)

```python
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

root_agent = LlmAgent(
    model="gemini-2.5-pro",
    name="mayor",
    instruction="You run a SimCity 3000 city through the simcity3000 tools. Call guide first.",
    tools=[
        McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=r"C:\Python313\python.exe",
                    args=["-m", "sc3k_mcp"],
                    env={"PYTHONPATH": r"C:\path\to\SiMCP-3000"},
                ),
                timeout=600,
            ),
            # tool_filter=["guide", "metrics", "advance_time", ...],
        )
    ],
)
```

ADK's class and module names have changed between versions (`MCPToolset` in older releases); check the version you
use.

## Local models with Ollama

`live/other_agent.py` is a complete, minimal agent loop for any model served by [Ollama](https://ollama.com) that
supports tool calling (no API key; the model runs locally): it starts the server over stdio, gives the model the
tool schemas exactly as the server publishes them, runs the tools it calls and feeds back the results.

```bash
python live/other_agent.py qwen3:0.6b "Load the saved city 'Madison, WI' and tell me its funds."
```

By default it offers a small set of tools (a small local context fits them easily); `TOOLS=all` offers all of
them. Tested with Qwen 3 (0.6B): with all 86 game tools offered it chose `game_status` and answered correctly; it
loaded a city with the right `load_city` arguments and read the server's error messages correctly. A model that
small still mixes up facts in its answers - use a larger model for real play. Models without tool support in
Ollama (Gemma 3, Phi-3) are refused by Ollama itself.

## HTTP transport

For clients that connect to a URL instead of starting the server:

```bash
python -m sc3k_mcp --transport streamable-http --port 8765
```

The endpoint is `http://127.0.0.1:8765/mcp` (`--transport sse` serves `/sse` for older clients). It binds to this
machine only by default. The server controls a program on this computer, so do not expose it to a network without
your own authentication in front of it. Examples: Claude Code `{"type": "http", "url": "http://127.0.0.1:8765/mcp"}`;
Gemini CLI `{"httpUrl": "http://127.0.0.1:8765/mcp"}`; OpenAI Agents SDK
`MCPServerStreamableHttp(params={"url": "http://127.0.0.1:8765/mcp"}, client_session_timeout_seconds=600)`.

## MCP Inspector

Browse and call the tools by hand:

```bash
npx @modelcontextprotocol/inspector C:\Python313\python.exe -m sc3k_mcp
```

## Your own code (Python MCP SDK)

```python
import asyncio, json, os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(command="python", args=["-m", "sc3k_mcp"],
                                   env={**os.environ, "PYTHONPATH": r"C:\path\to\SiMCP-3000"})
    async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
        await s.initialize()
        await s.call_tool("game_launch", {})
        await s.call_tool("start_trial", {"name": "mcp_e2e", "seed": 7})
        res = await s.call_tool("advance_time", {"years": 1, "record": "month"})
        print(res.isError, json.loads(res.content[0].text)["series"][-1])

asyncio.run(main())
```

`live/t6_stdio.py` is a complete example that drives about 50 calls this way.
