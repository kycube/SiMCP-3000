"""MCP server exposing SimCity 3000 Unlimited (GOG) as tools.

Observation reads the game's memory; actions call the game's own code on its UI thread through an injected
bridge DLL (building tools are driven through their own mouse handlers with tile coordinates, so costs and
placement rules are the game's). Where no dedicated tool exists, the ui_* tools operate the game's screens with
synthetic input (the real mouse is never moved) and screenshot shows the result.

Coordinates: tile (x, y), x = 0..W-1, y = 0..H-1 as the game stores them (map_text prints y as rows, x as
columns). Buildings are placed by their top-left tile.
"""

from __future__ import annotations

import datetime
import io
import json
import os
import time

from mcp.server.fastmcp import FastMCP, Image

from . import album as album_mod
from . import catalog
from .city import City, DEPARTMENTS
from .game import Game, GameError, calendar_days, date_to_jdn, jdn_to_date
from .lifecycle import Lifecycle
from .mapview import MapView
from .registry import tool as _register
from .buildings import Buildings

mcp = FastMCP(
    "simcity3000",
    instructions=(
        "Plays a live SimCity 3000 Unlimited game: everything is read from the game's memory and every action goes "
        "through the game's own code (normal costs and rules). Call guide() for the full how-to. Start with "
        "game_launch, then load_city / new_city, or start_trial(name, seed) for a reproducible experiment. Observe "
        "with metrics, city_status, get_budget, population_details, zone_summary, map_text, tile_info; act with "
        "build, place_building, set_tax, set_ordinance...; run time with advance_time (exact game days; it returns "
        "early with remaining_days after max_seconds or when the game asks something: dialog_status / close_dialog). "
        "Tiles are (x, y) as map_text shows them. Errors come back as tool errors with JSON {error, hint}."
    ),
)



def tool(kind: str, **kw):
    """Register a documented MCP tool of this kind (read | observe | set | act | destructive); see registry.py."""
    return _register(mcp, kind, **kw)


game = Game()
city = City(game)
life = Lifecycle(game)
mapview = MapView(city)
buildings_mod = Buildings(city, mapview.layers)


def _png(img) -> Image:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return Image(data=buf.getvalue(), format="png")


def _guard(fn, *a, _attach: bool = True, **kw):
    try:
        if _attach and (not game.proc or not game.proc.alive() or not game.bridge):
            game.attach(launch=False)            # attach to a running game automatically (never launches)
        return fn(*a, **kw)
    except (GameError, KeyError, ValueError) as e:
        return {"error": e.args[0] if isinstance(e, KeyError) and e.args else str(e)}
    except Exception as e:                       # bridge timeouts, memory reads of a dying process, ...
        out = {"error": f"{type(e).__name__}: {e}"}
        if game.proc and not game.proc.alive():
            out["hint"] = "SimCity 3000 is no longer running: game_launch starts it again, then load_city"
        elif "timed out" in str(e).lower():
            out["hint"] = "the game did not answer in time; dialog_status shows whether a game window is waiting"
        return out


# ================================================================ lifecycle
_GUIDE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guide.md")


@tool("read", structured_output=False)
def guide(topic: str = "") -> str:
    """How to use this server (markdown text): starting a game, map coordinates, building, time, dialogs and petitions,
    money, which tool answers which question, reproducible experiments, errors and the rules of play. Read it once
    before playing.

    Args:
        topic: A section title or part of it (e.g. "time", "experiments"); empty for the whole guide.
    """
    text = open(_GUIDE, encoding="utf-8").read()
    parts = text.split("\n## ")
    sections = {p.split("\n", 1)[0].strip(): "## " + p for p in parts[1:]}
    if not topic:
        return text
    hits = [v for k, v in sections.items() if topic.lower() in k.lower()]
    if not hits:
        return {"error": f"no section matches {topic!r}", "topics": list(sections)}
    return "\n\n".join(hits) + "\n\n(other sections: " + ", ".join(sections) + ")"


@tool("set")
def game_launch(reload_bridge: bool = False) -> dict:
    """Start SimCity 3000 Unlimited (windowed 1024x768, intro skipped) and attach to it, or attach to the copy that is
    already running; waits for the main menu. Call this first, then load_city, new_city, load_scenario or start_trial.

    Args:
        reload_bridge: Development only: re-inject a freshly built bridge DLL into the running game. Leave false.
    """
    def run():
        st = game.attach(launch=True, reload_bridge=reload_bridge)
        if st.get("launched"):
            deadline = time.time() + 30                # the main menu animates in after the window appears
            while time.time() < deadline and not life.at_main_menu() and not game.city():
                time.sleep(0.25)
            time.sleep(1.0)
            st = {**game.status(), "launched": True}
        return st
    return _guard(run, _attach=False)


@tool("read")
def game_status() -> dict:
    """Whether the game runs, which screen it shows (main menu, city, terrain editor), the city basics (name, date, funds,
    paused, speed) and any open game dialog. Cheap; safe to call at any time.
    """
    def run():
        st = game.status()
        if st.get("running"):
            st["dialog"] = life.modal()
            if life.at_main_menu():
                st["screen"] = "menu"
            elif st.get("screen") == "city" and life.terrain_panel():
                st["screen"] = "terrain_editor"
                st["terrain"] = life.terrain_settings()
        return st
    return _guard(run)


@tool("destructive")
def new_city(name: str = "New City", mayor: str = "Mayor", difficulty: str = "easy", start_year: int = 1900,
             size: str = "large", disasters: bool = False, auto_budget: bool = False, regenerate_terrain: int = 0,
             hills: int | None = None, water: int | None = None, trees: int | None = None,
             feature: str | None = None, coasts: list[str] | None = None, accept_terrain: bool = True) -> dict:
    """Start a new city through the game's New City screens. The current city is discarded without saving (save_city
    first if it matters). The simulation starts paused in the chosen year.

    Args:
        name: City name.
        mayor: Mayor name.
        difficulty: easy ($50,000 to start) | medium ($20,000) | hard ($10,000, as a loan).
        start_year: 1900 | 1950 | 2000.
        size: Map size: miniature (64x64 tiles) | small (128x128) | medium (192x192) | large (256x256).
        disasters: Enable random disasters.
        auto_budget: Enable the game's Auto Budget (otherwise the Budget window opens every 1 January).
        regenerate_terrain: Re-roll the random terrain this many extra times.
        hills: Terrain hills 0-100; omit to keep the game's default.
        water: Terrain water 0-100; omit to keep the default.
        trees: Terrain trees 0-100; omit to keep the default.
        feature: none | lake | river_nw_se | river_sw_ne | mountain; omit to keep the default.
        coasts: Map edges with sea, any of NW (the y=0 edge), NE (x=0), SE (y=max), SW (x=max); [] for none; omit to
            keep the default.
        accept_terrain: true starts the city at once; false stays in the terrain editor (generate_terrain,
            edit_terrain, then finish_map_editor).
    """
    def run():
        terrain = any(v is not None for v in (hills, water, trees, feature, coasts))
        r = life.new_city(name, mayor, difficulty, start_year, size, disasters, auto_budget, regenerate_terrain,
                          accept_terrain=accept_terrain and not terrain)
        if terrain:
            r["terrain"] = life.set_terrain(hills, water, trees, feature, coasts)
            if accept_terrain:
                r = {**life.accept_terrain(), "terrain": r["terrain"]}
        return r
    return _guard(run)


@tool("act")
def generate_terrain(hills: int | None = None, water: int | None = None, trees: int | None = None,
                     feature: str | None = None, coasts: list[str] | None = None) -> dict:
    """Terrain editor only (after new_city(accept_terrain=false) or loading a terrain): set the terrain parameters and
    press Re-Generate. Returns the settings as the editor shows them.

    Args:
        hills: 0-100; omit to keep.
        water: 0-100; omit to keep.
        trees: 0-100; omit to keep.
        feature: none | lake | river_nw_se | river_sw_ne | mountain; omit to keep.
        coasts: Any of NW (the y=0 edge), NE (x=0), SE (y=max), SW (x=max); [] for none; omit to keep.
    """
    return _guard(lambda: {"terrain": life.set_terrain(hills, water, trees, feature, coasts, regenerate=True)})


@tool("act")
def edit_terrain(tool: str, x: int, y: int, x2: int | None = None, y2: int | None = None) -> dict:
    """Terrain editor only: use one of the editor's free tools, dragging from tile (x, y) to (x2, y2). In a running city
    use build with raise_terrain / lower_terrain / level_terrain / trees / water instead (those cost money).

    Args:
        tool: raise | lower | level | trees | water | bulldoze.
        x: Start tile x.
        y: Start tile y.
        x2: End tile x; omit for a single tile.
        y2: End tile y; omit for a single tile.
    """
    def run():
        t = life.editor_tool(tool)
        cam = game.u32(game.view() + 0xB8)
        pts = [(x * 256, y * 256, 0)] + ([(x2 * 256, y2 * 256, 0)] if x2 is not None and y2 is not None else [])
        r = game.run_tool(t, cam, pts, len(pts) == 1, "edit_terrain")
        return _asking({k: v for k, v in r.items() if k not in ("cost", "funds")} or {"ok": True})
    return _guard(run)


@tool("act")
def finish_map_editor() -> dict:
    """Terrain editor only: accept the terrain and start the city (paused).
    """
    return _guard(life.accept_terrain)


@tool("read")
def list_cities(kind: str | None = None) -> dict:
    """Files the game can load from its Cities folder (saved cities, starter towns, real-city terrains, scenarios), each
    with the name and kind to pass to load_city or start_trial.

    Args:
        kind: Only this kind: city | starter_town | terrain | scenario; omit for all.
    """
    return _guard(lambda: {"files": [c for c in life.list_cities() if kind in (None, c["kind"])]})


