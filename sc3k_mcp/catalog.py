"""Tool and building catalog: names -> game command ids (Sys\\SYS.PAK MenuItem.INI) and occupant ids.

kind: "line" (drag from start to end tile), "area" (drag a rectangle), "click" (one tile per action;
buildings are placed by their top-left tile).
"""

from __future__ import annotations

import json
import os

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

TOOLS: dict[str, tuple[int, str, str]] = {
    # name: (command id, kind, description)
    "road": (0xC2B5DE77, "line", "Road"),
    "highway": (0x42B5DE86, "line", "Highway (needs the technology)"),
    "onramp": (0x02B5DEBB, "click", "Highway on-ramp (next to a highway)"),
    "rail": (0x42B5DE98, "line", "Rail"),
    "subway": (0xC2B5DEA6, "line", "Subway rail (underground)"),
    "power_line": (0x42C2F8BF, "line", "Power lines"),
    "pipe": (0x22C2F8C5, "line", "Water pipes (underground)"),
    "res_light": (0x42E88586, "area", "Residential zone, light density"),
    "res_medium": (0x02E88915, "area", "Residential zone, medium density"),
    "res_dense": (0xA2E8893B, "area", "Residential zone, dense"),
    "com_light": (0x02E88949, "area", "Commercial zone, light density"),
    "com_medium": (0xA2E8895A, "area", "Commercial zone, medium density"),
    "com_dense": (0x02E88968, "area", "Commercial zone, dense"),
    "ind_light": (0xC2E8898F, "area", "Industrial zone, light density"),
    "ind_medium": (0xA2E8899D, "area", "Industrial zone, medium density"),
    "ind_dense": (0x02E889AA, "area", "Industrial zone, dense"),
    "dezone": (0x82E88C9C, "area", "Remove zoning"),
    "landfill": (0xC2E889B6, "area", "Landfill zone"),
    "seaport": (0x02E889C4, "area", "Seaport zone"),
    "airport": (0xE2E889D4, "area", "Airport zone"),
    "bulldoze": (0xE3166801, "area", "Demolish/bulldoze"),
    "trees": (0x4253EC3F, "click", "Plant trees"),
    "water": (0x02E763C1, "click", "Place water"),
    "raise_terrain": (0x825AD7F6, "click", "Raise terrain"),
    "lower_terrain": (0xC25AD94F, "click", "Lower terrain"),
    "level_terrain": (0x825AD954, "area", "Level terrain"),
    "bus_stop": (0x02FF04FE, "click", "Bus stop"),
    "train_station": (0x22FF058F, "click", "Train station"),
    "subway_station": (0x62FF059B, "click", "Subway station"),
    "rail_to_subway": (0x22FF0521, "click", "Rail-to-subway connection"),
    "police_station": (0x42FF052F, "click", "Police station"),
    "jail": (0x22FF053F, "click", "Jail"),
    "fire_station": (0x22FF054C, "click", "Fire station"),
    "hospital": (0xE2FF0555, "click", "Hospital"),
    "school": (0xC2FF0563, "click", "School"),
    "college": (0xC2FF0571, "click", "College"),
    "library": (0xC2FF057A, "click", "Library"),
    "museum": (0x62FF0585, "click", "Museum"),
    "small_park": (0x02FF05AA, "click", "Small park"),
    "big_park": (0x82FF05B7, "click", "Big park"),
    "marina": (0x42FF05C2, "click", "Marina (on the shore)"),
    "zoo": (0x22FF05CA, "click", "Zoo"),
    "baseball_field": (0x62FF05D1, "click", "Baseball field"),
    "playground": (0xC2FF05E0, "click", "Playground"),
    "pond": (0x22FF05EA, "click", "Pond"),
    "fountain": (0x22FF05F3, "click", "Fountain"),
}

# building pickers (COMM 0xE2ED3560 with this parameter) -> agent categories that belong to them
PICKERS = {
    "power": (0x62E925A2, range(12101, 12200)),
    "water": (0xE2E92527, range(12800, 12850)),
    "garbage": (0xC2F291A9, range(12850, 12860)),
    "landmark": (0x22E92581, None),
    "reward": (0x62E92553, None),
}

