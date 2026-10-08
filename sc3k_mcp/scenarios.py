"""Scenario files (Cities\\Scenarios\\*.SNR): read them, and write new ones.

An .SNR is an IXF file (sc3k_mcp/ixf.py): the scenario's city (every record of a saved .sc3) plus
- header   (0x26E732E0, 0x19A6CEA1, 0): {u32 text table id, i32, i32}
- picture  (0x62B9DA24, 0x19A6CEA1, 1): a 24-bit BMP shown in the scenario picker
- (0x2026960B, 0x19A6CEA1, 2): 5 bytes 05 00 00 00 4D
- "SNR" chunk (0x04845CBE, 0xC3DE4D66, 0), text lines: "SNR ", the base city's path, "<script type> <script
  group> <entry script instance>", "<text table id> 1", "<guide advisor id> 1", "<text table id>"
- scripts  (0x23DFAE5F, 0x23DFAE8C, instance): plain text "; Script Code", the instruction count, then per
  instruction "<flag> <opcode> <argument count> ; comment" and one "<is variable> <value>" line per argument
- texts    (0x2026960B, <text table id>, index): u32 character count + Latin-1 text, as in the game's text tables;
  the game reads texts embedded in the .SNR (verified: live/t16). The shipped scenarios keep most of theirs in
  Apps\\Res\\Text\\<language>\\<Scenario>.IXF instead.
Opcode names: Apps\\Sys\\SYS.PAK SC3ScenarioLayer.ini (OPS below).
"""

from __future__ import annotations

import os
import struct

from . import ixf
from .game import GameError

T_HEADER, G_HEADER = 0x26E732E0, 0x19A6CEA1
T_PICTURE, T_TEXT = 0x62B9DA24, 0x2026960B
T_SNR, G_SNR = 0x04845CBE, 0xC3DE4D66
T_SCRIPT, G_SCRIPT = 0x23DFAE5F, 0x23DFAE8C

OPS = ["Add", "Subtract", "AndCondition", "Assign", "GetCrimeValue", "GetLandValue", "GetPollutionValue",
       "GetPopulation", "ComputePercentage", "Decrement", "Divide", "EndAnd", "EndOr", "Equal", "GreaterThan", "If",
       "IfElse", "Increment", "Multiply", "OrCondition", "RepeatRegular", "ShowNewsticker", "StartFire", "StartRiot",
       "StartTornado", "SubRoutine", "CountUnpoweredBuildings", "CountUnwateredBuildings", "GetTrafficDensity",
       "GetFundsAvailable", "GetMonthsElapsed", "EndScenario", "NotEqual", "CountStructures", "LessThan", "AddGoal",
       "MakeDialogText", "MarkGoalStatus", "AllGoalsMet", "GoalStatusIs", "PopUpMsg", "AddRankInfo",
       "SetResultsDlgText", "BeginBlock", "EndBlock", "GenerateRandomNum", "StartEarthquake", "StartUFOAttack",
       "GetAura", "DisableNewNeighborDeals", "EnableNewNeighborDeals", "GetSurplusPower", "GetSurplusWater",
       "OfferRewardBuilding", "GetCurrentDate", "SetVariable", "CountStructuresNearLocation", "GetTotalDebt",
       "CountStructuresWithAppearanceNearLocation", "CountStructuresWithAppearanceInCity", "MoveCamera",
       "EnableDisableDisasters", "PlaySound", "SetScenarioSpeed", "StartToxicCloud", "StartWhirlpool",
       "StartSpaceJunk", "StartLocusts", "IsOrdinanceEnacted", "OfferBusinessDeal", "IsBusinessDealActive",
       "EnableDisableBusinessDeal", "GetRCItaxes", "IsNeighborConnection", "IsNeighborDealPresent"]
OP_IDS = {n: k for k, n in enumerate(OPS)}


def folder() -> str:
    from .bridge import GAME_DIR
    return os.path.join(GAME_DIR, "Cities", "Scenarios")