@tool("destructive")
def load_city(name: str, kind: str = "city", city_name: str = "", mayor: str = "", difficulty: str = "easy",
              disasters: bool = False, auto_budget: bool = False) -> dict:
    """Load a file the way the game's Load menu does; the current city is discarded without saving. kind city loads a
    saved city (paused). starter_town and terrain start a new city on that map with the New City Options below; a
    terrain then opens the terrain editor (generate_terrain / edit_terrain / finish_map_editor). For reproducible
    experiments use start_trial instead.

    Args:
        name: File name as list_cities shows it (no extension), e.g. "Berlin, Germany".
        kind: city | starter_town | terrain | scenario (scenarios are better started with load_scenario).
        city_name: Name for the new city (starter_town / terrain only).
        mayor: Mayor name (starter_town / terrain only).
        difficulty: easy | medium | hard (starter_town / terrain only).
        disasters: Enable random disasters (starter_town / terrain only).
        auto_budget: Enable Auto Budget (starter_town / terrain only).
    """
    return _guard(life.load_city, name, False, kind, city_name, mayor, difficulty, disasters, auto_budget)


@tool("destructive")
def start_trial(name: str, seed: int, kind: str = "city") -> dict:
    """Start a reproducible experiment: quit and restart the game (a fresh process, about 12 s), make all of its randomness
    follow `seed`, then load the file as load_city does. The same seed, the same actions and the same advance_time
    calls give exactly the same city; different seeds give independent trials of one strategy. (Plain load_city is not
    reproducible: the game seeds its random numbers from the clock and keeps some traffic state across loads.)

    Args:
        name: File name as list_cities shows it.
        seed: Any integer; the same seed reproduces the same run.
        kind: city | starter_town | terrain | scenario (as load_city).
    """
    def run():
        try:
            game.attach(launch=False)              # a running game (possibly not attached yet)
        except GameError:
            pass
        if game.proc and game.proc.alive():
            life.exit_game()
            deadline = time.time() + 20
            while game.proc.alive() and time.time() < deadline:
                time.sleep(0.25)
        st = game.attach(launch=True)
        deadline = time.time() + 30
        while time.time() < deadline and not life.at_main_menu() and not game.city():
            time.sleep(0.25)
        time.sleep(1.0)
        rng = game.set_random_seed(seed)
        r = life.load_city(name, False, kind)
        return {**r, "seed": seed, "pid": st.get("pid"),
                "randomness": {k: rng[k] for k in ("seeders_patched", "global_generators_reset")}}
    return _guard(run, _attach=False)


@tool("destructive")
def load_scenario(name: str) -> dict:
    """Start one of the game's scenarios; the current city is discarded. Returns the briefing and the goals
    (scenario_status tracks them). Some scenarios cannot be paused or sped up.

    Args:
        name: Scenario name as list_cities(kind="scenario") shows it.
    """
    def run():
        r = life.load_city(name, False, "scenario")
        return {**r, "scenario": _scenario()}
    return _guard(run)


def _subst(t, extra=None):
    """Fill the game's text tokens the way it does (%YOURCITY%, %YOURNAME%, %YEAR%, ...)."""
    if not t or "%" not in t:
        return t
    b = game.city_basics(game.need_city())
    tokens = {"%YOURNAME%": b["mayor"], "%MAYOR%": b["mayor"], "%YOURCITY%": b["name"], "%CITYNAME%": b["name"],
              "%YEAR%": b["date"][:4]}
    if "%POPULATION%" in t:
        tokens["%POPULATION%"] = f"{city.stats().get('population', 0):,}"
    tokens.update(extra or {})
    for k, v in tokens.items():
        t = t.replace(k, str(v))
    return t


def _scenario() -> dict:
    sc = city.scenario()
    for k in ("description", "result"):
        if sc.get(k):
            sc[k] = _subst(sc[k])
    for gl in sc.get("goals", []):
        gl["goal"] = _subst(gl["goal"])
    return sc


@tool("read")
def scenario_status() -> dict:
    """The running scenario: name, description, goals with met / not met, months elapsed and, once it has ended, the
    final rank (1 is best) and result text. When a scenario ends the game shows its results window (dialog_status):
    answer it with close_dialog("Replay Scenario"), "Play Another Scenario" or "Return to Main Menu".
    {"scenario": false} outside scenarios.
    """
    return _guard(_scenario)


@tool("destructive")
def save_city(name: str, overwrite: bool = False) -> dict:
    """Save the current city as Cities/<name>.sc3 through the game's Save As dialog. An existing file is replaced only with
    overwrite=true; the game's own shipped cities are never overwritten.

    Args:
        name: File name without extension.
        overwrite: Replace an existing file of that name.
    """
    return _guard(life.save_city, name, overwrite)


@tool("set")
def rename_city(name: str | None = None, mayor: str | None = None) -> dict:
    """Rename the city and/or its mayor (the game's City Options window).

    Args:
        name: New city name; omit to keep.
        mayor: New mayor name; omit to keep.
    """
    return _guard(life.rename_city, name, mayor)


