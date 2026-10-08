# SimCity 3000 MCP: guide for agents

This server plays a live copy of SimCity 3000 Unlimited (Windows). Every number comes from the game's memory and
every action goes through the game's own code, so the game's costs, rules and availability apply exactly as for a
human player. Nothing needs screenshots: `screenshot` and `map_image` exist only for clients that can view images.
The `guide` tool returns this text (or one section of it).

## Start

1. `game_launch` starts the game (or attaches to a running one) and waits for the main menu.
2. Then one of:
   - `load_city(name)`: a saved city (`list_cities` shows the files and their kinds).
   - `new_city(...)`: a new city on generated terrain (difficulty, start year, map size, terrain settings).
   - `load_city(name, kind="starter_town" | "terrain")`: a new city on a prepared map.
   - `load_scenario(name)`: a scenario with goals (`scenario_status`).
   - `start_trial(name, seed)`: a reproducible experiment (see Experiments).
3. `city_status` or `metrics` to see where you stand.

The simulation stays paused except while `advance_time` or `run_realtime` runs.

## Map and coordinates

- Tiles are addressed as (x, y), 0-based. `city_status.map_size` gives the width and height (64, 128, 192 or 256).
- `map_text` draws rows = y (top to bottom) and columns = x (left to right), with axis labels and a legend.
- Map edges: y=0 is the NW edge, x=0 NE, x=max SW, y=max SE (as the game's Neighbors Map and terrain editor name
  them).
- Buildings are placed by their top-left tile; a building's footprint is its rect [x0, y0, x1, y1] (inclusive).
- Data layers (`map_data`, `map_text`, `layer_stats`, `tile_info`): landvalue, crime, police, fire, air,
  water_pollution, radiation, garbage, power, water, pipes, traffic, aura, flammability, density. `tile_info` adds
  the game's labels (e.g. traffic None / Light / Medium / Heavy / Congested) and whether water is salt or fresh.

## Building

- `tool_catalog` lists the build tools and how each is used: line tools (road, rail, power_line, pipe, highway,
  subway) drag from (x, y) to (x2, y2); area tools (zones, dezone, landfill, seaport, airport, level_terrain) cover a
  rectangle; click tools (stations, services, parks, trees...) act on one tile per call (or every tile of a
  rectangle).
- `build` / `bulldoze` / `build_many` report the cost charged (0 = the game refused) and what changed.
- Power plants, water buildings, garbage buildings, landmarks and rewards come from the game's pickers:
  `building_options(picker)` shows what is available now (by year, technology and rewards earned),
  `place_building(name, x, y)` places one.
- `find_empty_area(width, height)` finds flat, unzoned, unbuilt space.
- Zoned land develops on its own, as the game decides (demand, power, water, roads, land value); `advisors` say what
  holds growth back and `zone_summary.zoned_land` counts zoned tiles that are still empty.

## Time

- `advance_time(days, months, years)` runs exactly that long, one game day at a time as fast as the engine can, then
  pauses again. A large city (256x256, ~800,000 people) runs about 60 game days per second, a small one several
  hundred.
- It returns early when the game opens a window (a question, the year-end Budget window, a scenario result) or when
  `max_seconds` of real time have passed (default 50, to stay within client timeouts). The result then has
  `stopped_early` and `remaining_days`; call `advance_time(days=remaining_days)` to continue. Splitting a run this
  way gives exactly the same result as one long call.
- `set_auto_mode("info")` makes advance_time close windows that only inform (budget, tips, notes) and keep going, so
  only real decisions stop it. Recommended for long runs.
- The game settles taxes and department costs into the funds once a year, on 1 January; building costs are charged
  at once.
- `advance_time(..., record="month")` also returns a `metrics` snapshot at each month boundary (or day / week / year).
- `run_realtime(speed, seconds)` lets the game run in real time at speed 1 (turtle) .. 4 (african swallow); not
  reproducible. Needed for disasters, which stop the calendar until they are over.

## Questions, dialogs and petitions

- When an action makes the game ask something (e.g. "build a bridge?"), the tool's result says so and the game
  waits. `dialog_status` shows the window (title, text, buttons); `close_dialog(button)` answers it, after which a
  waiting build completes.
- Petitions (citizens, advisors, neighbor and business deal offers) queue up: `petitions` lists them,
  `answer_petition(id, accept)` answers. New neighbor deals cannot be requested; the game proposes them when a
  connection (road, rail, pipe, power line...) to that neighbor exists and supply / demand conditions hold.
- `game_events` returns what the news ticker announced since its last call.
- When a scenario ends (its goals met, or its time up), the game shows the results window: `scenario_status` has the
  final rank (1 is best), `close_dialog` answers with "Replay Scenario", "Play Another Scenario" or "Return to Main
  Menu".