COMMANDS = {
    "budget_window": 0x025DDC4A, "save": 0x410438DD, "new_city": 0xE3270FE9, "quit": 0xA10438E9,
    "load": 0x610438A4, "preferences": 0xC3001401, "city_properties": 0x855A2DC4, "scenario_goals": 0x844587AE,
}
LOAD_KINDS = {"saved_city": 0x83172AD7, "starter_town": 0x63172B74, "real_city_terrain": 0x23172AF2,
              "scenario": 0xA42C7725}
SAVE_AS = 0xC3172AEA

DISASTERS = {"fire": 0xC26CE54D, "tornado": 0x626CE901, "earthquake": 0x22FE8786, "riot": 0x02FE87A7,
             "ufo": 0x42FE87AE, "toxic_cloud": 0x447F1E40, "whirlpool": 0x447F1E41, "locusts": 0x447F1E42,
             "space_debris": 0x447F1E43}
DISPATCH = {"police": 0x029A52DD, "fire": 0x229A528C, "military": 0xA5354652, "early_warning": 0x02B5AECF}


# first year a picker building can be placed (Sys\SYS.PAK Advisor-Utilities.ini / Advisor-Environment.ini)
AVAILABLE_FROM = {12111: 0, 12112: 0, 12113: 1955, 12115: 1965, 12118: 1980, 12117: 1990, 12114: 2020,
                  12116: 2050, 12810: 0, 12840: 0, 12820: 1935, 12830: 1960, 12851: 1970, 12852: 1920,
                  12853: 2000}

# construction costs by agent category (SC3BudgetLayer.ini [BuildingPlacementCosts] / [SpecialCosts])
COSTS = {"zone_light": 10, "zone_medium": 20, "zone_dense": 50, "landfill": 50, "airport": 500, "seaport": 250,
         "dezone": 2, "demolish": 5, "level_terrain": 25, "raise_terrain": 25, "lower_terrain": 25,
         "decorative_water": 150, "tree": 3, "road": 10, "highway": 150, "highway_ramp": 75, "rail": 10,
         "subway": 150, "power_line": 5, "pipe": 5, "road_bridge": 100, "rail_bridge": 500,
         "highway_bridge": 1000, "tunnel": 1000, "bus_station": 150, "rail_station": 250, "subway_station": 500,
         "coal_plant": 5000, "oil_plant": 8500, "gas_plant": 4500, "microwave_plant": 30000,
         "nuclear_plant": 20000, "fusion_plant": 50000, "solar_plant": 15000, "wind_plant": 250,
         "water_pump": 300, "water_treatment": 15000, "desalination": 1500, "water_tower": 150,
         "recycling_center": 5000, "incinerator": 7500, "waste_to_energy": 25000, "police_station": 500,
         "fire_station": 500, "jail": 2500, "hospital": 500, "school": 500, "college": 3000, "library": 1000,
         "museum": 1500}


def availability_year(category: int | None) -> int:
    return AVAILABLE_FROM.get(category or 0, 0)


def _occupants():
    with open(os.path.join(DATA, "occupants.json"), encoding="utf-8") as f:
        raw = json.load(f)
    return {int(k): v for k, v in raw.items()}


OCCUPANTS = _occupants()


def buildings() -> dict[int, dict]:
    """Placeable buildings (owner 0x207EDC0E, type 0x57E) with their occupant id."""
    return {k: v for k, v in OCCUPANTS.items() if v["owner"].lower() == "0x207edc0e"
            and v["type"].lower() == "0x0000057e"}


def find_building(name: str) -> tuple[int, dict]:
    """Occupant id by exact name, numeric id, or a unique substring."""
    b = buildings()
    s = name.strip()
    try:
        oid = int(s, 0)
        if oid in b:
            return oid, b[oid]
    except ValueError:
        pass
    exact = [(k, v) for k, v in b.items() if v["name"].lower() == s.lower()]
    if exact:
        return exact[0]
    sub = [(k, v) for k, v in b.items() if s.lower() in v["name"].lower()]
    if len(sub) == 1:
        return sub[0]
    if not sub:
        raise KeyError(f"no building named {name!r}")
    raise KeyError(f"{name!r} is ambiguous: {[v['name'] for _, v in sub[:12]]}")


def picker_buildings(picker: str) -> list[tuple[int, dict]]:
    cats = PICKERS[picker][1]
    if cats is None:
        return []
    return sorted([(k, v) for k, v in buildings().items() if v.get("category") in cats], key=lambda kv: kv[0])