@tool("set")
def set_auto_budget(enabled: bool) -> dict:
    """Turn the game's Auto Budget option on or off. With it off the game opens the Budget window every 1 January
    (set_auto_mode("info") closes it and carries on).

    Args:
        enabled: true = on.
    """
    def run():
        c = game.need_city()
        game.call(game.vfn(c, 0x94 // 4), [1 if enabled else 0], this=c)
        return {"auto_budget": bool(game.proc.read(c + 0x1F1, 1)[0])}
    return _guard(run)


@tool("destructive")
def quit_game() -> dict:
    """Quit SimCity 3000 without saving. game_launch starts it again.
    """
    return _guard(life.exit_game)


# ================================================================ observation
@tool("read")
def city_status() -> dict:
    """The city at a glance: name, mayor, date, funds, population, commercial and industrial jobs, RCI demand (-1..1 per
    zone), power and water capacity and use, buildings without power / water, average land value and crime, average
    air / water / garbage pollution, the disasters and auto-budget options, whether a disaster is running, paused,
    speed and map size. Cheap; call it often.
    """
    def run():
        st = game.city_basics(game.need_city())
        st.update(city.stats())
        return st
    return _guard(run)


@tool("read")
def metrics(traffic: bool = True) -> dict:
    """One flat snapshot of the numbers that measure how well the city runs, for logging every step of an experiment:
    date, population, funds, yearly income / expense estimates and their difference, debt, tax rates, RCI demand, jobs,
    unemployment %, education (EQ), life expectancy, power and water use vs capacity, unserved buildings, land value,
    crime, air / water pollution, garbage produced vs handled, school / college / hospital use vs capacity and
    (traffic=true) the share of road tiles with heavy or congested traffic. advance_time(record=...) returns a series of
    these.

    Args:
        traffic: Include the road congestion share (scans the traffic layer).
    """
    return _guard(_metrics, traffic)


def _metrics(traffic: bool = True) -> dict:
    c = game.need_city()
    st = game.city_basics(c)
    s = city.stats()
    b = city.budget()
    p = city.population_details()
    g = p["garbage"]
    out = {"date": st["date"], "population": s["population"], "funds": b["funds"],
           "income_estimate_year": b["income_estimate_year"], "expense_estimate_year": b["expense_estimate_year"],
           "net_estimate_year": b["income_estimate_year"] - b["expense_estimate_year"], "debt": b["debt"],
           "tax_rates": {k: v["rate"] for k, v in b["taxes"].items()},
           "demand": s["demand"], "commercial_jobs": s["commercial_jobs"], "industrial_jobs": s["industrial_jobs"],
           "unemployment_percent": p["unemployment_percent"], "education_eq": p["education_eq"],
           "life_expectancy": p["life_expectancy"],
           "power_used": s["power"]["used"], "power_capacity": s["power"]["capacity"],
           "unpowered_buildings": s["power"]["unpowered_buildings"],
           "water_used": s["water"]["used"], "water_capacity": s["water"]["capacity"],
           "unwatered_buildings": s["water"]["unwatered_buildings"],
           "land_value_avg": s["land_value_avg"], "crime_avg": s["crime_avg"],
           "air_pollution_avg": s["pollution"]["air"], "water_pollution_avg": s["pollution"]["water"],
           "garbage_produced": g["produced_tons_per_year"],
           "garbage_handled": g["to_landfill"] + g["recycled"] + g["incinerated"] + g["waste_to_energy"] +
                              g["exported_by_deals"],
           "school_use": [p["schools"]["students"], p["schools"]["desks"]],
           "college_use": [p["colleges"]["students"], p["colleges"]["capacity"]],
           "hospital_use": [p["hospitals"]["patients"], p["hospitals"]["beds"]]}
    if traffic:
        from .layers import stats as lstats
        lab = lstats(mapview.layers, "traffic", "roads").get("labels", {})
        n = sum(lab.values())
        out["roads_heavy_or_congested_percent"] = round(100 * (lab.get("Heavy", 0) + lab.get("Congested", 0))
                                                         / n, 1) if n else 0
    return out


@tool("read")
def map_text(layer: str = "auto", x0: int = 0, y0: int = 0, x1: int | None = None, y1: int | None = None,
             step: int = 1) -> str:
    """Exact ASCII map of a region, one character per tile (rows = y, columns = x, with axis labels and a legend): the
    cheapest way to see the layout without images.

    Args:
        layer: auto (buildings over zones over terrain) | terrain | zones | buildings | a data layer: landvalue, crime,
            police, fire, air, water_pollution, radiation, garbage, power, water, pipes, traffic, aura, flammability, density.
        x0: Left tile x.
        y0: Top tile y.
        x1: Right tile x, inclusive; omit for the map edge.
        y1: Bottom tile y, inclusive; omit for the map edge.
        step: Show every step-th tile (step > 1 gives an overview of a large map).
    """
    r = _guard(mapview.text, layer, x0, y0, x1, y1, step)
    return f"error: {r['error']}" if isinstance(r, dict) else r


@tool("read")
def map_data(layer: str, x0: int = 0, y0: int = 0, x1: int | None = None, y1: int | None = None,
             step: int = 1) -> dict:
    """Raw numbers of one data layer for a region, for analysis: rows[i][j] is the value at tile (x0 + j*step,
    y0 + i*step). At most 16,384 values per call (use step or a smaller region). tile_info gives the game's labels.

    Args:
        layer: landvalue | crime | police | fire | air | water_pollution | radiation | garbage | power | water | pipes |
            traffic | aura | flammability | density.
        x0: Left tile x.
        y0: Top tile y.
        x1: Right tile x, inclusive; omit for the map edge.
        y1: Bottom tile y, inclusive; omit for the map edge.
        step: Sample every step-th tile.
    """
    def run():
        from .layers import LAYERS
        if layer not in LAYERS:
            raise GameError(f"layer must be one of {list(LAYERS)}")
        W, H = city.size()
        xa, ya = max(0, x0), max(0, y0)
        xb = W - 1 if x1 is None else min(x1, W - 1)
        yb = H - 1 if y1 is None else min(y1, H - 1)
        st = max(1, step)
        xs, ys = range(xa, xb + 1, st), range(ya, yb + 1, st)
        if len(xs) * len(ys) > 16384:
            raise GameError(f"{len(xs) * len(ys)} values: use a larger step or a smaller region (max 16384)")
        shift, rows = mapview.layers.get(layer)
        return {"layer": layer, "x0": xa, "y0": ya, "step": st, "cell_tiles": 1 << shift,
                "rows": [[rows[x >> shift][y >> shift] for x in xs] for y in ys]}
    return _guard(run)


@tool("read")
def layer_stats(layer: str, where: str = "all", thresholds: list[int] | None = None) -> dict:
    """Distribution of a data layer over a set of tiles: count, mean, min / percentiles / max, the game's labels (e.g.
    traffic None / Light / Medium / Heavy / Congested) and the share of tiles at or above each threshold. Example:
    police coverage on residential tiles with thresholds [50, 100].

    Args:
        layer: A data layer, as map_data.
        where: Which tiles: all | zoned | residential | commercial | industrial | a zone name (res_dense, landfill...) |
            roads | highways | rail | subways | stations | network.
        thresholds: Values t for which to report the share of tiles with value >= t.
    """
    def run():
        from .layers import stats
        return stats(mapview.layers, layer, where, thresholds)
    return _guard(run)


@tool("read", structured_output=False)
def map_image(scale: int = 3, overlay: str | None = None) -> Image:
    """Top-down colour picture of the whole map (one tile = scale pixels), optionally tinted by a data layer. Only useful
    to clients that can view images; map_text and map_data carry the same information as text.

    Args:
        scale: Pixels per tile.
        overlay: A data layer to tint the map with (as map_data); omit for none.
    """
    try:
        return _png(mapview.image(scale, overlay))
    except GameError as e:
        raise ValueError(str(e))


def _tile(x: int, y: int) -> None:
    W, H = city.size()
    if not (0 <= x < W and 0 <= y < H):
        raise GameError(f"tile ({x}, {y}) is outside the {W}x{H} map")


@tool("read")
def tile_info(x: int, y: int) -> dict:
    """Everything at one tile: corner altitudes and water, zone, occupants (category, name, footprint) and every data
    layer (land value, crime, police, fire, pollution, radiation, garbage, power, water, pipes, traffic, aura,
    flammability) with the game's labels.

    Args:
        x: Tile x, 0 .. map width - 1 (city_status map_size).
        y: Tile y, 0 .. map height - 1.
    """
    return _guard(lambda: (_tile(x, y), mapview.tile_info(x, y))[1])


@tool("read")
def buildings(name_filter: str | None = None, x0: int = -1, y0: int = -1, x1: int = -1, y1: int = -1,
              include_trees: bool = False, limit: int = 300, details: bool = False) -> dict:
    """List occupants (buildings and network pieces) with category, name and footprint rect [x0, y0, x1, y1]. With
    details=true: buildings only, each with state, residents / jobs, power and water service, land value and its class
    data (as building_info).

    Args:
        name_filter: Only names containing this text, e.g. "Plant", "Road", "Res"; omit for all.
        x0: Region left tile x (-1 with the others = whole map).
        y0: Region top tile y.
        x1: Region right tile x.
        y1: Region bottom tile y.
        include_trees: Include trees (there can be tens of thousands).
        limit: Maximum number of entries returned.
        details: Buildings only, with per-building data.
    """
    def run():
        if details:
            recs = buildings_mod.records((x0, y0, x1, y1))
            if name_filter:
                f = name_filter.lower()
                recs = [r for r in recs if f in r["name"].lower() or f in r["type"].lower()]
            return {"count": len(recs), "buildings": recs[:limit]}
        occ = city.occupants((x0, y0, x1, y1))
        if not include_trees:
            occ = [o for o in occ if o["category"] != 300]
        if name_filter:
            f = name_filter.lower()
            occ = [o for o in occ if f in o["name"].lower() or f in o.get("building", "").lower()]
        return {"count": len(occ), "occupants": [{k: o[k] for k in ("category", "name", "building", "rect", "layer")
                                                  if k in o} for o in occ[:limit]]}
    return _guard(run)


@tool("read")
def building_info(x: int, y: int, game_query: bool = True) -> dict:
    """Everything the game knows about the building covering tile (x, y): name, type, zone / density / wealth, state
    (working, abandoned, under construction, destroyed...), residents or jobs, powered, watered, land value; power
    plants: fuel, output, capacity, age, life span; water buildings: source, capacity, use, intake, pipe connection;
    police / fire: coverage radius and cost; jails: inmates; stations: passengers per day; garbage, recycling and
    treatment buildings: capacity and use; every data layer at that tile; and (game_query) the lines of the game's
    own Query window for it (e.g. crimes and arrests per month, performance rating, attendance, grades).

    Args:
        x: Any tile x of the building.
        y: Any tile y of the building.
        game_query: Also run the game's Query tool on it and include its lines (about a second).
    """
    def run():
        _tile(x, y)
        recs = buildings_mod.records((x, y, x, y))
        if not recs:
            raise GameError(f"no building at ({x}, {y})")
        out = {**recs[0], "tile": mapview.layers.at(x, y)}
        if game_query:
            q = life.query(x, y)
            out["game_query"] = {l["label"]: l["value"] for l in q.get("lines", [])}
        return out
    return _guard(run)


@tool("read")
def zone_summary() -> dict:
    """City-wide building totals: buildings by state, residents and jobs; per zone / density / wealth (or industry type)
    the number of buildings, working, abandoned, residents and jobs; and per zone type the zoned tiles and how many of
    them are still undeveloped.
    """
    return _guard(buildings_mod.summary)


@tool("read")
def population_details() -> dict:
    """Demographics and services, city-wide: population by age and, per age group, education (EQ) and life
    expectancy (the Population window's three pages), children / workforce / seniors, education (EQ) and life
    expectancy, jobs and unemployment, schools / colleges / hospitals (users, capacity, staff, grade, strikes),
    library and museum capacity, garbage flows and landfill fullness, average pollution.
    """
    return _guard(city.population_details)


@tool("read")
def building_counts() -> dict:
    """Number of occupants per category name (trees, road pieces, houses, plants...), most common first.
    """
    def run():
        from collections import Counter
        return dict(Counter(o["name"] for o in city.occupants()).most_common())
    return _guard(run)


@tool("read", structured_output=False)
def screenshot(scale: float = 0.75, x0: int = 0, y0: int = 0, x1: int | None = None, y1: int | None = None) -> Image:
    """PNG of the game window's client area (1024x768), only for clients that can view images: every number the other
    tools return is read from memory, not from pictures. Full-size pixel coordinates are what ui_click expects.

    Args:
        scale: Shrink factor for the returned picture (coordinates stay full-size).
        x0: Crop left pixel.
        y0: Crop top pixel.
        x1: Crop right pixel; omit for the edge.
        y1: Crop bottom pixel; omit for the edge.
    """
    try:
        img = game.capture()
    except GameError as e:
        raise ValueError(str(e))
    if x1 is not None or y1 is not None or x0 or y0:
        img = img.crop((x0, y0, x1 if x1 is not None else img.width, y1 if y1 is not None else img.height))
    if scale != 1:
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))))
    return _png(img)


@tool("set")
def center_view(x: int, y: int, zoom: int | None = None) -> dict:
    """Centre the game's camera on tile (x, y). Only changes what the screen and screenshots show.

    Args:
        x: Tile x.
        y: Tile y.
        zoom: 0 (farthest) .. 4 (closest); omit to keep.
    """
    return _guard(game.set_view, x=x, y=y, zoom=zoom)


@tool("set")
def set_view(rotation: int | None = None, zoom: int | None = None, data_view: str | None = None,
             zones: bool | None = None, transport: bool | None = None, power_lines: bool | None = None,
             trees: bool | None = None, zoned_buildings: bool | None = None,
             other_buildings: bool | None = None, grid: bool | None = None, toolbars: bool | None = None) -> dict:
    """The game window's camera and display layers, as its rotate / zoom buttons and Layer Views panel set them
    (only what the screen and screenshots show). Returns the view: centre tile, zoom, rotation, data view, layers.
    Call it without arguments to read the view.

    Args:
        rotation: 0..3 (quarter turns); omit to keep.
        zoom: 0 (farthest) .. 4 (closest); omit to keep.
        data_view: normal | subways | pipes (the underground views) | aura | crime | power | flammability |
            landvalue | pollution | traffic | density (the game's data overlays); omit to keep.
        zones: Show zone colours.
        transport: Show roads, rail and other transport.
        power_lines: Show power lines.
        trees: Show trees.
        zoned_buildings: Show buildings on zones.
        other_buildings: Show all other buildings.
        grid: Show the terrain grid (the G key).
        toolbars: Show (true) or hide (false) the game's toolbars and status bar (its Hide / Show Toolbars tab).
    """
    layers = {k: v for k, v in dict(zones=zones, transport=transport, power_lines=power_lines, trees=trees,
                                    zoned_buildings=zoned_buildings, other_buildings=other_buildings).items()
              if v is not None}

    def run():
        if toolbars is not None:
            life.set_toolbars(toolbars)
        out = game.set_view(zoom=zoom, rotation=rotation, data_view=data_view, layers=layers or None, grid=grid)
        if isinstance(out, dict):
            out["toolbars"] = life.toolbars_shown()
        return out
    return _guard(run)


@tool("read")
def find_empty_area(width: int, height: int, near_x: int | None = None, near_y: int | None = None,
                    flat: bool = True, limit: int = 5) -> dict:
    """Find places to build: up to `limit` non-overlapping rectangles of width x height tiles with nothing built (trees are
    fine), no zoning, no water and (flat=true) level ground, nearest to (near_x, near_y). Returns their top-left and
    bottom-right tiles.

    Args:
        width: Width in tiles (along x).
        height: Height in tiles (along y).
        near_x: Search around this tile x; omit for the map centre.
        near_y: Search around this tile y; omit for the map centre.
        flat: Require level ground (most buildings need it).
        limit: Maximum number of areas returned.
    """
    def run():
        near = (near_x, near_y) if near_x is not None and near_y is not None else None
        return {"areas": mapview.free_areas(max(1, width), max(1, height), near, flat, max(1, min(limit, 50)))}
    return _guard(run)