def s32(v: int) -> int:
    return v - (1 << 32) if v >= 1 << 31 else v


# ---------------------------------------------------------------- scripts
def _num(x: str):
    """A script number: an int, or a float where the Creator wrote one (e.g. "2.0")."""
    try:
        return int(x)
    except ValueError:
        f = float(x)
        return int(f) if f.is_integer() else f


def parse_script(text: str) -> list[dict]:
    """Script text -> [{"flag", "op", "name", "args": [[is_variable, value], ...]}]."""
    lines = [ln.split(";")[0].split() for ln in text.replace("\r", "").split("\n")]
    lines = [ln for ln in lines if ln]
    if not lines:
        return []
    count, k, out = int(lines[0][0]), 1, []
    for _ in range(count):
        if k >= len(lines):
            break
        flag, op, nargs = (int(_num(x)) for x in lines[k][:3])
        k += 1
        args = []
        for _ in range(nargs):
            v = lines[k] if k < len(lines) else ["0", "0"]
            args.append([int(_num(v[0])), _num(v[1]) if len(v) > 1 else 0])
            k += 1
        out.append({"flag": flag, "op": op, "name": OPS[op] if 0 <= op < len(OPS) else f"op{op}", "args": args})
    return out


def format_script(instructions: list[dict]) -> str:
    """[{"op" or "name", "args", ["flag"]}] -> the script text the game reads (the Scenario Creator's layout)."""
    out = ["; Script Code", f" {len(instructions)} "]
    for ins in instructions:
        op = ins["op"] if "op" in ins else OP_IDS[ins["name"]]
        args = ins.get("args", [])
        out.append(f" {int(ins.get('flag', 0)):<13} {op:<13} {len(args):<12} ;  ")
        for a in args:
            isvar, val = (a if isinstance(a, (list, tuple)) else (0, a))
            out.append(f"{'':15}{int(isvar):<13} {val if isinstance(val, float) else int(val)} ")
        out.append("")
    return "\r\n".join(out) + "\r\n"


# ---------------------------------------------------------------- texts
def text_record(s: str) -> bytes:
    """A text record as the game's text tables hold them: u32 character count + Latin-1 text."""
    b = s.encode("latin-1", "replace")
    return struct.pack("<I", len(b)) + b


def read_text_record(d: bytes) -> str:
    n = struct.unpack_from("<I", d)[0]
    return d[4:4 + n].decode("latin-1", "replace")      # (the old Creator's records can be shorter than n)


def listing(instructions: list[dict], table: int = 0, texts: dict | None = None) -> list[str]:
    """Readable lines for a script: Name(args), $n for variable n, a text reference (table, index) shown with the
    text's first words."""
    out, depth = [], 0
    for ins in instructions:
        name = ins["name"]
        if name in ("EndBlock", "EndAnd", "EndOr"):
            depth = max(0, depth - 1)
        parts, args, k = [], ins["args"], 0
        while k < len(args):
            isvar, v = args[k]
            if not isvar and table and v == s32(table) and k + 1 < len(args) and not args[k + 1][0]:
                idx = args[k + 1][1]
                t = (texts or {}).get(idx, "")
                parts.append(f"text#{idx}" + (f" '{t[:48]}'" if t else ""))
                k += 2
                continue
            parts.append(f"${v}" if isvar else (f"{v & 0xFFFFFFFF:#010x}" if abs(v) > 99999 else str(v)))
            k += 1
        out.append("  " * depth + f"{name}({', '.join(parts)})")
        if name in ("BeginBlock", "AndCondition", "OrCondition"):
            depth += 1
    return out


# ---------------------------------------------------------------- writing
ADVISORS = {"utilities": 0x022E288E, "budget": 0x628D0C45, "planner": 0xC28D0B6E, "environment": 0x828D04EB,
            "health_education": 0xC28D0F40, "safety": 0x828D0A2F, "transportation": 0x028D0FC5}


