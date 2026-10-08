"""LIVE t6: drive the new/changed tools through the real MCP stdio protocol on the e2e test city and report
each call's outcome (no assertion stops the run; errors are counted).

    python live/t6_stdio.py
"""
import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STEPS = [
    ("guide", {"topic": "time"}),
    ("load_city", {"name": "mcp_e2e"}),
    ("preferences", {}),
    ("disasters", {}),
    ("city_options", {}),
    ("set_view", {"rotation": 1, "data_view": "crime"}),
    ("set_view", {"rotation": 0, "data_view": "normal"}),
    ("query", {"x": 62, "y": 26}),
    ("take_snapshot", {"size": "small"}),
    ("building_replacements", {"size": 1, "category": "residential"}),
    ("replace_building", {"building": "Squat St.", "user_building": "The Joneses"}),
    ("replace_building", {"building": "Squat St.", "user_building": ""}),
    ("game_status", {}),
    ("city_status", {}),
    ("neighbors", {}),
    ("deals", {}),
    ("advisors", {}),
    ("advisors", {"full": True, "advisor": "utilities"}),
    ("petitions", {}),
    ("game_events", {"all_recent": True}),
    ("find_empty_area", {"width": 3, "height": 3, "near_x": 70, "near_y": 40}),
    ("build", {"tool": "road", "x": 80, "y": 61, "x2": 80, "y2": 127}),       # asks about a bridge
    ("dialog_status", {}),
    ("close_dialog", {"button": "No"}),
    ("advance_time", {"months": 1, "record": "week"}),
    ("game_events", {}),
    ("scenario_status", {}),
    ("list_cities", {"kind": "scenario"}),
    ("building_options", {"picker": "power"}),
    ("discuss_deal", {"neighbor": "NE"}),
    ("set_paused", {"paused": True}),
    ("run_realtime", {"speed": 3, "seconds": 2}),
    ("population_details", {}),
    ("zone_summary", {}),
    ("building_info", {"x": 62, "y": 26}),
    ("tile_info", {"x": 70, "y": 31}),
    ("map_text", {"layer": "power", "x0": 60, "y0": 20, "x1": 100, "y1": 40}),
    ("map_text", {"layer": "traffic", "x0": 60, "y0": 20, "x1": 100, "y1": 40}),
    ("buildings", {"details": True, "name_filter": "Pump"}),
    ("map_data", {"layer": "traffic", "x0": 60, "y0": 20, "x1": 90, "y1": 40}),
    ("layer_stats", {"layer": "police", "where": "residential", "thresholds": [50, 100]}),
    ("rewards", {}),
    ("transit", {}),
    ("metrics", {}),
    ("advance_time", {"days": 40, "max_seconds": 0.01}),
    ("layer_stats", {"layer": "density", "where": "residential"}),
    ("ordinances", {}),
    ("get_budget", {}),
    ("tile_info", {"x": 9999, "y": 0}),
    ("set_auto_mode", {"mode": "info"}),
    ("advance_time", {"years": 1}),
    ("set_auto_mode", {"mode": "off"}),
    ("save_city", {"name": "mcp_e2e", "overwrite": True}),
]


async def main():
    env = dict(os.environ, PYTHONPATH=ROOT, PYTHONIOENCODING="utf-8")
    params = StdioServerParameters(command=sys.executable, args=["-m", "sc3k_mcp"], env=env)
    errors = 0
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            init = await s.initialize()
            listed = (await s.list_tools()).tools
            print(f"server {init.serverInfo.name}: {len(listed)} tools, "
                  f"{sum(t.annotations is not None for t in listed)} annotated, "
                  f"{sum(all(p.get('description') for p in t.inputSchema.get('properties', {}).values()) for t in listed)}"
                  " with every parameter described")
            for tool, args in STEPS:
                res = await s.call_tool(tool, args)
                text = " ".join(c.text for c in res.content if c.type == "text")
                bad = res.isError or '"error"' in text[:200]
                errors += bad
                flag = " isError" if res.isError else ""
                print(f"{'ERR' if bad else 'ok '}{flag} {tool} {json.dumps(args)}: {text[:300]}")
    print(f"{errors} errors")


if __name__ == "__main__":
    asyncio.run(main())