# ================================================================ building
@tool("read")
def tool_catalog() -> dict:
    """The build tools for build / build_many (name, kind, description) and the buildings of the power, water and garbage
    pickers. kind line: drag from (x, y) to (x2, y2); area: the rectangle (x, y)..(x2, y2); click: one tile (buildings
    are placed by their top-left tile).
    """
    return {"tools": {k: {"kind": v[1], "what": v[2]} for k, v in catalog.TOOLS.items()},
            "pickers": {p: [v["name"] for _, v in catalog.picker_buildings(p)] for p in ("power", "water", "garbage")},
            "note": "place_building places any listed picker building (power/water/garbage) by name once the game "
                    "makes it available (year); see SC3BudgetLayer costs in get_budget/tool costs."}


def _asking(r: dict) -> dict:
    """A tool operation stopped at a game dialog: show the question and how to answer it."""
    if "pending" in r:
        m = life.modal()
        r["dialog"] = m
        r["note"] = ("the game is asking a question; answer it with close_dialog(button=one of "
                     f"{(m or {}).get('buttons')}) and the action completes (its cost is reported then)")
    return r


def _build(tool: str, x: int, y: int, x2: int | None, y2: int | None) -> dict:
    if tool not in catalog.TOOLS:
        raise GameError(f"unknown tool {tool!r} (see tool_catalog)")
    cmd, kind, _ = catalog.TOOLS[tool]
    if kind == "click":
        pts = [(x, y)]
        if x2 is not None and y2 is not None:      # click every tile of a rectangle (e.g. trees)
            pts = [(xx, yy) for xx in range(min(x, x2), max(x, x2) + 1) for yy in range(min(y, y2), max(y, y2) + 1)]
        out = {"cost": 0}
        for i in range(0, len(pts), 16):
            r = game.apply_tool(cmd, pts[i:i + 16], click_each=True)
            if "pending" in r:
                out.update(r)
                out["tiles_done"] = i
                return _asking(out)
            out["cost"] += r["cost"]
            out["funds"] = r["funds"]
        return out
    x2 = x if x2 is None else x2
    y2 = y if y2 is None else y2
    return _asking(game.apply_tool(cmd, [(x, y), (x2, y2)]))


def _snapshot(rect):
    """Occupants and zone tiles inside a tile rectangle (memory only), to report what an action changed."""
    from .city import ZONE_NAMES
    W, H = city.size()
    x0, y0, x1, y1 = max(0, rect[0]), max(0, rect[1]), min(W - 1, rect[2]), min(H - 1, rect[3])
    occ = {o["ptr"]: (o.get("building") or o["name"]) for o in city.occupants((x0, y0, x1, y1)) if o["layer"] < 2}
    rows = city.zones()
    zones = {(x, y): ZONE_NAMES.get(rows[x][y], rows[x][y]) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}
    return occ, zones


def _changes(before, after) -> dict:
    import collections
    (o0, z0), (o1, z1) = before, after
    added = collections.Counter(o1[p] for p in o1.keys() - o0.keys())
    removed = collections.Counter(o0[p] for p in o0.keys() - o1.keys())
    zoned = collections.Counter(z1[t] for t in z1 if z1[t] != z0.get(t))
    out = {}
    if added:
        out["built"] = dict(added)
    if removed:
        out["removed"] = dict(removed)
    if zoned:
        out["zone_tiles_now"] = dict(zoned)
    return out


def _build_noted(tool, x, y, x2, y2):
    rect = (min(x, x2 if x2 is not None else x) - 1, min(y, y2 if y2 is not None else y) - 1,
            max(x, x2 if x2 is not None else x) + 1, max(y, y2 if y2 is not None else y) + 1)
    small = (rect[2] - rect[0] + 1) * (rect[3] - rect[1] + 1) <= 64 * 64
    before = _snapshot(rect) if small else None
    r = _build(tool, x, y, x2, y2)
    if before and "pending" not in r:
        r.update(_changes(before, _snapshot(rect)))      # what the game actually changed (read from memory)
    if r.get("cost") == 0 and tool not in ("bulldoze",) and "pending" not in r and not r.get("built")             and not r.get("zone_tiles_now"):
        r["note"] = "the game charged nothing: its placement rules refused this (terrain, occupied, not allowed)"
    return r


@tool("act")
def build(tool: str, x: int, y: int, x2: int | None = None, y2: int | None = None) -> dict:
    """Use one of the game's build tools (tool_catalog) at the game's normal cost: line tools (road, rail, power_line,
    pipe...) from (x, y) to (x2, y2); area tools (zones, dezone, landfill...) over the rectangle; click tools
    (stations, services, parks, trees...) at (x, y) or at every tile of the rectangle. Returns the cost charged (0 = the
    game refused) and what changed, read back from memory. If the game asks a question (e.g. whether to build a bridge)
    the result says so: answer with close_dialog.

    Args:
        tool: Tool name from tool_catalog, e.g. road, res_light, power_line, police_station.
        x: Start tile x (a building's top-left tile).
        y: Start tile y.
        x2: End tile x; omit for one tile.
        y2: End tile y; omit for one tile.
    """
    return _guard(_build_noted, tool, x, y, x2, y2)


@tool("destructive")
def bulldoze(x: int, y: int, x2: int | None = None, y2: int | None = None) -> dict:
    """Demolish everything in the rectangle (x, y)..(x2, y2) with the game's bulldozer (normal demolition cost) and report
    what was removed.

    Args:
        x: Corner tile x.
        y: Corner tile y.
        x2: Opposite corner tile x; omit for one tile.
        y2: Opposite corner tile y; omit for one tile.
    """
    return _guard(_build_noted, "bulldoze", x, y, x2, y2)


PICKER_ORDER = ("power", "water", "garbage", "landmark", "reward")


PARK_CATEGORIES = range(14310, 14320)          # parks, playgrounds, ponds, fountains (National Park condition)


@tool("read")
def transit() -> dict:
    """Transportation overview: stations per mode (bus, rail, subway, subway-rail) with total and busiest passengers per
    day (as the game's Query computes them), the transit strike state and funding, the airport (air traffic, on-time
    flights) and seaport (port traffic) as their Query windows show them, fares income (year to date and by month)
    and road / highway / rail traffic distributions with the game's None..Congested labels.
    """
    def run():
        from collections import defaultdict
        from .layers import stats
        recs = [r for r in buildings_mod.records() if r.get("kind") == "station"]
        by = defaultdict(lambda: {"stations": 0, "passengers_per_day": 0, "busiest": []})
        for r in recs:
            m = by[r["mode"]]
            m["stations"] += 1
            m["passengers_per_day"] += r.get("passengers_per_day", 0)
            m["busiest"].append((r.get("passengers_per_day", 0), r["rect"][:2]))
        for m in by.values():
            m["busiest"] = [{"passengers_per_day": p, "at": xy} for p, xy in sorted(m["busiest"], reverse=True)[:5]]
        T = game.u32(game.need_city() + 0xAC)
        b = city.budget()
        ports = buildings_mod.ports()
        traffic = {w: {k: v for k, v in stats(mapview.layers, "traffic", w).items()
                       if k in ("tiles", "mean", "median", "p90", "max", "labels")}
                   for w in ("roads", "highways", "rail")}
        state = game.proc.read(T + 0x108, 1)[0]
        return {"stations": dict(by),
                "strike": {2: "none", 0: "threatened", 1: "on_strike"}.get(state, state),
                "months_on_strike": game.i32(T + 0x10C) if state == 1 else 0,
                "funding_percent": {"roads": game.proc.read(T + 0xE4, 1)[0], "transit": game.proc.read(T + 0xE5, 1)[0]},
                **ports,
                "fares_ytd": b["ledgers"]["transit_fares"]["ytd"],
                "fares_by_month": b["ledgers"]["transit_fares"]["by_month"], "traffic": traffic}
    return _guard(run)


@tool("read")
def rewards(check_picker: bool = True) -> dict:
    """Reward and business-deal buildings: what each needs (population, year, an extra condition such as EQ, life
    expectancy, parks, funds or airport size, from the game's City Planner table), the city's current values, whether
    the conditions are met, how many are built and whether the game's Rewards picker offers it now. Unlocked rewards are
    placed with place_building(..., picker="reward"); many are first offered as a petition (answer_petition).

    Args:
        check_picker: Also open the game's Rewards picker to confirm what it offers now.
    """
    def run():
        import json as _json
        import os as _os
        from collections import Counter
        data = _json.load(open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "data", "rewards.json")))
        st = city.stats()
        b = game.city_basics(game.need_city())
        pd = city.population_details()
        cats = Counter(o["category"] for o in city.occupants() if o["layer"] == 0)
        zones = city.zones()
        now = {"population": st.get("population", 0), "year": int(b["date"][:4]), "funds": b["funds"],
               "education_eq": pd["education_eq"], "life_expectancy": pd["life_expectancy"],
               "parks": sum(n for c, n in cats.items() if c in PARK_CATEGORIES),
               "airport_tiles": sum(row.count(15) for row in zones)}
        offered = set()
        if check_picker and not life.modal():
            offered = {i["name"] for i in life.picker_items(catalog.PICKERS["reward"][0])}
        out = []
        for r in data["rewards"]:
            need = {"population": r["population"], **({"year": r["year"]} if r["year"] else {}), **r["requires"]}
            met = all(now[k] >= v for k, v in need.items())
            e = {"name": (r["names"] or [r["ini_name"]])[0], "kind": r["kind"], "needs": need, "conditions_met": met,
                 "built": cats.get(r["category"], 0)}
            if r["petition"]:
                e["petition"] = r["petition"]
            if check_picker:
                e["offered_now"] = any(n in offered for n in r["names"])
            out.append(e)
        return {"city": now, "rewards": out}
    return _guard(run)