def table_id(name: str) -> int:
    """A text-table id for a new scenario, from its name (stable; with the high bits of the game's own ids)."""
    import zlib
    return (zlib.crc32(("simcp scenario " + name).encode()) & 0x0FFFFFF0) | 0x50000001


def picture(name: str, image=None):
    """The 163 x 152 picture the scenario picker shows: the given PIL image fitted, or a plain card with the name."""
    from PIL import Image, ImageDraw
    W, H = 163, 152
    if image is not None:
        im = image.convert("RGB")
        s = max(W / im.width, H / im.height)
        im = im.resize((max(W, int(im.width * s)), max(H, int(im.height * s))))
        x, y = (im.width - W) // 2, (im.height - H) // 2
        return im.crop((x, y, x + W, y + H))
    im = Image.new("RGB", (W, H), (36, 64, 104))
    d = ImageDraw.Draw(im)
    for k in range(0, H, 8):
        d.line([(0, k), (W, k)], fill=(44, 74, 118))
    words, lines, cur = name.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > 18 and cur:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    lines.append(cur)
    y = H // 2 - 8 * len(lines)
    for ln in lines[:6]:
        d.text(((W - 6 * len(ln)) // 2, y), ln, fill=(240, 236, 220))
        y += 16
    return im


def bmp_bytes(im) -> bytes:
    import io
    b = io.BytesIO()
    im.convert("RGB").save(b, "BMP")
    return b.getvalue()


# goal measures: (the script command that puts the value into a variable, its extra arguments)
MEASURES = {
    "population": ("GetPopulation", []), "funds": ("GetFundsAvailable", []), "crime": ("GetCrimeValue", []),
    "land_value": ("GetLandValue", []), "traffic": ("GetTrafficDensity", []), "approval": ("GetAura", []),
    "air_pollution": ("GetPollutionValue", [0]), "water_pollution": ("GetPollutionValue", [1]),
    "garbage_pollution": ("GetPollutionValue", [2]), "unpowered_buildings": ("CountUnpoweredBuildings", []),
    "unwatered_buildings": ("CountUnwateredBuildings", []), "debt": ("GetTotalDebt", []),
    "power_surplus": ("GetSurplusPower", []), "water_surplus": ("GetSurplusWater", []),
}
MONTHLY = 2                     # RepeatRegular period code for once a month
V_MONTHS = 200                  # script variable for the months elapsed (goal k uses variable k)
T_BRIEFING, T_GOAL0, T_RANK0, T_RESULT0 = 101, 141, 160, 170


def _ins(name: str, *args) -> dict:
    return {"name": name, "args": [list(a) if isinstance(a, tuple) else [0, a] for a in args]}


def _var(n: int) -> tuple:
    return (1, n)


def compile_goals(table: int, goals: list[dict], months: int, briefing: bool) -> tuple[dict, dict]:
    """Scripts for a goal-based scenario: the entry script (149) adds the goals and the two rank titles, shows the
    briefing and runs the check script (150) once a month; the check script measures each goal into its variable,
    marks it met or not met, ends the scenario with rank 1 when all goals are met, and with rank 2 when the time
    limit has passed. Returns {script instance: instructions}."""
    T = s32(table)
    entry = [_ins("AddGoal", k + 1, T, T_GOAL0 + k) for k in range(len(goals))]
    entry += [_ins("AddRankInfo", 1, T, T_RANK0), _ins("AddRankInfo", 2, T, T_RANK0 + 1)]
    if briefing:
        entry.append(_ins("MakeDialogText", T, T_BRIEFING, 1))
    entry.append(_ins("RepeatRegular", MONTHLY, G_SCRIPT, 150))
    check = []
    for k, gl in enumerate(goals):
        cmd, extra = MEASURES[gl["measure"]]
        v = k + 1
        check.append(_ins(cmd, v, *extra))
        if "at_least" in gl:
            met, unmet = _ins("GreaterThan", _var(v), int(gl["at_least"]) - 1), _ins("LessThan", _var(v), int(gl["at_least"]))
        else:
            met, unmet = _ins("LessThan", _var(v), int(gl["at_most"]) + 1), _ins("GreaterThan", _var(v), int(gl["at_most"]))
        check += [_ins("If"), met, _ins("MarkGoalStatus", k + 1, 1), _ins("If"), unmet, _ins("MarkGoalStatus", k + 1, 0)]
    check += [_ins("If"), _ins("AllGoalsMet"), _ins("BeginBlock"), _ins("SetResultsDlgText", T, T_RESULT0, 1),
              _ins("EndScenario", 1), _ins("EndBlock")]
    if months:
        check += [_ins("GetMonthsElapsed", V_MONTHS), _ins("If"), _ins("GreaterThan", _var(V_MONTHS), int(months) - 1),
                  _ins("BeginBlock"), _ins("SetResultsDlgText", T, T_RESULT0 + 1, 2), _ins("EndScenario", 2),
                  _ins("EndBlock")]
    return {149: entry, 150: check}


def build(city_records: list, table: int, texts: dict[int, str], scripts: dict[int, list[dict]], entry: int,
          advisor: int, pic, base_path: str) -> list:
    """The records of a new .SNR: the city, the scenario header, picture, SNR chunk, texts and scripts."""
    out = [r for r in city_records if r[1] not in (G_HEADER, G_SNR, G_SCRIPT) and r[1] != table]
    out.append((T_HEADER, G_HEADER, 0, struct.pack("<Iii", table, 3, 3)))
    out.append((T_PICTURE, G_HEADER, 1, bmp_bytes(pic)))
    out.append((T_TEXT, G_HEADER, 2, b"\x05\x00\x00\x00M"))
    snr = (f"SNR \r\n{base_path}\r\n{T_SCRIPT}     {G_SCRIPT}      {entry} \r\n{s32(table)}    1 \r\n"
           f" {s32(advisor)}   1\r\n{s32(table)} \r\n")
    out.append((T_SNR, G_SNR, 0, snr.encode("cp1252", "replace")))
    out += [(T_TEXT, table, k, text_record(v)) for k, v in sorted(texts.items())]
    out += [(T_SCRIPT, G_SCRIPT, k, format_script(v).encode("cp1252")) for k, v in sorted(scripts.items())]
    return out


def create(name: str, base_city: str, description: str, goals: list[dict], months: int = 0, briefing: str = "",
           win_title: str = "Scenario Completed!", win_text: str = "", lose_title: str = "Time Is Up",
           lose_text: str = "", advisor: str = "planner", picture_path: str = "", overwrite: bool = False) -> dict:
    """Write Cities\\Scenarios\\<name>.SNR: the base saved city plus goals checked monthly (see compile_goals)."""
    from .bridge import GAME_DIR
    clean = name.strip()
    if not clean or any(c in clean for c in '\\/:*?"<>|'):
        raise GameError("name: a plain file name (no \\ / : * ? \" < > |)")
    if not goals:
        raise GameError("give at least one goal")
    for k, gl in enumerate(goals):
        if gl.get("measure") not in MEASURES:
            raise GameError(f"goal {k + 1}: measure one of {sorted(MEASURES)}")
        if ("at_least" in gl) == ("at_most" in gl):
            raise GameError(f"goal {k + 1}: give at_least or at_most (one of them)")
        if not str(gl.get("text", "")).strip():
            raise GameError(f"goal {k + 1}: give its text (what the player reads)")
    if advisor not in ADVISORS:
        raise GameError(f"advisor: one of {sorted(ADVISORS)}")
    base = os.path.join(GAME_DIR, "Cities", base_city if base_city.lower().endswith(".sc3") else base_city + ".sc3")
    if not os.path.isfile(base):
        raise GameError(f"no saved city {base_city!r} in the Cities folder (list_cities kind=city; save_city makes one)")
    path = os.path.join(folder(), clean + ".SNR")
    if os.path.exists(path) and not overwrite:
        raise GameError(f"{clean}.SNR exists: give another name or overwrite=true")
    shipped = {"a better betterfeld", "criminalville", "fall of the wall", "frankfurtfest", "london fires",
               "lord of the locusts", "rags to riches", "seoul world cup", "separation anxiety", "top of the world",
               "tutorial on getting started", "tutorial on sea and air", "tutorial on transportation"}
    if clean.lower() in shipped:
        raise GameError("that is one of the game's own scenarios: choose another name")
    table = table_id(clean)
    texts = {0: description or clean, 1: clean, T_RANK0: win_title, T_RANK0 + 1: lose_title,
             T_RESULT0: win_text or win_title, T_RESULT0 + 1: lose_text or lose_title}
    if briefing:
        texts[T_BRIEFING] = briefing
    for k, gl in enumerate(goals):
        texts[T_GOAL0 + k] = str(gl["text"])
    scripts = compile_goals(table, goals, months, bool(briefing))
    from PIL import Image
    pic = picture(clean, Image.open(picture_path) if picture_path else None)
    city = ixf.read(open(base, "rb").read())
    ixf.write(path, build(city, table, texts, scripts, 149, ADVISORS[advisor], pic, base))
    return {"file": path, "name": clean, "goals": len(goals), "months": months, "text_table": f"{table:#010x}",
            "bytes": os.path.getsize(path)}


# ---------------------------------------------------------------- reading
def read(path_or_name: str) -> dict:
    """Everything in a scenario file: name and description, base city, entry script, texts (embedded and from the
    game's text tables), goals, and every script as instructions with opcode names."""
    p = path_or_name
    if not os.path.isfile(p):
        p = os.path.join(folder(), path_or_name if path_or_name.lower().endswith(".snr") else path_or_name + ".SNR")
    if not os.path.isfile(p):
        raise GameError(f"no scenario file {path_or_name!r} (list_cities(kind='scenario') lists them)")
    recs = ixf.read(open(p, "rb").read())
    by = {(t, g, i): d for t, g, i, d in recs}
    out = {"file": p}
    h = by.get((T_HEADER, G_HEADER, 0))
    table = struct.unpack_from("<I", h)[0] if h else 0
    if h:
        out["header"] = [f"{table:#010x}", *struct.unpack_from("<ii", h, 4)]
    snr = by.get((T_SNR, G_SNR, 0))
    entry = None
    if snr:
        lines = [ln.strip() for ln in snr.decode("cp1252", "replace").replace("\r", "").split("\n")]
        out["snr_chunk"] = [ln for ln in lines if ln]
        try:
            entry = int(lines[2].split()[2])
            out["base_city"] = lines[1]
            out["entry_script"] = entry
            out["guide_advisor"] = f"{int(lines[4].split()[0]) & 0xFFFFFFFF:#010x}"
        except (IndexError, ValueError):
            pass
    pic = by.get((T_PICTURE, G_HEADER, 1))
    if pic and pic[:2] == b"BM":
        out["picture"] = list(struct.unpack_from("<ii", pic, 18))
    texts = {i: read_text_record(d) for (t, g, i), d in by.items() if t == T_TEXT and g == table and table}
    from . import text as gametext
    for (tt, ix), s in getattr(gametext, "_TABLE", {}).items() if gametext.text(table, 1) is not None else []:
        if tt == table:
            texts.setdefault(ix, s)
    out["name"] = texts.get(1, os.path.splitext(os.path.basename(p))[0])
    out["description"] = texts.get(0, "")
    out["texts"] = {str(k): v for k, v in sorted(texts.items())}
    out["texts_embedded"] = sum(1 for (t, g, i) in by if t == T_TEXT and g == table)
    scripts = {}
    for (t, g, i), d in by.items():
        if t == T_SCRIPT and g == G_SCRIPT:
            scripts[i] = parse_script(d.decode("cp1252", "replace"))
    out["scripts"] = {str(k): v for k, v in sorted(scripts.items())}
    out["city_records"] = sum(1 for (t, g, i) in by if g not in (G_HEADER, G_SNR, G_SCRIPT, table))
    return out
