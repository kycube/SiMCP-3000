# SiMCP 3000

**MCP servers that let AI agents play SimCity 3000 Unlimited - and design new buildings for it.**

SiMCP 3000 is two [Model Context Protocol](https://modelcontextprotocol.io) servers for **SimCity 3000 Unlimited**
(the stock GOG build 2.0.949, Windows):

- **simcity3000** (`python -m sc3k_mcp`, 86 tools): plays the game. It reads the game's state from process memory
  and acts by calling the game's own code on its UI thread, so costs, placement rules, availability and the
  simulation are the game's own. No screenshots are needed to know anything: every number comes from memory.
  Time steps exactly and reproducibly, which makes it a tool for city-efficiency experiments as much as for play.
- **buildingarchitect** (`python -m bat_mcp`, 47 tools): creates new buildings, either with the game's own
  Building Architect or straight from a photograph, and shows them as images without screenshots (see
  [Building Architect server](#building-architect-server)).

It works with any MCP client and any model: Claude Code / Claude Desktop, OpenAI Codex CLI and the OpenAI Agents
SDK, Gemini CLI and Google's Agent Development Kit, editors with MCP support, or your own code. Every tool is fully
described in its JSON schema, carries the standard MCP annotations (read-only / destructive / idempotent) and
reports failures as MCP tool errors with a JSON `{error, hint}`.

> SiMCP 3000 is a fan project, not affiliated with or endorsed by Electronic Arts or Maxis. SimCity is a trademark of
> Electronic Arts Inc. You need your own copy of SimCity 3000 Unlimited; this repository contains no game files.

| Document | For |
|---|---|
| [docs/CLIENTS.md](docs/CLIENTS.md) | Install, and connecting Claude, OpenAI, Gemini / ADK and other clients (timeouts, tool filters, HTTP) |
| [sc3k_mcp/guide.md](sc3k_mcp/guide.md) | How an agent plays: coordinates, building, time, dialogs, money, experiments, errors (also the `guide` tool) |
| [docs/TOOLS.md](docs/TOOLS.md) | Every tool with its parameters, types, defaults and annotations (generated from the server) |
| [bat_mcp/guide.md](bat_mcp/guide.md), [docs/BAT_TOOLS.md](docs/BAT_TOOLS.md) | The Building Architect server: agent guide and generated tool reference |
| [notes/LIVE_FACTS.md](notes/LIVE_FACTS.md) | Verified memory layouts and recipes behind the tools |

## Quick start

1. Windows, SimCity 3000 Unlimited (GOG) installed, Python 3.10+.
2. `python -m pip install -e .` in this folder (or set `PYTHONPATH` to it in your client's config).
3. Build the bridge DLL that the servers inject into the game: `bridge\build.bat` (needs Visual Studio or its free
   Build Tools with "Desktop development with C++"). Or download the `bridge-dlls` artifact of a CI run and set
   `SC3K_BRIDGE_DLL` to its `sc3kbridge.dll`.
4. Register the stdio server `python -m sc3k_mcp` (and `python -m bat_mcp` for buildings) with your client
   (examples for each client in [docs/CLIENTS.md](docs/CLIENTS.md)); give it a tool timeout of a few minutes.
5. Ask the agent to call `guide`, then `game_launch` and `load_city` / `new_city` / `start_trial`.

`python -m sc3k_mcp --transport streamable-http --port 8765` serves the same tools at `http://127.0.0.1:8765/mcp`
for clients that connect to a URL. Set `SC3K_GAME_DIR` if the game is not in the GOG default folder.

## Tests

- `python -m pytest` (install with `pip install -e ".[test]"`): offline tests that need no game - the sprite and
  database formats, authored facades and the software renderer, roofs, both servers' tool schemas over MCP stdio,
  and that the generated tool references are current. With the game installed it also round-trips the
  Architect's sample projects byte for byte. CI runs it on every push, and builds the bridge DLLs.
- `live/`: tests against the running game or Building Architect (`t6_stdio.py` drives the game server over MCP
  stdio, `t9_trials.py` checks reproducibility, `b1_stdio.py` the Architect server, `p1_photo.py` the photo route),
  plus the memory tools used to find things (`memscan.py`, `refs.py`, `dump.py`, `trace_run.py`, `watch_run.py`).
  Most game tests load a test city saved as `mcp_e2e`: make one with `new_city` (128x128, founded 1900, a small
  powered town with water) and `save_city("mcp_e2e")`. Coordinates in `t6_stdio.py` refer to the developers' copy;
  adjust them for yours.

## Tools (86)

| Group | Tools |
|---|---|
| Help | `guide` (how to use the server, by topic) |
| Lifecycle | `game_launch`, `game_status`, `start_trial` (reproducible experiment: fresh game + seeded randomness + load), `new_city` (name, mayor, difficulty, start year, size, disasters, terrain: hills/water/trees, river/lake/mountain, coasts), `generate_terrain`, `edit_terrain`, `finish_map_editor`, `list_cities`, `load_city` (saved city, starter town, real-city terrain, scenario), `load_scenario`, `scenario_status`, `save_city`, `rename_city`, `set_auto_budget`, `preferences`, `set_preferences` (traffic / pedestrian / animation display, auto go to disasters, tips, music and the songs in rotation, sound effects, ambient sound, volumes, 3D sound), `set_city_options` (landscape, tree and building styles: North American / European / Asian; description), `building_replacements` / `replace_building` / `reset_building_replacements` (show default buildings as user-made Building Architect buildings, as the game's Building Replacement Manager does), `quit_game` |
| Observe | `metrics` (one flat efficiency snapshot), `city_status` (incl. power produced by fuel type, water served %, approval), `map_text` / `map_data` / `map_image` / `layer_stats` (terrain, zones, buildings and every data layer: land value, crime, police, fire, air and water pollution, radiation, landfill garbage, power, water, pipes, traffic, aura, flammability, density), `tile_info` (every layer at a tile with the game's labels, salt or fresh water), `building_info` / `buildings` (state, residents / jobs, service, plant fuel / capacity / age, water source and intake, treatment, recycling, waste-to-energy, stations' passengers...), `zone_summary` (incl. undeveloped zoned land), `population_details` (ages, EQ, life expectancy, workforce, unemployment, schools / colleges / hospitals, libraries / museums, garbage flows and landfill fullness), `transit`, `rewards`, `building_counts`, `find_empty_area`, `graphs` (14 history series), `news`, `game_events`, `advisors` (messages and mood), `disasters`, `query` (the game's own Query window for any tile), `city_options` (styles, description), `screenshot`, `center_view`, `set_view` (rotation, zoom, underground and data-view overlays, layers, grid, toolbars) |
| Photo Album | `take_snapshot`, `snapshots` (with each one's city, mayor, date, population, funds and caption), `snapshot_image`, `set_snapshot_caption`, `delete_snapshot` (to the Recycle Bin) |
| Cheats | `cheats` (the codes the game accepts and the ones used), `cheat` (as the game's cheat box; "Crash" and "Internet chat" refused) |
| Build | `tool_catalog`, `build` (line / area / click tools by tile; reports what changed, read back from memory), `bulldoze`, `building_options` (what each game picker offers now), `place_building` (power / water / garbage / landmark / reward buildings by name, chosen in the game's own picker), `build_many` |
| Economy | `get_budget` (taxes, departments, bonds, ledgers by month), `set_tax`, `set_department_funding`, `ordinances` (monthly amount of every ordinance at the current city size), `set_ordinance`, `issue_bond`, `petitions` (with text and the real deal terms), `answer_petition` |
| Neighbors and deals | `neighbors` (population, border edge, connections, deals), `deals` (deals in force, proposals, business deals, penalties due), `cancel_deal`, `discuss_deal` (the game's terms window: Keep / Cancel / Impact Analysis) |
| Time | `advance_time` (exact game days, deterministic, fast; time budget with `remaining_days`; `record="month"` etc. returns a `metrics` series), `run_realtime` (speeds 1-4, incl. african swallow), `set_auto_mode` (stop at every game window, or close informational ones and stop only at decisions), `set_paused`, `set_speed` |
| Disasters | `set_disasters`, `trigger_disaster`, `disasters` (what is happening where, damage), `dispatch` (police / fire / military units, early warning) |
| Dialogs / UI | `dialog_status` (title, text, fields, buttons of any game window), `close_dialog` (press a button by its label, or close), `ui_click`, `ui_drag`, `ui_key`, `ui_type` |

Coordinates are tiles `(x, y)` as the game stores them (`map_text` rows are y, columns x). Buildings are placed by
their top-left tile. `advance_time` months and years follow the calendar.

## Building Architect server

`python -m bat_mcp` (server name `buildingarchitect`, 47 tools) drives Apps\Baapp.exe, the "Building Architect Plus"
that makes new buildings for SimCity 3000, through the same injected bridge (it is built on the same Maxis
framework). Every edit uses the program's own functions; every picture is read from its render buffer or decoded
from the files it writes - never a screenshot.

| Group | Tools |
|---|---|
| Session | `guide`, `bat_launch`, `bat_status`, `bat_quit` |
| Projects | `projects`, `project_image` (the preview stored in a .bld), `new_building` (lot 1x1..5x5, name, architect, description, type), `open_building`, `save_building`, `building_info`, `set_building_properties` |
| Construction | `shapes` (the 16 block shapes and what each face is), `blocks`, `place_blocks`, `fill_box`, `roof` (hip / gable / pyramid / shed roofs and their unions, with valleys, from rectangles), `remove_blocks`, `copy_blocks` (copy / cut and paste a box with its paint and props: storeys, repeated bays), `rotate_building` (the Rotate button), `undo` / `redo` (per call) |
| Paint and decorate | `library` (walls, roofs, ground, 220 colours, details by set, props by category, custom), `texture_sheet` (40 labelled per picture), `texture_image`, `paint_faces` / `detail_faces` (textures laid out continuously like the Paintbrush), `fill_paint` (the Fill tool: a whole wall, roof or the lot ground in one call), `place_detail` (a whole multi-face decal), `paint_box` (walls, roof and window details on the outside of a box), `place_props` / `placed_props` / `remove_props` (trees, cars, signs, rooftop units...) |
| Photo to building (no Architect) | `photo_add`, `photo_view` (pixel grid for reading coordinates), `photo_rectify` (perspective removed), `photo_model_render` (a model of 3D parts in metres - boxes, polygons, round towers, cones, true roof planes with bargeboards, finials and ridge caps, beams, see-through panels, stock props - whose walls are authored facades drawn from the photo's measurements (windows, doors, bands, friezes, arches, railings, ornaments; or patterns, textures, photo regions), rendered by the server in the game's projection and light: anti-aliased, soft shadows), `photo_model_export` (the game's sprite format with full-resolution zoom 5; `install=true` adds it to its own DAT in Apps\BARender), `photo_buildings` / `photo_building_remove` (what is installed; take one out) |
| Your own content | `create_texture` (a new paint or detail from a picture file, base64 or pixel rows + palette, into Apps\BACustom), `prop_template` (the exact drawing guide for a prop of any size), `create_prop` (four view pictures, 32-256 px, + its .met) |
| See and render | `view_image` (the live construct / paint / detail / props view from memory, any side or all four, cropped to the building), `game_building_image` (any of the game's own buildings and landmarks, for scale and style), `render_building` (the Architect's own renderer: the four rotations exactly as SimCity draws them; `install=true` adds the building to the game's BAT.DAT), `rendered_buildings`, `rendered_image` |

How it was made and verified: `notes/BAT_PHASE0.md`, `re/agents/{bld,batrender,baapp,batlib}/REPORT.md` (the .bld format
with a byte-exact round-trip on all 17 sample projects, the rendered sprite format, the program's model and
commands), `live/b1_stdio.py` (builds a cottage - walls, gable, windows, grass, a tree - over MCP stdio, saves and
renders it). A full end-to-end test - the Empire State Building recreated from a photograph, then compared with the
game's own landmark - is written up in `notes/BAT_E2E_EMPIRE_STATE.md`, and a second one - a Queen Anne Victorian
house on a 2x2 lot, with the renderer's colour response measured - in `notes/BAT_E2E_VICTORIAN.md`.
`examples/empire_state/` and `examples/victorian/` replay them (`python live/mcp_run.py bat examples/<name>/build.py`),
and the lessons are in the agent guide's "Best practices" section. Photo to building: `notes/PHOTO_TO_BUILDING.md` (the Haas-Lilienthal House from one photograph in three versions, verified inside SimCity 3000; the best practices are in the agent guide, `guide(topic="photo")`), `examples/photo_queen_anne/` (`authored.py`; `v3_ingame_vs_photo.png` = the game beside the photo), regression `live/p1_photo.py` (synthetic photo, no game needed).

## How it works

```
MCP client --stdio or HTTP--> Python FastMCP server (64-bit)
                                | ReadProcessMemory: all observation
                                | WriteProcessMemory + SendMessageTimeout(WM_APP+0x3C3) to the bridge's window
                                v
                  SC3U.exe (32-bit) + sc3kbridge-<sha1>.dll (injected from %TEMP%\sc3k-mcp)
```

- The bridge creates a message-only window on the game's UI thread (temporary WH_GETMESSAGE hook; the game window
  is never subclassed) and runs every command there under SEH (`status -100` on a crash, game keeps running).
- **Time**: SC3U simulates on its own engine thread, driven by a clock. `advance_time` pauses the clock, unpauses
  the engine, calls the clock's own AdvanceDay one day at a time and waits for the engine to drain each day. Exact
  and reproducible; a small city runs several hundred days per second.
- **Tools**: menu command ids (from `Sys\SYS.PAK MenuItem.INI`) are executed through the game's command server;
  the installed tool's own mouse handlers are then driven through tile coordinates by temporarily overriding the
  camera's screen-to-world picking inside the game. Buildings from the pickers are constructed with the game's
  ploppable-tool class for their occupant id.
- **Dialogs**: the game's GZWIND modal windows are detected (`wm+0x194`) and read through their child windows
  (texts, rich texts, list boxes, buttons and the labels of option buttons); they are answered by pressing a
  button the way a player does, or with EndModal. Lifecycle flows (new/load/save, terrain editor, preferences)
  drive the game's own screens with synthetic input relative to each window's rectangle.
- **Questions during a build** (bridge over water, connection to a neighbor) do not block: the tool runs from
  the game's message loop, the server returns the question, and `close_dialog` with the chosen answer finishes
  the build and reports its cost.
- **Deals, advisors, scenarios, disasters** are read from the game's own objects and answered through the game's
  own handlers, so terms, penalties and goals are the game's.
- Synthetic input fakes `GetCursorPos`/`GetAsyncKeyState`/`GetKeyState` inside the game only; the real mouse is
  never moved.
- **Tool registration** (`sc3k_mcp/registry.py`): each tool's docstring `Args:` section becomes its JSON-schema
  parameter descriptions, its kind sets the MCP annotations, and `{"error": ...}` results become MCP tool errors.
  `python scripts/gen_tool_docs.py --check` verifies that every tool is fully documented within the strictest
  common client limits and that docs/TOOLS.md is current.

## Layout

| Path | What |
|---|---|
| `sc3k_mcp/server.py` | MCP tools (game) |
| `bat_mcp/server.py`, `app.py`, `model.py`, `render.py`, `sprites.py`, `bldfile.py`, `custom.py`, `roofs.py`, `render3d.py`, `photomodel.py`, `datwriter.py`, `guide.md` | Building Architect server: tools; process; the model and library through the program's functions; rendering; sprite / thumbnail decoders (BAT renders and the game's own sprites); .bld reader/writer; BACustom textures / props and prop templates; roofs as height fields; photo route: software renderer in the game's projection, photo models and materials, the game's sprite-file writer |
| `sc3k_mcp/registry.py` | tool registration: schema descriptions, annotations, error results |
| `sc3k_mcp/guide.md` | the agent guide (`guide` tool) |
| `sc3k_mcp/game.py` | launch/attach, bridge calls, time stepping, tools, buildings, camera, screenshots, input |
| `sc3k_mcp/city.py` | statistics, budget/taxes/departments/bonds, ordinances, petitions, news, deals, advisors, disasters |
| `sc3k_mcp/layers.py`, `buildings.py` | per-tile data layers; per-building data |
| `sc3k_mcp/lifecycle.py` | new/load/save/exit, preferences, terrain editor and modal dialogs |
| `sc3k_mcp/mapview.py`, `catalog.py`, `text.py` | map rendering; tool/building catalog; game text tables |
| `sc3k_mcp/data/` | tables extracted from the game's data (agent types, occupants, ordinances, rewards, advisor moods...) |
| `bridge/sc3kbridge.cpp`, `sc3kplug.cpp`, `build.bat` | the bridge DLL injected into the game and the optional GZCOM plugin stub (`build.bat` writes `bridge/build/`, not tracked) |
| `docs/` | `CLIENTS.md` (connecting clients), `TOOLS.md` / `BAT_TOOLS.md` (generated tool references) |
| `scripts/gen_tool_docs.py` | generates and checks docs/TOOLS.md and docs/BAT_TOOLS.md |
| `notes/` | development notes: `LIVE_FACTS.md` (verified recipes), `PHASE0.md`, `GZCOM.md`, `UI_ATLAS.md`, `ADDRESSES.md`, `RE_BRIEF.md`, and the Building Architect write-ups (`BAT_*.md`, `PHOTO_TO_BUILDING.md`) |
| `re/` | reverse-engineering reports per subsystem (`agents/*/REPORT.md`) and the static helpers (`pe.py`, `inventory.py`, `vtlen.py`, `syspak.py`); see `re/README.md` |
| `live/` | scripts that talk to the live game (tests t1-t11; `t6_stdio.py` drives the server over MCP stdio; `b1_stdio.py` the Architect server; `p1_photo.py` the photo route; `mcp_run.py` runs any list of tool calls against either server) and the memory tools used to find things |
| `tests/` | offline pytest suite (no game needed); `.github/workflows/ci.yml` runs it and builds the bridge DLLs |
| `examples/` | complete examples as plain MCP calls: the Empire State Building (4x4) and a Queen Anne house (2x2) with the Architect, the Haas-Lilienthal House from a photograph without it (`examples/README.md`, with credits) |

## Known limits

- When the monitor sleeps, DDrawCompat stops presenting until the game window is clicked once (game logic is
  unaffected; `screenshot` reports it).
- New neighbor deals cannot be requested: the game only proposes them (as petitions) when a connection exists
  and supply/demand conditions hold (see `re/agents/deals/REPORT.md`). Business deals come the same way when the
  treasury is low; an accepted one becomes a reward building to place with `place_building(..., picker="reward")`.
- Bonds cannot be repaid early: the game has no such option (`re/agents/features/REPORT.md`).
- Scenarios that "cannot be paused" keep their rule: `set_paused`/`set_speed` refuse, `advance_time` still steps
  exactly and leaves the game running afterwards.
- Terrain-editor coastlines are toggled by clicking the Pick Features preview's edge strips (the game has no
  command for them); the result is read back from the editor's memory (coast mask).
- The game settles its budget yearly on 1 January. With Auto Budget off it also opens the Budget window then;
  `set_auto_mode("info")` closes it (the budget stays as set) and keeps going.
- `save_city` never overwrites the game's shipped cities (GOG manifest) and replaces other files only with
  `overwrite=True`.
- Screen resolution is fixed at 1024x768 windowed by `game_launch` and not offered by `set_preferences`: the
  screen recipes (dialog layouts, toolbar and picker positions, `ui_*` and screenshot coordinates) are measured at
  that size.
- Outside the game itself: the Building Architect (`Apps\Baapp.exe`) has its own server (`bat_mcp`, above); the
  Scenario Creator is a separate program not covered, and the game's online features (SimCity.com exchange) no longer
  exist. Buildings made with the Architect show up in the game as user-made buildings (`building_replacements`).
  The Building Architect's "building sets" (.bst / .scs) are stubs in this build of the program (its menu
  strings exist, the functions do nothing), so there is nothing to cover.
- Building Architect: `render_building(install=true)` writes Apps\BARender\BAT.DAT (backed up first) and needs
  SimCity 3000 closed (the game keeps that file open). The Architect's Edit List dialog (choosing which projects go
  into BAT.DAT) is replaced by `render_building`, which keeps every other building already in the file. A render
  clears the Architect's undo history (the program does the same). Zoom in `view_image` stops at the program's
  per-lot limits. Saving leaves out blocks that are completely enclosed (the program's own behaviour; the building
  looks the same). `create_texture` / `create_prop` write into Apps\BACustom (the folder the Architect reads user
  content from) and never replace the Architect's own files; changing an existing custom prop's size reaches the
  Architect's own prop tool only after it restarts (it keeps the first definition).
- Reproducibility: the game seeds its random generators from the clock and keeps some traffic state across city
  loads, so plain runs differ (+-4% population after a year in a tiny city). `start_trial(name, seed)` restarts
  the game, seeds every generator (per-object, global and rand(), including the ones used while loading) and loads
  the file: the same seed + the same actions + the same advance_time calls give the same city (verified: 3 fresh
  runs, one year, identical; actions in between replay identically; splitting advance_time by time budget or
  recording metrics changes nothing); different seeds give independent trials.
- Speed: a 128x128 test city runs ~400 days/s; Berlin (256x256, 794k people) ~60-80 days/s (5-6 s per year),
  steady over 28 simulated years with flat handle counts. Display preferences do not change it (measured).
- The live tests write files named `mcp_*` / `MCP *` into the game folders (test cities, snapshots, Architect
  projects, `BACustom` paints and props) and leave them there for inspection; remove them when done. Note that the
  game stores the Windows user name in saved cities and snapshot details.

## Removing

`python -m pip uninstall simcp-3000`; delete `%TEMP%\sc3k-mcp`. If the optional plugin stub was installed, delete
`Apps\PlugIn\` in the game folder while the game is closed. Buildings installed by the photo route live in
`Apps\BARender\MCP Photo Buildings.DAT` (`photo_building_remove` takes them out one by one).

## License

MIT (see `LICENSE`). SimCity 3000 itself is not included and remains Electronic Arts' property.