@tool("read")
def building_options(picker: str) -> dict:
    """What one of the game's building pickers offers right now (availability by year, technology and earned rewards is the
    game's own).

    Args:
        picker: power | water | garbage | landmark | reward.
    """
    def run():
        if picker not in catalog.PICKERS:
            raise GameError(f"picker must be one of {list(catalog.PICKERS)}")
        return {"picker": picker, "buildings": [i["name"] for i in life.picker_items(catalog.PICKERS[picker][0])]}
    return _guard(run)


@tool("act")
def place_building(name: str, x: int, y: int, picker: str | None = None) -> dict:
    """Place a building from one of the game's pickers (power plants, water buildings, garbage buildings, landmarks,
    rewards) by name with its top-left tile at (x, y), at the game's normal cost. The picker is opened and the building
    chosen there, so only what the game offers now can be placed (building_options).

    Args:
        name: Building name as building_options lists it, e.g. "Coal Power Plant".
        x: Top-left tile x.
        y: Top-left tile y.
        picker: power | water | garbage | landmark | reward; omit to guess from the name.
    """
    def run():
        order = [picker] if picker else []
        if not picker:
            try:
                _, b = catalog.find_building(name)
                cat = b.get("category") or 0
                guess = next((p for p, (_, cats) in catalog.PICKERS.items() if cats is not None and cat in cats), None)
                if guess:
                    order = [guess]
                elif 18000 <= cat < 19000:
                    order = ["landmark"]
            except KeyError:
                pass
            order += [p for p in PICKER_ORDER if p not in order]
        first = None
        for p in order:
            try:
                tool = life.choose_in_picker(catalog.PICKERS[p][0], name)
            except GameError as e:
                first = first or e
                continue
            before = {o["ptr"] for o in city.occupants((x, y, x, y))}
            cam = game.u32(game.view() + 0xB8)
            r = game.run_tool(tool, cam, [(x * 256, y * 256, 0)], True, "place_building")
            if "pending" in r:
                return _asking({"building": name, "picker": p, **r})
            new = [o for o in city.occupants((x, y, x, y)) if o["ptr"] not in before]
            return {"building": name, "picker": p, "cost": r["cost"], "funds": r["funds"], "placed": bool(new),
                    "footprint": new[0]["rect"] if new else None}
        raise first or GameError(f"{name!r} not found in any picker")
    return _guard(run)


@tool("act")
def build_many(actions: list[dict]) -> dict:
    """Run several build / place actions in order, stopping at the first error or game question. Each action is an object:
    {"tool": "road", "x": 10, "y": 5, "x2": 30, "y2": 5} (as build) or {"building": "Coal Power Plant", "x": 40,
    "y": 40, "picker": "power"} (as place_building). Returns each result and the total cost.

    Args:
        actions: List of action objects as described above.
    """
    results, total = [], 0
    for i, a in enumerate(actions):
        if not isinstance(a, dict) or "x" not in a or "y" not in a:
            results.append({"error": f"action {i} needs x and y (and a tool or a building): {a!r}"})
            return {"done": i, "results": results, "total_cost": total}
        if "building" in a:
            r = place_building(a["building"], a["x"], a["y"], a.get("picker"))
        else:
            r = build(a.get("tool", ""), a["x"], a["y"], a.get("x2"), a.get("y2"))
        results.append(r)
        if "error" in r:
            return {"done": i, "results": results, "total_cost": total}
        if "pending" in r:                       # the game asked a question: answer it, then send the rest
            return {"done": i, "waiting": True, "results": results, "total_cost": total,
                    "note": "the game asked a question during this action; answer with close_dialog (the action "
                            "then completes) and send the remaining actions again"}
        total += r.get("cost", 0)
    return {"done": len(actions), "results": results, "total_cost": total}


# ================================================================ economy
@tool("read")
def get_budget() -> dict:
    """Funds; tax rate, max and income per zone; department funding % and costs; yearly income / expense (to date and
    estimated); bonds (principal, total due, remaining, monthly payment) and debt; and the other ledgers (transit fares,
    neighbor and business deals, ordinance income / expense, other income) year to date and by calendar month (months
    after the current one still hold last year's amounts). income_ytd = taxes + all income ledgers; expense_ytd =
    departments + ordinance and deal expenses + bond payments.
    """
    def run():
        b = city.budget()
        for t in b["taxes"].values():
            t.pop("income_by_month", None)
        for d in b["departments"].values():
            d.pop("item", None)
        return b
    return _guard(run)


@tool("set")
def set_tax(zone: str, rate: int) -> dict:
    """Set a zone's property tax rate (as the Budget window's slider does).

    Args:
        zone: residential | commercial | industrial.
        rate: Percent, 0 .. the zone's max (get_budget shows it).
    """
    return _guard(city.set_tax, zone, rate)


@tool("set")
def set_department_funding(department: str, percent: int) -> dict:
    """Set a department's funding level (as the Budget window does).

    Args:
        department: police | fire | health | education | roads | transit.
        percent: 0 .. 200 (100 = full funding).
    """
    return _guard(city.set_department_funding, department, percent)


@tool("read")
def ordinances() -> dict:
    """All ordinances: enacted and available flags, the monthly amount each would bring (+ income) or cost (-) at the
    city's current size (as the Ordinances window estimates it; the actual amount for enacted ones), and the monthly
    totals of the enacted ones.
    """
    return _guard(lambda: {"ordinances": city.ordinances(), **city.ordinance_totals()})


@tool("set")
def set_ordinance(name: str, enabled: bool) -> dict:
    """Enact or repeal an ordinance (it must be available; see ordinances).

    Args:
        name: Ordinance name as ordinances lists it.
        enabled: true = enact, false = repeal.
    """
    return _guard(city.set_ordinance, name, enabled)


@tool("act")
def issue_bond(amount: int) -> dict:
    """Take out a bond (loan). The game rounds the amount down to a multiple of $5,000 and allows at most $25,000 per bond,
    10 bonds and $250,000 outstanding. It is repaid monthly over 10 years (1.2 x the principal in total) and the game
    has no early repayment.

    Args:
        amount: Dollars.
    """
    return _guard(city.issue_bond, amount)


# petition id -> (deal type, where its terms are: the proposal or the deal in force)
DEAL_PETITIONS = {**{i: ("buy_power", "pending") for i in (172, 173, 202, 175)},
                  **{i: ("sell_power", "pending") for i in (179, 180, 181, 248)},
                  **{i: ("buy_water", "pending") for i in (165, 166, 167, 168)},
                  **{i: ("sell_water", "pending") for i in (185, 186, 187, 189)},
                  **{i: ("export_garbage", "pending") for i in (196, 197, 247, 199)},
                  **{i: ("import_garbage", "pending") for i in (191, 192, 193, 194)},
                  177: ("buy_power", "active"), 170: ("buy_water", "active"), 195: ("export_garbage", "active"),
                  234: ("buy_power", "active"), 233: ("sell_power", "active"), 236: ("buy_water", "active"),
                  235: ("sell_water", "active"), 238: ("export_garbage", "active"),
                  237: ("import_garbage", "active")}


@tool("read")
def petitions(full: bool = False, ids: list[int] | None = None) -> dict:
    """Pending petitions and proposals (neighbor and business deals arrive this way): id, heading, who asks and the two
    answers (button1 = accept, button2 = reject; none = informational). Answer with answer_petition.

    Args:
        full: Also include the message, the advisor's advice and the reactions.
        ids: Only these petition ids.
    """
    def run():
        from .text import petition_text
        pending = {d["type"]: d for d in city.deals("pending")}
        active = {d["type"]: d for d in city.deals("active")}
        names = [n["name"] for n in city.neighbors()]
        out = []
        for p in city.petitions():
            if ids and p["id"] not in ids:
                continue
            t = petition_text(p["id"])
            if not full:
                t = {k: v for k, v in t.items() if k in ("heading", "name", "button1", "button2")}
            extra, deal = {}, None
            dt, src = DEAL_PETITIONS.get(p["id"], (None, None))
            if dt:
                deal = (pending if src == "pending" else active).get(dt)
            if deal:
                sell = dt.startswith("sell") or dt == "import_garbage"
                extra = {"%NEIGHBOR%": names[deal["neighbor"]] if deal["neighbor"] < 4 else "",
                         "%X%": f"{deal['quantity']:,}",
                         "%Y%": f"{deal['monthly'] if sell else deal['rate_per_1000']:,}",
                         "%W%": f"{deal['minimum_monthly']:,}", "%Z%": f"{deal['cancel_penalty']:,}",
                         "%YEAROFDEAL%": (deal.get("since") or "")[:4]}
                p = {**p, "deal": {**deal, "neighbor": extra["%NEIGHBOR%"]}}
            t = {k: _subst(v, extra) for k, v in t.items()}
            out.append({**p, **t})
        return {"petitions": out}
    return _guard(run)


@tool("read")
def graphs(span: str = "months", names: list[str] | None = None) -> dict:
    """History of the city's graphs as the game's Graphs window has them (Residents, Education, Health, Land Value, Crime,
    Approval Rating, Funds, City Size, Nat'l Pop, Commerce, Industry, Unemployment, Pollution, Traffic), in the graphs'
    own units, newest first.

    Args:
        span: months (last 12) | years (last 10) | decades (last 10).
        names: Only graphs whose name contains one of these texts.
    """
    def run():
        gr = city.graphs(span)
        if names:
            gr = {k: v for k, v in gr.items() if any(n.lower() in k.lower() for n in names)}
        return {"span": span, "graphs": gr}
    return _guard(run)


@tool("read")
def news() -> dict:
    """The news ticker's current headlines by category (status, news, petitions, advisors...). game_events returns only
    what is new since its last call.
    """
    return _guard(city.news)


@tool("read")
def neighbors() -> dict:
    """The four neighbor cities: name, mayor, population, the map edge each borders (and its quadrant on the game's
    Neighbors Map), the connections built to it (road, rail, highway, pipes, power lines, subway: a connection is what
    makes deals possible) and the deals with it.
    """
    def run():
        deals = city.deals("active")
        out = city.neighbors()
        for i, (n, (pos, _)) in enumerate(zip(out, life.NEIGHBOR_QUADRANTS)):
            n["edge"] = city.NEIGHBOR_EDGES[i]
            n["map_quadrant"] = pos
            n["connections"] = city.connections(i)
            n["deals"] = [{k: v for k, v in d.items() if k != "neighbor"} for d in deals if d["neighbor"] == i]
        return {"neighbors": out}
    return _guard(run)