## Scenarios

- Play: `load_scenario(name)` (`list_cities(kind="scenario")`), `scenario_status` for the goals and the months
  elapsed; when it ends the results window offers "Replay Scenario", "Play Another Scenario", "Return to Main Menu".
- Read: `scenario_file(name)` shows any scenario without playing it - its goals, rank titles, texts and every
  script in the game's scenario language (conditions, pop-ups, disasters, timers). The shipped ones are good
  examples.
- Write: `create_scenario(name, base_city, goals, months, ...)` makes a new scenario from a saved city (set the
  city up first and `save_city` it): goals such as population at least N or crime at most N, checked once a month;
  all goals met = rank 1, the time limit passed first = rank 2. Then play it with `load_scenario(name)`. Useful for
  experiments: the same challenge, replayed by different strategies.

## Money

- `get_budget`: funds, taxes, department funding and costs, bonds, and ledgers by month (fares, deals, ordinances).
- `set_tax(zone, rate)`, `set_department_funding(department, percent)`, `set_ordinance(name, enabled)`
  (`ordinances` shows what each costs or earns per month at the city's current size), `issue_bond(amount)` (repaid
  over 10 years at 1.2 x the principal; no early repayment).
- With Auto Budget off the game opens the Budget window every 1 January (`set_auto_budget`, `set_auto_mode`).

## Observing

| question | tool |
|---|---|
| overall state, cheap | `city_status`, `metrics` |
| money | `get_budget`, `ordinances`, `deals` |
| people: ages, education, health, jobs, schools, hospitals, garbage | `population_details` |
| what is built, residents and jobs per zone type, undeveloped zones | `zone_summary`, `buildings`, `building_counts` |
| one place | `tile_info`, `building_info`, `query` (the game's own Query window, line by line) |
| a layer's distribution (e.g. police coverage of homes) | `layer_stats` |
| layout | `map_text`, `map_data` |
| traffic and transit | `transit`, `layer_stats(layer="traffic", where="roads")` |
| history | `graphs` |
| advice and news | `advisors`, `news`, `game_events`, `petitions` |
| rewards and their conditions | `rewards` |
| neighbors and connections | `neighbors`, `deals` |
| disasters in progress | `disasters` |
| approval, power by fuel type, water service | `city_status` |
| the game's own settings (display, sound, music tracks, auto go to disasters) | `preferences`, `set_preferences` |
| the city's look (landscape, trees, building style) and description | `city_options`, `set_city_options` |
| user-made (Building Architect) buildings shown in place of default ones | `building_replacements`, `replace_building` |
| the game window's camera, overlays and toolbars, pictures | `set_view`, `center_view`, `take_snapshot`, `screenshot` |
| the Photo Album: snapshots, their details and captions | `snapshots`, `snapshot_image`, `set_snapshot_caption`, `delete_snapshot` |
| cheat codes the game accepts and the ones used | `cheats` |

## Experiments and reproducibility

- `start_trial(name, seed)` restarts the game in a fresh process (about 12 s), seeds all of its randomness with
  `seed` and loads the file. The same seed + the same actions + the same `advance_time` calls give the same city,
  so strategies can be compared exactly; different seeds give independent trials of one strategy.
- Plain `load_city` is not reproducible (the game seeds its random numbers from the clock and keeps some traffic
  state across loads).
- `save_city(name)` saves the current city (never over the game's shipped cities; `overwrite=true` to replace your
  own file).
- Typical loop: `start_trial` -> actions -> `advance_time(years=1, record="month")` -> compare `metrics`.

## Errors

- A failed call returns an MCP tool error (isError = true) whose text is JSON: `{"error": "...", "hint": "..."}`.
  The hint says what to do (e.g. start the game with `game_launch`, answer an open dialog).
- Actions that the game refuses (no money, wrong place) are not errors: the result shows cost 0 or what happened.
- `ui_click` / `ui_drag` / `ui_key` / `ui_type` operate the game's screens directly (pixel coordinates of a
  1024x768 screenshot). They are a last resort for screens without a dedicated tool.

## Rules of play

- Only actions the game itself offers, at the game's prices; deals only as the game proposes them; scenarios that
  cannot be paused stay that way.
- Cheat codes are part of the game (`cheat`, as its Ctrl+Alt+Shift+C box), but they change its rules: free
  buildings, money, unlocked buildings, terrain. Use them only when asked to; an honest experiment checks that
  `cheats().used_in_this_session` is empty. "Crash" and "Internet chat" are refused.
- The tools never change memory values directly to gain an advantage; reading memory is only for observing.
