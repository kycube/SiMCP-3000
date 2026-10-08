# Contributing to SiMCP 3000

Thanks for helping. A few rules keep the servers useful to any agent and honest about the game.

## Ground rules

- **The game's own code, the game's own rules.** Tools act by calling the game's (or the Building Architect's)
  own functions and read state from memory; they never write memory values to gain an advantage. If the game
  doesn't offer something (requesting a neighbor deal, repaying a bond early), there is no tool for it.
- **Any client, any model.** Tools are registered with `@tool(kind)` (`sc3k_mcp/registry.py`): the docstring's
  `Args:` section becomes the JSON schema, the kind sets the MCP annotations, `{"error": ...}` results become MCP
  tool errors. No vendor-specific wording in tool text.
- **No game files in the repository.** No binaries, dumps, sprites, saved cities or snapshots (saved cities and
  snapshot details also carry the Windows user name). Reverse-engineering findings go in `re/agents/*/REPORT.md`
  and `notes/`, with addresses as `MODULE preferred-VA` and how they were verified.
- **Verify live.** A new tool or recipe is done when it has worked against the running game (or Architect); note
  what was checked in `notes/LIVE_FACTS.md` / `notes/BAT_PHASE0.md` and, where possible, add it to a `live/` test.

## Before a pull request

```bash
python -m pip install -e ".[test]"
python -m pytest
python scripts/gen_tool_docs.py
```

`gen_tool_docs.py` regenerates `docs/TOOLS.md` and `docs/BAT_TOOLS.md`; `--check` (run by the tests) fails when a
tool is under-documented or the references are stale. With the game installed, also run the live test for the
area you touched (`live/t6_stdio.py` for the game server, `live/b1_stdio.py` for the Building Architect,
`live/p1_photo.py` for the photo route).

## Building the bridge

`bridge\build.bat` (and `bridge\build.bat plug` for the optional plugin stub) needs Visual Studio or its Build
Tools with the C++ toolset; the output in `bridge\build\` is not tracked. CI builds both DLLs on every push.