@tool("read")
def deals() -> dict:
    """Every neighbor deal in force (type, neighbor, monthly amount, rate, quantity, minimum, cancellation penalty, months
    running), proposals waiting for an answer (they arrive as petitions: answer_petition), the business-deal offers
    (casino, prison, gigamall, toxic waste plant; accepted ones become placeable rewards) and penalties due at the next
    month end. Types: buy_power, sell_power, buy_water, sell_water, export_garbage (we pay), import_garbage (they pay).
    """
    def run():
        names = [n["name"] for n in city.neighbors()]

        def named(ds):
            return [{**d, "neighbor": names[d["neighbor"]] if d["neighbor"] < 4 else d["neighbor"]} for d in ds]
        return {"active": named(city.deals("active")), "proposed": named(city.deals("pending")),
                "business_deals": city.business_deals(), "penalties_due": city.deal_penalties_pending()}
    return _guard(run)


TERMS_PETITION = {"buy_power": 234, "sell_power": 233, "buy_water": 236, "sell_water": 235,
                  "export_garbage": 238, "import_garbage": 237}


@tool("destructive")
def cancel_deal(deal_type: str) -> dict:
    """Cancel the neighbor deal of this type (see deals), as "Cancel Deal" in its terms window does. The game charges the
    deal's cancellation penalty at month end unless it has run 60 months.

    Args:
        deal_type: buy_power | sell_power | buy_water | sell_water | export_garbage | import_garbage.
    """
    def run():
        if deal_type not in TERMS_PETITION:
            raise GameError(f"deal_type must be one of {list(TERMS_PETITION)}")
        before = [d for d in city.deals("active") if d["type"] == deal_type]
        if not before:
            raise GameError(f"no active {deal_type} deal")
        r = city.answer_petition(TERMS_PETITION[deal_type], True)
        after = [d for d in city.deals("active") if d["type"] == deal_type]
        return {"cancelled": not after, "deal": before[0], "penalties_due": city.deal_penalties_pending(),
                "funds": r["funds"]}
    return _guard(run)


def _neighbor_index(neighbor: str) -> int:
    names = [n["name"].lower() for n in city.neighbors()]
    pos = [p for p, _ in life.NEIGHBOR_QUADRANTS]
    key = neighbor.strip().lower()
    if key in names:
        return names.index(key)
    if neighbor.strip().upper() in pos:
        return pos.index(neighbor.strip().upper())
    raise GameError(f"unknown neighbor {neighbor!r}: one of {[n['name'] for n in city.neighbors()]} or {pos}")


@tool("act")
def discuss_deal(neighbor: str) -> dict:
    """Open the terms of the current deal with a neighbor (the Neighbors Map's Discuss Deal button). The game shows the
    exact terms (quantity, price, termination fee) with the options "Keep Deal", "Cancel Deal" and "Impact Analysis":
    answer with close_dialog(<option>), then close_dialog("close") until dialog_status is null.

    Args:
        neighbor: Neighbor name, or its quadrant NE | NW | SW | SE (see neighbors).
    """
    return _guard(lambda: {"dialog": life.discuss_deal(_neighbor_index(neighbor))})


@tool("read")
def advisors(full: bool = False, advisor: str | None = None) -> dict:
    """What each of the seven advisors currently says, as their panels show it (utilities, budget, city_planner,
    environment, health_education, public_safety, transportation), with each advisor's mood as the game computes it
    (1 = good news .. 5 = crisis).

    Args:
        full: Include the messages, not only the headings.
        advisor: Only this advisor.
    """
    def run():
        out, moods = {}, {}
        for name, items in city.advice().items():
            if advisor and name != advisor:
                continue
            moods[name] = city.advisor_mood(items)
            out[name] = [({"heading": _subst(i["heading"]), "message": _subst(i["message"])} if full
                          else _subst(i["heading"])) for i in items]
        return {"advisors": out, "moods": moods, "mood_scale": "1 good news .. 3 neutral .. 5 crisis"}
    return _guard(run)


@tool("act")
def answer_petition(petition_id: int, accept: bool) -> dict:
    """Accept or reject a pending petition (as the meeting window's buttons do).

    Args:
        petition_id: Id from petitions.
        accept: true = button1 (accept), false = button2 (reject).
    """
    return _guard(city.answer_petition, petition_id, accept)


# ================================================================ events
_events_seen: dict = {}            # (pid, city) -> last ticker sequence number reported


def _ticker_max() -> int:
    try:
        return max((e["seq"] for e in city.ticker_entries()), default=0)
    except GameError:
        return 0


def _events_since(seq: int, limit: int = 40) -> list[dict]:
    ev = [e for e in city.ticker_entries() if e["seq"] > seq and e["category"] != "status"]
    return [{"category": e["category"], "text": e["text"]} for e in ev[-limit:]]


@tool("observe")
def game_events(all_recent: bool = False) -> dict:
    """What the game announced since the previous call (news, alerts, petitions, advisor notes from the ticker), oldest
    first, plus any open game dialog.

    Args:
        all_recent: Return everything the ticker still holds instead of only what is new.
    """
    def run():
        key = (game.proc.pid, game.need_city())
        top = _ticker_max()
        last = 0 if all_recent else _events_seen.get(key, 0)
        if last > top:                       # the ticker restarted (city reloaded)
            last = 0
        out = {"date": game.city_basics(key[1])["date"], "events": _events_since(last, 200)}
        _events_seen[key] = top
        m = life.modal()
        if m:
            out["dialog"] = m
        return out
    return _guard(run)


# ================================================================ time
# ---- auto mode: what to do when the game opens a window during advance_time / run_realtime
AUTO = {"mode": "off"}
DECISION_WORDS = ("yes", "no", "accept", "reject", "keep", "cancel", "enact", "repeal", "ignore", "agree",
                  "destroy", "give raise", "decline", "tear down")


def _informational(m: dict | None) -> bool:
    """A window that only informs: the year-end Budget window, scenario tour notes, advisor notes, tips. Not:
    questions (yes/no, accept/reject, keep/cancel...), file/option dialogs, pickers, or a scenario's results."""
    if not m or m.get("kind") in ("prompt", "file", "picker", "new_city_options"):
        return False
    if m.get("title") == "Budget":
        return True
    if any(b.strip().lower().startswith(DECISION_WORDS) for b in m.get("buttons", [])):
        return False
    sc = city.scenario()
    if sc.get("ended"):
        return False                      # the scenario's results: the player decides what comes next
    return True


def _auto_close(log: list) -> bool:
    """In auto mode "info", close an informational window (logged) and return True."""
    m = life.modal()
    if AUTO["mode"] != "info" or not _informational(m):
        return False
    log.append({"title": m.get("title"), "text": (m.get("text") or "")[:400]})
    if m.get("title") == "Budget":
        life.close()                      # = OK: the budget stays as set
    else:
        life.press_ok()
    return not life.modal() or life.modal().get("window") != m.get("window")


@tool("set")
def set_auto_mode(mode: str = "info") -> dict:
    """Choose what advance_time and run_realtime do when the game opens a window. "off": stop at every window (default).
    "info": close windows that only inform (the year-end Budget window when Auto Budget is off, scenario notes, advisor
    notes, tips) and keep going, stopping only at real decisions (questions, scenario results). Windows closed this way
    are listed in the result's "auto_closed".

    Args:
        mode: off | info.
    """
    if mode not in ("off", "info"):
        return {"error": "mode must be off or info"}
    AUTO["mode"] = mode
    return {"auto_mode": mode}


@tool("act")
def advance_time(days: int = 0, months: int = 0, years: int = 0, record: str = "", max_seconds: float = 50.0) -> dict:
    """Run the simulation exactly this long, one game day at a time as fast as the engine can, then leave it paused.
    Months and years follow the calendar (1 March + 1 month = 1 April); days are added after them. Stops early when the
    game opens a window (see set_auto_mode, dialog_status) or after max_seconds of real time: the result then has
    "stopped_early" and "remaining_days" (advance_time(days=remaining_days) continues; the outcome is the same as one
    call). Returns the new date, the period's events, population, demand and funds.

    Args:
        days: Days to run.
        months: Calendar months to run.
        years: Calendar years to run.
        record: Also return a metrics snapshot (without traffic) at every boundary and at the end, as "series":
            day | week | month (1st of each month) | year (1 January); empty for none.
        max_seconds: Return after about this much real time even if not done, to stay within client tool timeouts
            (0 = no limit). A large city runs about 60 game days per second, a small one several hundred.
    """
    def run():
        c = game.need_city()
        target = game.i32(c + 0x138) + calendar_days(game.i32(c + 0x138), days, months, years)
        if target <= game.i32(c + 0x138):
            raise GameError("nothing to advance")
        if record not in ("", "day", "week", "month", "year"):
            raise GameError("record: day | week | month | year (or empty)")
        seq0 = _ticker_max()
        jdn0 = game.i32(c + 0x138)
        auto_closed, seconds, r, series = [], 0.0, {}, []
        t_start, timed_out = time.time(), False
        while True:
            now = game.i32(c + 0x138)
            mark = _next_boundary(now, record) if record else None
            stop = min(target, mark) if mark else target
            if max_seconds and max_seconds > 0:
                stop = min(stop, now + 30)       # check the clock every 30 game days (same outcome as one run)
            for _ in range(60):
                if life.modal() and not _auto_close(auto_closed):
                    break
                if stop - game.i32(c + 0x138) <= 0:
                    break
                r = game.advance_days(until=stop)
                seconds += r.get("seconds", 0)
                if "stopped_early" not in r:
                    break
            cur = game.i32(c + 0x138)
            done = cur < stop or cur >= target          # held by a game window, or finished
            if not done and max_seconds and max_seconds > 0 and time.time() - t_start >= max_seconds:
                timed_out = True
            if record and (cur == mark or done or timed_out):
                series.append(_metrics(traffic=False))
            if done or timed_out:
                break
        jdn1 = game.i32(c + 0x138)
        r = {**r, "days": jdn1 - jdn0, "from": jdn_to_date(jdn0).isoformat(), "to": jdn_to_date(jdn1).isoformat(),
             "seconds": round(seconds, 3)}
        m = life.modal()
        if m:
            r["stopped_early"] = "a game window is open"
            r["dialog"] = m
        elif timed_out:
            r["stopped_early"] = f"max_seconds ({max_seconds:g}) reached"
        else:
            r.pop("stopped_early", None)
        if jdn1 < target:
            r["remaining_days"] = target - jdn1
        if auto_closed:
            r["auto_closed"] = auto_closed
        r["events"] = _events_since(seq0)
        r["status"] = {k: v for k, v in city.stats().items() if k in ("population", "demand")}
        r["funds"] = game.city_basics(game.need_city())["funds"]
        if record:
            r["series"] = series
        return r
    return _guard(run)


def _next_boundary(jdn: int, unit: str) -> int:
    """The next day / week / 1st of a month / 1 January after jdn."""
    if unit == "day":
        return jdn + 1
    if unit == "week":
        return jdn + 7
    d = jdn_to_date(jdn)
    if unit == "month":
        return date_to_jdn(datetime.date(d.year + (d.month == 12), d.month % 12 + 1, 1))
    return date_to_jdn(datetime.date(d.year + 1, 1, 1))


@tool("act")
def run_realtime(speed: int = 2, seconds: float = 10.0) -> dict:
    """Let the game run in real time at a speed for up to `seconds`, then pause. Stops early as soon as the game opens a
    dialog (returned; answer with close_dialog). Not reproducible; prefer advance_time for experiments.

    Args:
        speed: 1 (turtle) | 2 (llama) | 3 (cheetah) | 4 (african swallow, the fastest).
        seconds: Real seconds to run (max 600; keep it below your client's tool timeout).
    """
    def run():
        if not _scenario_locks_time():
            game.set_speed(speed)
        c = game.need_city()
        start = game.i32(c + 0x138)
        depth0 = game.modal_depth()
        seq0 = _ticker_max()
        game.set_paused(False)
        t0 = time.time()
        deadline = t0 + max(0.0, min(seconds, 600))
        m, auto_closed = None, []
        while time.time() < deadline:
            time.sleep(min(0.25, max(0.0, deadline - time.time())))
            if game.modal_depth() > depth0:
                if _auto_close(auto_closed):
                    continue
                m = life.modal()
                break
        if not _scenario_locks_time():
            game.set_paused(True)
        end = game.i32(c + 0x138)
        out = {"days": end - start, "date": jdn_to_date(end).isoformat(), "seconds": round(time.time() - t0, 2),
               "events": _events_since(seq0)}
        if auto_closed:
            out["auto_closed"] = auto_closed
        if m:
            out["dialog"] = m                   # a game window opened and is holding the simulation
            out["stopped_early"] = "a game dialog opened"
        return out
    return _guard(run)


def _scenario_locks_time() -> bool:
    """A running scenario that fixes its speed and cannot be paused (SCENARIO byte +0x9A9 == 0)."""
    sc = game.u32(game.need_city() + 0x100)
    return bool(sc) and bool(game.proc.read(sc + 9, 1)[0]) and not game.proc.read(sc + 0x9A9, 1)[0]


@tool("set")
def set_paused(paused: bool) -> dict:
    """Pause or unpause the simulation for real-time play (advance_time does not need it). Scenarios that cannot be paused
    refuse.

    Args:
        paused: true = pause.
    """
    def run():
        if paused and _scenario_locks_time():
            raise GameError("this scenario cannot be paused (the game's rule); advance_time still steps it")
        game.set_paused(paused)
        return {"paused": paused}
    return _guard(run)


@tool("set")
def set_speed(speed: int) -> dict:
    """Simulation speed for real-time play. Some scenarios fix the speed.

    Args:
        speed: 1 (turtle) | 2 (llama) | 3 (cheetah) | 4 (african swallow, the fastest).
    """
    def run():
        if _scenario_locks_time():
            raise GameError("this scenario sets the speed and it cannot be changed (the game's rule)")
        if speed not in (1, 2, 3, 4):
            raise GameError("speed must be 1 (turtle), 2 (llama), 3 (cheetah) or 4 (african swallow)")
        game.set_speed(speed)
        return {"speed": speed}
    return _guard(run)


# ================================================================ disasters
@tool("set")
def set_disasters(enabled: bool) -> dict:
    """Enable or disable random disasters (the New City option).

    Args:
        enabled: true = random disasters can happen.
    """
    def run():
        c = game.need_city()
        game.call(game.vfn(c, 0x9C // 4), [1 if enabled else 0], this=c)
        return {"disasters_enabled": bool(game.proc.read(c + 0x1F2, 1)[0])}
    return _guard(run)


@tool("destructive")
def trigger_disaster(kind: str) -> dict:
    """Start a disaster now; the game picks the place. The game switches to disaster mode: the calendar stops and the
    game runs in real time until it is over (use disasters, run_realtime, dispatch, news).

    Args:
        kind: fire | tornado | earthquake | riot | ufo | toxic_cloud | whirlpool | locusts | space_debris.
    """
    def run():
        if kind not in catalog.DISASTERS:
            raise GameError(f"kind must be one of {list(catalog.DISASTERS)}")
        r = game.bridge.command(catalog.DISASTERS[kind])
        return {"started": bool(r.ret[0]), "kind": kind}
    return _guard(run)


@tool("read")
def preferences() -> dict:
    """The game's Preferences (read from memory, no window): traffic and pedestrians drawn at how many zoom levels,
    other animations, auto go to disasters, tips at startup, music / sound effects / ambient sound on-off and volumes
    (percent), 3D sound, which songs are in the music rotation, and the New City defaults. They change only what is drawn and heard (measured: no effect on
    simulation speed). Change them with set_preferences.
    """
    return _guard(life.preferences)


@tool("set")
def set_preferences(traffic_visible: int | None = None, sims_visible: int | None = None,
                    other_animations: bool | None = None, auto_go_to_disasters: bool | None = None,
                    show_tips_at_startup: bool | None = None, music: bool | None = None,
                    music_volume: int | None = None, sound_effects: bool | None = None,
                    sound_effects_volume: int | None = None, ambient_sound: bool | None = None,
                    ambient_volume: int | None = None, sound_3d: bool | None = None,
                    music_tracks: dict[str, bool] | None = None) -> dict:
    """Change the game's Preferences through its own Preferences window (the options are set as a player sets them,
    then OK; the game applies and saves them). Only the given options change; the result is read back from memory.
    Screen resolution is not offered (game_launch fixes the window at 1024x768).

    Args:
        traffic_visible: Draw traffic at the closest N zoom levels: 0 (off) .. 3.
        sims_visible: Draw pedestrians at the closest N zoom levels: 0 (off) .. 2.
        other_animations: Other animations on / off.
        auto_go_to_disasters: Move the camera to each new disaster.
        show_tips_at_startup: Show the tip of the day when the game starts.
        music: Music on / off.
        music_volume: Music volume, percent 0-100.
        sound_effects: Sound effects on / off.
        sound_effects_volume: Sound effects volume, percent 0-100.
        ambient_sound: Ambient sound on / off.
        ambient_volume: Ambient sound volume, percent 0-100.
        sound_3d: Enable 3D sounds.
        music_tracks: Songs to put in or take out of the music rotation, by name: {"Night Life": false, ...}
            (preferences lists the 17 songs).
    """
    return _guard(life.set_preferences, traffic_visible=traffic_visible, sims_visible=sims_visible,
                  other_animations=other_animations, auto_go_to_disasters=auto_go_to_disasters,
                  show_tips_at_startup=show_tips_at_startup, music=music, music_volume=music_volume,
                  sound_effects=sound_effects, sound_effects_volume=sound_effects_volume,
                  ambient_sound=ambient_sound, ambient_volume=ambient_volume, sound_3d=sound_3d,
                  music_tracks=music_tracks)


@tool("read")
def query(x: int, y: int) -> dict:
    """Use the game's own Query tool on a tile and return everything its Query window shows: the title (building or
    terrain name) and every line with its label and value (e.g. for a fire station: elevation, powered, watered,
    number of fires and calls per month, performance rating, funding cost; for homes, shops, factories, plants,
    services, stations, ports and land the game's own lines). The window is closed again; nothing changes.

    Args:
        x: Tile x.
        y: Tile y.
    """
    return _guard(life.query, x, y)


@tool("read")
def city_options() -> dict:
    """The City Options of the current city: name, mayor, description, landscape style, tree style, building style
    (the game's look: e.g. European or Asian buildings), disasters and auto budget, how many user-made (Building
    Architect) buildings are available, and the possible style choices.
    """
    return _guard(life.city_options)


@tool("set")
def set_city_options(landscape: str | None = None, trees: str | None = None, buildings: str | None = None,
                     description: str | None = None) -> dict:
    """Change the city's look and description as the City Options window does (the game re-skins the city at once;
    the styles are cosmetic and saved with the city). Names, disasters and auto budget: rename_city, set_disasters,
    set_auto_budget.

    Args:
        landscape: temperate | winter | desert | dry | tropical.
        trees: mixed | desert | deciduous | palms | conifers.
        buildings: north_american | european | asian.
        description: The city's description text.
    """
    def run():
        if landscape is not None or trees is not None or buildings is not None:
            life.set_city_style(landscape, trees, buildings)
        if description is not None:
            life.set_description(description)
        return life.city_options()
    return _guard(run)


@tool("read")
def building_replacements(list_replaceable: bool = False, size: int | None = None,
                          category: str | None = None) -> dict:
    """The Building Replacement Manager's data: the user-made buildings (made with the Building Architect: name,
    architect, size), which default buildings are currently shown as a user-made one, and (list_replaceable) the
    default buildings that can be replaced (id, name, size, category, current replacement). Replacements are
    cosmetic: same building, different look and name.

    Args:
        list_replaceable: Also list the replaceable default buildings (338 in all; filter with size / category).
        size: Only replaceable buildings of this footprint (1..4 tiles a side).
        category: Only this category: residential | commercial | industrial | rewards | other.
    """
    def run():
        out = {"user_made": [{k: v for k, v in u.items() if not k.startswith("_")} for u in life.user_buildings()],
               "replacements": life.replacements()}
        if list_replaceable or size is not None or category is not None:
            rows = [{k: v for k, v in r.items() if not k.startswith("_")} for r in life.replaceable_buildings()
                    if (size is None or r["size"] == size) and (category is None or r["category"] == category)]
            out["replaceable"] = rows
        return out
    return _guard(run)


@tool("set")
def replace_building(building: str, user_building: str = "") -> dict:
    """Show a default building as one of the user-made buildings, as the Building Replacement Manager does (Replace,
    then OK): every existing building of that kind changes its look and name at once; the choice is saved with the
    city. An empty user_building reverts it to the game's own building.

    Args:
        building: The default building's name or id (building_replacements(list_replaceable=True)).
        user_building: The user-made building's name (same size); empty to revert.
    """
    return _guard(life.replace_building, building, user_building or None)


@tool("destructive")
def reset_building_replacements(import_from_city: str = "", merge: bool = True) -> dict:
    """Clear every building replacement (the manager's Clear Set), or import the replacements saved with another
    city (its Import Set from Selected City). Returns the replacements now in force.

    Args:
        import_from_city: A saved city's name (list_cities); empty to clear all replacements instead.
        merge: With import_from_city: add to the current replacements (true) or replace them (false).
    """
    def run():
        if import_from_city:
            return {"replacements": life.import_replacements(import_from_city, merge)}
        return {"replacements": life.clear_replacements()}
    return _guard(run)


@tool("act")
def take_snapshot(size: str = "medium") -> dict:
    """Take a snapshot with the game's own Take Snapshot (a JPG of the middle of the city view, saved by the game in
    its Albums folder, as in the game's Photo Album). Position the view first with center_view / set_view. Returns
    the file's path. Works even while the game window is not presenting on screen.

    Args:
        size: small | medium | large (640x480 is medium on a 1024x768 window: small 480x360, large 800x600).
    """
    return _guard(life.take_snapshot, size)


@tool("read")
def snapshots(album: str | None = None) -> dict:
    """The game's Photo Album: every snapshot with its album (one per city), file name, path, size, time, and what the
    album shows for it - city, mayor, game date, population, funds and the description (caption). Read from the
    Albums folder; the game need not be running.

    Args:
        album: Only this album (its folder name, or the city name); omit for all.
    """
    return _guard(lambda: {"snapshots": album_mod.snapshots(album)}, _attach=False)


@tool("read", structured_output=False)
def snapshot_image(file: str, album: str | None = None, scale: float = 1.0):
    """One snapshot from the Photo Album as a picture, with its details (city, mayor, date, population, funds,
    caption).

    Args:
        file: The snapshot's file name as snapshots lists it (with or without .jpg).
        album: Its album, when the same file name is in several albums.
        scale: Shrink factor for the returned picture (1 = as saved).
    """
    def run():
        from PIL import Image as PImage
        p = album_mod.find(file, album)
        info = next(s for s in album_mod.snapshots() if s["path"] == p)
        img = PImage.open(p).convert("RGB")
        if scale != 1:
            img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))))
        return [json.dumps({**info, "pixels": list(img.size)}), _png(img)]
    return _guard(run, _attach=False)


@tool("set")
def set_snapshot_caption(file: str, caption: str, album: str | None = None) -> dict:
    """Set a snapshot's description, as typing it in the Photo Album's text box does (an empty caption removes it).
    Close the game's Photo Album window first if it is open: it saves its own text box when it closes.

    Args:
        file: The snapshot's file name as snapshots lists it.
        caption: The description text.
        album: Its album, when the same file name is in several albums.
    """
    def run():
        if game.proc and game.proc.alive() and life._find_window(title="View Snapshots"):
            raise GameError("the game's Photo Album window is open: close it first (it saves its own text box)")
        return album_mod.set_caption(file, caption, album)
    return _guard(run, _attach=False)


@tool("destructive")
def delete_snapshot(file: str, album: str | None = None) -> dict:
    """Delete a snapshot as the Photo Album's Delete button does (the picture, its details and its description),
    but into the Windows Recycle Bin, so it can be restored (the game's own Delete removes it for good).

    Args:
        file: The snapshot's file name as snapshots lists it.
        album: Its album, when the same file name is in several albums.
    """
    def run():
        if game.proc and game.proc.alive() and life._find_window(title="View Snapshots"):
            raise GameError("the game's Photo Album window is open: close it first")
        return album_mod.delete(file, album)
    return _guard(run, _attach=False)


@tool("read")
def cheats() -> dict:
    """The cheat codes the game accepts in its cheat box (Ctrl+Alt+Shift+C), as registered in its cheat manager, and
    the ones used since the game started. Cheats change the game's rules (free buildings, money, unlocked buildings,
    terrain), so experiments that must stay honest should check this list. Two are blocked here: "Crash" (crashes the
    game) and "Internet chat" (an online service that no longer exists).
    """
    return _guard(life.cheats)


@tool("act")
def cheat(code: str) -> dict:
    """Enter a cheat code as the game's cheat box (Ctrl+Alt+Shift+C) does: the game matches it (case-insensitive;
    some take parameters, e.g. "force Moe to say 12") and sends it to the parts of the game that act on it. Returns
    the change in funds; if the cheat opens a game window (e.g. "call cousin Vinnie"), answer it with close_dialog.

    Args:
        code: The text to enter, e.g. "I am weak", "garbage in, garbage out", "Terrain one up" (cheats lists all).
    """
    return _guard(life.cheat, code)


@tool("read")
def disasters() -> dict:
    """Disasters in progress, from the game's disaster manager: whether the game is in disaster mode (calendar
    stopped, real time only), each active disaster instance (one per burning building, riot, swarm...) with its kind,
    tile, buildings destroyed and damage in $, the ones still in their warning phase, whether an early warning is on
    and the damage the game will partly refund when the disaster ends.
    """
    return _guard(city.disasters)


@tool("act")
def dispatch(kind: str, x: int, y: int) -> dict:
    """Send emergency units to tile (x, y) during a disaster, or issue an early warning.

    Args:
        kind: police | fire | military | early_warning.
        x: Tile x.
        y: Tile y.
    """
    def run():
        if kind not in catalog.DISPATCH:
            raise GameError(f"kind must be one of {list(catalog.DISPATCH)}")
        return game.apply_tool(catalog.DISPATCH[kind], [(x, y)], click_each=True)
    return _guard(run)


# ================================================================ dialogs and UI
@tool("read")
def dialog_status() -> dict:
    """The game's open modal window, or null: kind, rect, title, text, fields and button labels. While one is open the
    simulation is held; answer it with close_dialog.
    """
    def run():
        out = {"dialog": life.modal()}
        if game.pending:
            out["waiting_action"] = game.pending["what"]
        return out
    return _guard(run)


@tool("act")
def close_dialog(button: str = "ok") -> dict:
    """Answer the open game dialog by pressing one of its buttons. If a build was waiting on this dialog it completes and
    its cost is returned.

    Args:
        button: A button label as dialog_status lists it (e.g. "Yes"), or a standard result: ok | cancel | yes | no |
            close (closes any game window, e.g. the Neighbors Map, via its X button).
    """
    def run():
        m = life.modal()
        if not m:
            raise GameError("no game dialog is open")
        labels = [b.strip().lower() for b in m.get("buttons", [])]
        if button.strip().lower() in labels:
            life.press(button)
        elif button.strip().lower() == "close":
            life.close()
        else:
            life.end_modal(button.lower())
        out = {}
        if game.pending:
            out["action"] = game.pending["what"]
            out["result"] = _asking(game.finish_pending())
        out["dialog"] = life.modal()
        return out
    return _guard(run)


@tool("destructive")
def ui_click(x: int, y: int, button: str = "left", wait_ms: int = 400) -> dict:
    """Low-level: click the game window at client pixel (x, y) (full-size screenshot coordinates). For screens without a
    dedicated tool; it can press anything, so prefer the dedicated tools.

    Args:
        x: Pixel x, 0..1023.
        y: Pixel y, 0..767.
        button: left | right.
        wait_ms: Milliseconds to wait afterwards for the game to react.
    """
    return _guard(lambda: (game.click(x, y, button, wait_ms), {"ok": True})[1])


@tool("destructive")
def ui_drag(x1: int, y1: int, x2: int, y2: int, wait_ms: int = 400) -> dict:
    """Low-level: press the left mouse button at pixel (x1, y1), move to (x2, y2) and release.

    Args:
        x1: Start pixel x.
        y1: Start pixel y.
        x2: End pixel x.
        y2: End pixel y.
        wait_ms: Milliseconds to wait afterwards for the game to react.
    """
    return _guard(lambda: (game.drag(x1, y1, x2, y2, wait_ms), {"ok": True})[1])


@tool("destructive")
def ui_key(key: str, shift: bool = False, ctrl: bool = False, alt: bool = False) -> dict:
    """Low-level: press a key in the game window.

    Args:
        key: A character, or esc | enter | space | tab | backspace | delete | home | end | pageup | pagedown | left | up |
            right | down | f1..f12 | plus | minus.
        shift: Hold Shift.
        ctrl: Hold Ctrl.
        alt: Hold Alt.
    """
    return _guard(lambda: (game.key(key, shift, ctrl, alt), {"ok": True})[1])


@tool("act")
def ui_type(text: str) -> dict:
    """Low-level: type text into the focused game text field.

    Args:
        text: The text to type.
    """
    return _guard(lambda: (game.type_text(text), {"ok": True})[1])


def main():
    """Command line: sc3k-mcp (or python -m sc3k_mcp) [--transport stdio|streamable-http|sse] [--host] [--port]."""
    import argparse
    ap = argparse.ArgumentParser(prog="sc3k-mcp", description="MCP server that plays SimCity 3000 Unlimited.")
    ap.add_argument("--transport", choices=["stdio", "streamable-http", "sse"], default="stdio",
                    help="stdio (default; the client starts this process) or an HTTP transport for clients that "
                         "connect to a URL (streamable-http serves http://HOST:PORT/mcp)")
    ap.add_argument("--host", default="127.0.0.1", help="HTTP bind address (default 127.0.0.1, this machine only)")
    ap.add_argument("--port", type=int, default=8765, help="HTTP port (default 8765)")
    a = ap.parse_args()
    if a.transport != "stdio":
        mcp.settings.host, mcp.settings.port = a.host, a.port
    mcp.run(transport=a.transport)


if __name__ == "__main__":
    main()
