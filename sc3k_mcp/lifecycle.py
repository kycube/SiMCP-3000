"""New city / load / save / exit through the game's own screens and dialogs.

The game's dialogs are GZWIND modal windows: wm = *(SC3U.exe 0x4FAC90); wm+0x194 = modal depth; wm+0x30 = the
current modal window, whose client rect is at +0x14 {x0, y0, x1, y1}. Closing one = wm->vt[0x44](0xD, win, result)
(EndModal). Controls are clicked relative to the window's top-left, measured in notes/UI_ATLAS.md.
"""

from __future__ import annotations

import os
import struct
import time

from .catalog import COMMANDS, LOAD_KINDS, SAVE_AS
from .game import APPS, Game, GameError

WM_GLOBAL = 0x4FAC90
BTN = {"abort": 0x53018146, "cancel": 0x53018147, "ignore": 0x53018148, "no": 0x53018149, "ok": 0x5301814A,
       "retry": 0x5301814B, "yes": 0x5301814C}
CITIES_DIR = os.path.join(os.path.dirname(APPS), "Cities")

# dialog sizes (w, h) -> kind
DIALOG_KINDS = {(288, 139): "prompt", (639, 368): "new_city_options", (478, 353): "file", (307, 274): "tip",
                (370, 412): "picker"}

# New City Options, relative to the window's top-left
NCO = {"name": (116, 63), "mayor": (116, 101),
       "difficulty": {"easy": (29, 141), "medium": (29, 159), "hard": (29, 177)},
       "year": {1900: (29, 213), 1950: (29, 231), 2000: (29, 249)},
       "size": {"miniature": (114, 213), "small": (114, 231), "medium": (114, 249), "large": (114, 267)},
       "disasters": (23, 302), "auto_budget": (23, 319), "ok": (610, 346)}
FILE_DLG = {"file_name": (380, 270), "ok": (445, 325)}
MAIN_MENU = {"start_new_city": (357, 400), "load_city": (690, 470), "scenario": (611, 243),
             "starter_town": (447, 269), "terrain": (587, 543)}
MAIN_MENU_SIZE = (640, 480)               # the main menu window (modal, depth 1)
TERRAIN_ACCEPT, TERRAIN_REGENERATE = (937, 590), (940, 443)


def shipped_files() -> set[str]:
    """Lower-case names of the city files the game was installed with (GOG manifest), never to be overwritten."""
    global _SHIPPED
    if _SHIPPED is None:
        _SHIPPED = set()
        try:
            for line in open(os.path.join(os.path.dirname(APPS), "goggame-galaxyFileList.ini"), encoding="latin-1"):
                _, _, path = line.strip().partition("=")
                if path.lower().startswith("cities\\"):
                    _SHIPPED.add(os.path.basename(path).lower())
        except OSError:
            pass
    return _SHIPPED


_SHIPPED: set[str] | None = None


class Lifecycle:
    def __init__(self, game: Game):
        self.g = game

    # ------------------------------------------------------------ modal windows
    def _menu_entry(self, pos) -> dict:
        """Click a main-menu entry (retrying while the menu is still animating in) and return the window it
        opens."""
        for _ in range(4):
            self.g.click(*pos, wait_ms=500)
            try:
                return self.wait_modal(timeout=5)
            except GameError:
                continue
        raise GameError("the main menu did not respond")

    def at_main_menu(self) -> bool:
        """The main menu window (modal, 640x480) is the top window."""
        wm = self.g.u32(WM_GLOBAL)
        win = self.g.u32(wm + 0x30)
        if self.g.i32(wm + 0x194) <= 0 or not win:
            return False
        x0, y0, x1, y1 = struct.unpack("<4i", self.g.proc.read(win + 0x14, 16))
        return (x1 - x0, y1 - y0) == MAIN_MENU_SIZE

    def modal(self, details: bool = True) -> dict | None:
        wm = self.g.u32(WM_GLOBAL)
        depth = self.g.i32(wm + 0x194)
        win = self.g.u32(wm + 0x30)
        if depth <= 0 or not win:
            return None
        x0, y0, x1, y1 = struct.unpack("<4i", self.g.proc.read(win + 0x14, 16))
        size = (x1 - x0, y1 - y0)
        if size == MAIN_MENU_SIZE:
            return None                             # the main menu is itself a modal window: a screen, not a dialog
        out = {"depth": depth, "window": win, "rect": [x0, y0, x1, y1],
               "kind": DIALOG_KINDS.get(size, f"dialog_{size[0]}x{size[1]}")}
        if details:
            try:
                out.update(self.dialog_text(win))
            except Exception:                       # a window being torn down; the basics still stand
                pass
        return out

    # GZWIND windows: +0x14 rect {x0, y0, x1, y1} (client coords), +0x34 -> std::list of child windows
    # {next, prev, child*}, +0x44 the window's text (cRZString). Classes by vtable (GZWIND.dll RVA).
    GZ_BUTTON, GZ_TEXT, GZ_RICHTEXT = 0x2B190, 0x2BBD0, 0x2BF10     # rich text: its text is at +0xA8
    GZ_EDIT = 0x2A8CC                                                # edit field: its text is at +0xC4
    GZ_RADIOGROUP = 0x2A5EC                                          # radio group: selected item id at +0xC4

    def widgets(self, win: int, depth: int = 0) -> list[dict]:
        """Every descendant window of `win` with its class (vtable module+RVA), text and rect."""
        out = []
        head = self.g.u32(win + 0x34)
        node, k = self.g.u32(head), 0
        gz = self.g.mod("gzwind.dll")
        while node and node != head and k < 64:
            ch = self.g.u32(node + 8)
            vt = self.g.u32(ch)
            cls = vt - gz if gz <= vt < gz + 0x100000 else vt
            try:
                text = self.g.rz_string(ch + {self.GZ_RICHTEXT: 0xA8, self.GZ_EDIT: 0xC4}.get(cls, 0x44), 8192)
            except Exception:
                text = ""
            rect = list(struct.unpack("<4i", self.g.proc.read(ch + 0x14, 16)))
            d = {"window": ch, "class": cls, "text": text, "rect": rect, "depth": depth, "id": self.g.u32(ch + 0x10)}
            if cls == self.GZ_BUTTON and self.g.u32(ch + 0xF4) in (4, 5, 6, 7):
                d["checked"] = bool(self.g.u32(ch + 0xA8) & 1)     # toggle / check box / radio item
            elif cls == self.GZ_RADIOGROUP:
                d["selected"] = self.g.u32(ch + 0xC4)
            out.append(d)
            if depth < 4:
                out += self.widgets(ch, depth + 1)
            node = self.g.u32(node)
            k += 1
        return out

    def _buttons(self, w: list[dict]) -> list[tuple[str, dict]]:
        """(label, button) for every button of a window: its own text, else the text label right next to it on
        the same row (option buttons such as "Cancel Deal" / "Keep Deal", "Impact Analysis:")."""
        out = []
        labels = [x for x in w if x["class"] == self.GZ_TEXT and x["text"].strip()]
        for b in w:
            if b["class"] != self.GZ_BUTTON or b["depth"] > 0:
                continue
            if b["text"].strip():
                out.append((b["text"].strip(), b))
                continue
            bx0, by0, bx1, by1 = b["rect"]
            for lab in labels:
                lx0, ly0, lx1, ly1 = lab["rect"]
                overlap = min(by1, ly1) - max(by0, ly0)
                if overlap >= min(by1 - by0, ly1 - ly0) // 2 and (0 <= lx0 - bx1 <= 20 or 0 <= bx0 - lx1 <= 20):
                    out.append((lab["text"].strip().rstrip(":"), b))
                    break
        return out

    def dialog_text(self, win: int) -> dict:
        """Title, message text and button labels of a dialog."""
        title = ""
        try:
            title = self.g.rz_string(win + 0x44)
        except Exception:
            pass
        w = self.widgets(win)
        buttons = self._buttons(w)
        used = {b[0] for b in buttons}
        texts = [x["text"].strip() for x in w if x["class"] in (self.GZ_TEXT, self.GZ_RICHTEXT) and x["text"].strip()
                 and x["text"].strip().rstrip(":") not in used]
        fields = [x["text"] for x in sorted((x for x in w if x["class"] == self.GZ_EDIT),
                                            key=lambda x: (x["rect"][1], x["rect"][0]))]
        if not title:
            title = next((x["text"] for x in w if x["depth"] == 0 and x["class"] not in
                          (self.GZ_BUTTON, self.GZ_TEXT, self.GZ_RICHTEXT) and x["text"].strip()), "")
        out = {}
        if title:
            out["title"] = title
        if texts:
            out["text"] = "\n".join(texts)
        if buttons:
            out["buttons"] = [b[0] for b in buttons]
        if fields:
            out["fields"] = fields                     # edit fields' contents, top to bottom
        return out

    def close(self) -> None:
        """Close the open game window the way a player would: its title-bar X button if it has one (some
        windows, e.g. the Neighbors Map, reopen themselves after EndModal(cancel)), else EndModal(cancel),
        else Esc."""
        m = self.modal()
        if not m:
            raise GameError("no game dialog is open")
        depth, title = m["depth"], m.get("title")

        def closed():
            n = self.modal()
            return not n or n["depth"] < depth or (n["window"] != m["window"] and n.get("title") != title)

        w = self.widgets(m["window"])
        for bar in (x for x in w if x["depth"] == 0 and x["class"] not in (self.GZ_BUTTON, self.GZ_TEXT)
                    and x["text"]):
            x0, y0, x1, y1 = bar["rect"]
            for b in w:
                bx0, by0, bx1, by1 = b["rect"]
                if b["depth"] == 1 and b["class"] == self.GZ_BUTTON and y0 <= by0 and by1 <= y1                         and x1 - 16 <= bx1 <= x1:                    # the X sits at the bar's right end
                    self.g.click((bx0 + bx1) // 2, (by0 + by1) // 2, wait_ms=500)
                    if closed():
                        return
        self.end_modal("cancel")
        if closed():
            return
        self.g.key("esc", wait_ms=400)
        if not closed():
            raise GameError("could not close the game window")

    def press_ok(self) -> None:
        """Press the open window's unlabeled OK (check mark) button at its bottom right, else close it."""
        m = self.modal(details=False)
        if not m:
            return
        btns = [x for x in self.widgets(m["window"]) if x["class"] == self.GZ_BUTTON and x["depth"] == 0
                and not x["text"].strip()]
        if not btns:
            self.close()
            return
        x0, y0, x1, y1 = max(btns, key=lambda x: (x["rect"][3], x["rect"][2]))["rect"]
        self.g.click((x0 + x1) // 2, (y0 + y1) // 2, wait_ms=800)

    def press(self, label: str) -> None:
        """Click the open dialog's button whose label is `label` (case-insensitive), as a player would."""
        m = self.modal(details=False)
        if not m:
            raise GameError("no game dialog is open")
        want = label.strip().lower().rstrip(":")
        for lab, x in self._buttons(self.widgets(m["window"])):
            if lab.lower() == want:
                x0, y0, x1, y1 = x["rect"]
                self.g.click((x0 + x1) // 2, (y0 + y1) // 2, wait_ms=400)
                return
        raise GameError(f"the dialog has no {label!r} button (has {self.modal().get('buttons')})")

    def end_modal(self, result: str | int = "ok") -> None:
        m = self.modal()
        if not m:
            raise GameError("no game dialog is open")
        wm = self.g.u32(WM_GLOBAL)
        if isinstance(result, str) and result not in BTN:
            raise GameError(f"unknown button {result!r}: use one of the dialog's buttons {m.get('buttons')} "
                            f"or {list(BTN)}")
        code = BTN[result] if isinstance(result, str) else int(result)
        self.g.call(self.g.vfn(wm, 0x44 // 4), [0xD, m["window"], code], this=wm)
        time.sleep(0.3)

    def wait_modal(self, kind: str | None = None, timeout: float = 15.0) -> dict:
        deadline = time.time() + timeout
        while time.time() < deadline:
            m = self.modal()
            if m and (kind is None or m["kind"] == kind):
                return m
            time.sleep(0.1)
        raise GameError(f"timed out waiting for a {kind or 'game'} dialog")

    def wait_no_modal(self, timeout: float = 15.0) -> None:
        deadline = time.time() + timeout
        while self.modal():
            if time.time() > deadline:
                raise GameError("a game dialog stayed open")
            time.sleep(0.1)

    def close_tips(self, wait: float = 3.0) -> int:
        """Close startup tips/notices that appear after a city starts or loads."""
        closed, deadline = 0, time.time() + wait
        while time.time() < deadline:
            m = self.modal()
            if m and m["kind"] == "tip":
                self.end_modal("ok")
                closed += 1
                deadline = time.time() + 1.0
            time.sleep(0.15)
        return closed

    def _click_rel(self, m: dict, pos, wait_ms: int = 250) -> None:
        self.g.click(m["rect"][0] + pos[0], m["rect"][1] + pos[1], wait_ms=wait_ms)

    def _fill_rel(self, m: dict, pos, text: str) -> None:
        self._click_rel(m, pos, 150)
        self.g.key("end", wait_ms=30)
        for _ in range(40):
            self.g.key("backspace", wait_ms=5)
        self.g.type_text(text)

    # ------------------------------------------------------------ flows
    def _leave_city(self, save: bool) -> None:
        """Answer the 'save this city?' prompt the game asks before replacing the current city."""
        m = self.wait_modal(timeout=10)
        if m["kind"] == "prompt":
            if save:
                raise GameError("save the city first with save_city; then call again with save=False")
            self.end_modal("no")

    def _fill_options(self, m: dict, name, mayor, difficulty, start_year=None, size=None, disasters=False,
                      auto_budget=False) -> None:
        """Fill the New City Options dialog and press OK (year/size are skipped when None, e.g. for starter
        towns and real-city terrains, which fix them)."""
        if name:
            self._fill_rel(m, NCO["name"], name)
        if mayor:
            self._fill_rel(m, NCO["mayor"], mayor)
        edits = [x["text"] for x in sorted((x for x in self.widgets(m["window"]) if x["class"] == self.GZ_EDIT),
                                            key=lambda x: x["rect"][1])]
        if len(edits) >= 2 and ((name and edits[0] != name) or (mayor and edits[1] != mayor)):
            raise GameError(f"the name fields read {edits[:2]} (expected {[name, mayor]})")
        self._click_rel(m, NCO["difficulty"][difficulty])
        if start_year is not None:
            self._click_rel(m, NCO["year"][start_year])
        if size is not None:
            self._click_rel(m, NCO["size"][size])
        # Disasters / Auto Budget are applied after the city exists, with the game's own setters (see
        # _apply_flags) - the check boxes' state is not read from the screen
        self._flags = (bool(disasters), bool(auto_budget))
        self._click_rel(m, NCO["ok"], 1000)

    def _apply_flags(self) -> dict:
        """Set the city's Disasters / Auto Budget options (city vt[0x9C] / vt[0x94], as City Options does) to
        what new_city / load_city asked for, and read them back from memory."""
        flags = getattr(self, "_flags", None)
        c = self.g.city()
        if not flags or not c:
            return {}
        self._flags = None
        disasters, auto_budget = flags
        if bool(self.g.proc.read(c + 0x1F2, 1)[0]) != disasters:
            self.g.call(self.g.vfn(c, 0x9C // 4), [int(disasters)], this=c)
        if bool(self.g.proc.read(c + 0x1F1, 1)[0]) != auto_budget:
            self.g.call(self.g.vfn(c, 0x94 // 4), [int(auto_budget)], this=c)
        return {"disasters": bool(self.g.proc.read(c + 0x1F2, 1)[0]),
                "auto_budget": bool(self.g.proc.read(c + 0x1F1, 1)[0])}

    def new_city(self, name: str = "New City", mayor: str = "Mayor", difficulty: str = "easy",
                 start_year: int = 1900, size: str = "large", disasters: bool = False, auto_budget: bool = False,
                 regenerate: int = 0, accept_terrain: bool = True) -> dict:
        g = self.g
        g.ensure()
        if difficulty not in NCO["difficulty"] or start_year not in NCO["year"] or size not in NCO["size"]:
            raise GameError("difficulty easy|medium|hard, start_year 1900|1950|2000, size miniature|small|medium|large")
        if self.modal():
            raise GameError("close the open game dialog first")
        if g.city():
            r = g.bridge.command(COMMANDS["new_city"], defer=True)
            if not r.ok:
                raise GameError(f"new city command failed: {r}")
            self._leave_city(False)
        else:
            self._menu_entry(MAIN_MENU["start_new_city"])
        m = self.wait_modal("new_city_options", timeout=20)
        self._fill_options(m, name, mayor, difficulty, start_year, size, disasters, auto_budget)
        self.wait_no_modal(timeout=30)
        deadline = time.time() + 20
        while not g.city() and time.time() < deadline:
            time.sleep(0.2)
        time.sleep(1.5)                                   # terrain editor
        for _ in range(max(0, regenerate)):
            g.click(*TERRAIN_REGENERATE, wait_ms=2500)
        if not accept_terrain:
            return {**g.status(), "screen": "terrain_editor"}        # options applied by accept_terrain
        g.click(*TERRAIN_ACCEPT, wait_ms=2000)
        self.close_tips(4.0)
        return {**g.status(), "options": self._apply_flags()}

    # ------------------------------------------------------------ terrain editor (new city, before Accept)
    # re/agents/uistate/REPORT.md: the editor's controller TE = *(*(SC3U 0x4FAA30) + 0x28) holds every parameter:
    # +0x0C feature, +0x10 word coast mask (1 NW = map edge y=0, 2 NE = x=0, 4 SW = x=max, 8 SE = y=max),
    # +0x12/+0x13/+0x14 hills/water/trees 0..255. The panel's controls feed it through the game's own handlers:
    # sliders (class 0x2AEB4, iface vt[0x14] SetValue notifies the panel), the Pick Features preview (clicking its
    # centre cycles the feature, an edge strip toggles that coast; points relative to the preview's top-left).
    # Re-Generate builds the map from TE (only it regenerates).
    FEATURES = {0: "none", 1: "lake", 2: "river_nw_se", 3: "river_sw_ne", 4: "mountain"}
    COAST_BITS = {"NW": 1, "NE": 2, "SW": 4, "SE": 8}
    COAST_CLICK = {"NW": (31, 16), "NE": (93, 16), "SE": (87, 44), "SW": (37, 44)}
    SLIDER_CLASS, PREVIEW_CLASS = 0x2AEB4, 0xAAB14
    SLIDER_IDS = {"hills": 0x72E867AD, "water": 0x72E867AE, "trees": 0x72E867AF}
    EDITOR_TOOLS = ("lower", "raise", "level", "trees", "water", "bulldoze")   # the six buttons, by row
    MODE_MANAGER = 0x4FAA30

    def terrain_panel(self) -> dict | None:
        root = self.g.u32(self.g.u32(WM_GLOBAL) + 0x38)
        if not root:
            return None
        head = self.g.u32(root + 0x34)
        node, k = self.g.u32(head), 0
        while node and node != head and k < 200:
            ch = self.g.u32(node + 8)
            try:
                if self.g.rz_string(ch + 0x44) == "Terrain Edit":
                    rect = list(struct.unpack("<4i", self.g.proc.read(ch + 0x14, 16)))
                    if rect[2] > rect[0]:
                        return {"window": ch, "rect": rect}
            except Exception:
                pass
            node = self.g.u32(node)
            k += 1
        return None

    def _editor(self) -> tuple[dict, list[dict]]:
        p = self.terrain_panel()
        if not p:
            raise GameError("the terrain editor is not open (new_city with accept_terrain=False opens it)")
        return p, self.widgets(p["window"])

    def _te(self) -> int:
        te = self.g.u32(self.g.u32(self.MODE_MANAGER) + 0x28)
        if not te:
            raise GameError("terrain editor controller not found")
        return te

    def _preview(self, w) -> dict:
        simui = self.g.mod("simui.dll")
        for x in w:
            if x["class"] == simui + self.PREVIEW_CLASS:
                return x
        raise GameError("terrain feature preview not found")

    def terrain_settings(self) -> dict:
        """The terrain editor's parameters, read from its controller object (no screen reading)."""
        self._editor()
        te = self._te()
        mask = struct.unpack("<H", self.g.proc.read(te + 0x10, 2))[0]
        h, w, t = self.g.proc.read(te + 0x12, 3)
        return {"hills": round(h * 100 / 255), "water": round(w * 100 / 255), "trees": round(t * 100 / 255),
                "feature": self.FEATURES.get(self.g.u32(te + 0x0C), "?"),
                "coasts": [e for e, bit in self.COAST_BITS.items() if mask & bit]}

    # ------------------------------------------------------------ preferences (re/agents/features/REPORT.md s. 3)
    # PR = *(app+0xF8), app = *(SC3U 0x4FA86C); the Preferences window (COMM 0xC3001401) edits it and OK applies
    # (SIMUI 0x100593AC: live setters, audio, then message 0x231BBF91; saved in Apps\SC3.cfg).
    PREF_CHECKS = {"auto_go_to_disasters": 0x2F95AF8, "show_tips_at_startup": 0x2F95AF7, "sound_3d": 0x2F95AFC,
                   "sound_effects": 0x2F95AFB, "ambient_sound": 0x2F95AFA, "music": 0x2F95AF9}
    PREF_RADIOS = {"traffic_visible": {3: 0x2F95AEC, 2: 0x2F95AED, 1: 0x2F95AEE, 0: 0x2F95AEF},
                   "sims_visible": {2: 0x2F95AF1, 1: 0x2F95AF2, 0: 0x2F95AF3},
                   "other_animations": {True: 0x2F95AF5, False: 0x2F95AF6}}
    PREF_SLIDERS = {"music_volume": 0x2F95AFE, "ambient_volume": 0x2F95AFF, "sound_effects_volume": 0x2F95B00}
    PREF_OK = 0x2F95AD8

    def _prefs_ptr(self) -> int:
        g = self.g
        app = g.u32(g.mod("sc3u.exe") + 0xFA86C)
        return g.u32(app + 0xF8) if app else 0

    def preferences(self) -> dict:
        """The game's Preferences, read from its preferences object (no window opened)."""
        g = self.g
        PR = self._prefs_ptr()
        if not PR:
            raise GameError("the game's preferences object is not available yet")
        b = g.proc.read(PR + 0x6C, 0x38)
        i32 = lambda off: struct.unpack_from("<i", b, off - 0x6C)[0]
        vol = lambda off: round(i32(off) * 100 / 1024)
        return {"traffic_visible": i32(0x94), "sims_visible": i32(0x98), "other_animations": bool(i32(0x9C)),
                "auto_go_to_disasters": bool(b[0x84 - 0x6C]), "show_tips_at_startup": bool(b[0xA0 - 0x6C]),
                "music": bool(b[0x6D - 0x6C]), "music_volume": vol(0x70),
                "sound_effects": bool(i32(0x74)), "sound_effects_volume": vol(0x78),
                "ambient_sound": bool(i32(0x7C)), "ambient_volume": vol(0x80), "sound_3d": bool(b[0]),
                "music_tracks": {t["name"]: t["enabled"] for t in self.music_tracks()},
                "new_city_defaults": {"auto_budget": bool(b[0x85 - 0x6C]), "disasters": bool(b[0x86 - 0x6C])},
                "scales": {"traffic_visible": "draw traffic at the closest N zoom levels (0 = off, 3 = most)",
                           "sims_visible": "draw pedestrians at the closest N zoom levels (0 = off, 2 = most)",
                           "volumes": "percent"}}

    # ------------------------------------------------------------ the game's Query tool
    QUERY_TOOL = 0x0339DA69           # command the city view installs for query mode (SIMSPR 0x10048AEE)
    QUERY_LINES = 0xAAF64             # SIMUI RVA of the Query window's line-table widget class; +0xC4 = std::list
                                      # of lines {next, prev, label cRZString +8, value cRZString +0x1C}

    def query(self, x: int, y: int) -> dict:
        """Use the game's Query tool on tile (x, y) and return exactly what its Query window shows (title, every
        label / value line, other texts), then close the window. Verified on a Berlin fire station: Number of
        Fires 29/Month, Calls 37/Month, Performance Rating Excellent, Funding Cost $33/Month."""
        g = self.g
        g.need_city()
        if self.modal():
            raise GameError("close the open game dialog first")
        W, H = struct.unpack("<ii", g.proc.read(g.need_city() + 0x3C, 8))
        if not (0 <= x < W and 0 <= y < H):
            raise GameError(f"tile ({x}, {y}) is outside the {W}x{H} map")
        g.apply_tool(self.QUERY_TOOL, [(x, y)], click_each=True)
        try:
            m = self.wait_modal(timeout=5)
        except GameError:
            g.finish_pending(timeout=2)
            return {"x": x, "y": y, "query": None, "note": "the game showed no Query window for this tile"}
        try:
            cls = g.mod("simui.dll") + self.QUERY_LINES
            w = self.widgets(m["window"])
            lines = []
            for t in (x for x in w if x["class"] == cls):
                head = g.u32(t["window"] + 0xC4)
                node, k = g.u32(head), 0
                while node and node != head and k < 80:
                    label, value = g.rz_string(node + 8), g.rz_string(node + 0x1C)
                    if label or value:
                        lines.append({"label": label.rstrip(":"), "value": value})
                    node, k = g.u32(node), k + 1
                break
            texts = [x["text"] for x in w if x["text"] and x["class"] in (self.GZ_TEXT, self.GZ_RICHTEXT)
                     and x["text"] != m.get("title")]
            out = {"x": x, "y": y, "window": m.get("title"), "title": texts[0] if texts else "",
                   "lines": lines, "texts": texts[1:]}
        finally:
            self.close()
            g.finish_pending(timeout=3)
        return out

    # ------------------------------------------------------------ city styles and description (re/agents/styles)
    # scheme manager S = *(app+0x108): +0x18 landscape, +0x2C trees (if byte +0x34), +0x50 buildings (if byte +0x58);
    # SetScheme(landscape, trees, buildings, showProgress) = S vt[0x18] (SIMINIT 0x10006589), what City Options' OK
    # calls; ids from Sys\SC3CityScheme.ini (names from the window's icons)
    LANDSCAPES = {"temperate": 0, "winter": 0xC55A6D62, "desert": 0xC55A6D84, "dry": 0x655B8076,
                  "tropical": 0xE55B8055}
    TREE_SETS = {"mixed": 0, "desert": 0xC55A6D62, "deciduous": 0xC55A6D84, "palms": 0x79EF435A,
                 "conifers": 0x39EDF62B}
    BUILDING_STYLES = {"north_american": 0, "european": 0xE523F3FB, "asian": 0x6523F3D5}

    def _scheme(self) -> int:
        g = self.g
        S = g.u32(g.u32(g.mod("sc3u.exe") + 0xFA86C) + 0x108)
        if not S:
            raise GameError("the city scheme manager is not available")
        return S

    def _scheme_ids(self) -> tuple[int, int, int]:
        g, S = self.g, self._scheme()
        b = g.proc.read(S, 0x60)
        land = struct.unpack_from("<I", b, 0x18)[0]
        trees = struct.unpack_from("<I", b, 0x2C)[0] if b[0x34] else 0
        bldg = struct.unpack_from("<I", b, 0x50)[0] if b[0x58] else 0
        return land, trees, bldg

    def city_options(self) -> dict:
        g = self.g
        c = g.need_city()
        land, trees, bldg = self._scheme_ids()
        name = lambda table, v: next((k for k, i in table.items() if i == v), f"{v:#010x}")
        S = self._scheme()
        user_made = (g.u32(S + 0x84) - g.u32(S + 0x80)) // 0xC if g.u32(S + 0x80) else 0
        b = g.city_basics(c)
        return {"name": b["name"], "mayor": b["mayor"], "description": g.rz_string(c + 0x70, 8192),
                "landscape": name(self.LANDSCAPES, land), "trees": name(self.TREE_SETS, trees),
                "buildings": name(self.BUILDING_STYLES, bldg),
                "disasters": bool(g.proc.read(c + 0x1F2, 1)[0]), "auto_budget": bool(g.proc.read(c + 0x1F1, 1)[0]),
                "user_made_buildings_available": user_made,
                "choices": {"landscape": list(self.LANDSCAPES), "trees": list(self.TREE_SETS),
                            "buildings": list(self.BUILDING_STYLES)}}

    def set_city_style(self, landscape=None, trees=None, buildings=None) -> dict:
        for v, table, what in ((landscape, self.LANDSCAPES, "landscape"), (trees, self.TREE_SETS, "trees"),
                               (buildings, self.BUILDING_STYLES, "buildings")):
            if v is not None and v not in table:
                raise GameError(f"{what} must be one of {list(table)}")
        g = self.g
        g.need_city()
        cur = self._scheme_ids()
        want = (self.LANDSCAPES[landscape] if landscape is not None else cur[0],
                self.TREE_SETS[trees] if trees is not None else cur[1],
                self.BUILDING_STYLES[buildings] if buildings is not None else cur[2])
        if want != cur:
            S = self._scheme()
            g.call(g.vfn(S, 0x18 // 4), [*want, 0], this=S)
        if self._scheme_ids() != want:
            raise GameError(f"the game did not take the styles (now {self.city_options()})")
        return self.city_options()

    def set_description(self, text: str) -> dict:
        """city vt[0x84](cIGZString*) (SIMCITY 0x100070C0), the setter City Options' OK calls; the string is a
        cRZString built in scratch memory (vtable SIMCITY 0x1001378C, begin, end, cap, refcount)."""
        g = self.g
        c = g.need_city()
        data = text.encode("cp1252", "replace")[:4000]
        buf = g.scratch() + 0x1000
        p = buf + 0x20
        g.proc.write(p, data + b"\0")
        g.proc.write(buf, struct.pack("<5I", g.mod("simcity.dll") + 0x1378C, p, p + len(data), p + len(data), 1))
        g.call(g.vfn(c, 0x84 // 4), [buf], this=c)
        got = g.rz_string(c + 0x70, 8192)
        if got != data.decode("cp1252"):
            raise GameError(f"the description reads {got!r}")
        return self.city_options()

    # ------------------------------------------------------------ user-made building replacements
    # (re/agents/replace/REPORT.md): the scheme manager S keeps the user-made (Building Architect) buildings
    # (S vt[0x9C] collection of IID 0x656CD1DD objects b: size u8 b+4, name cRZString b+8, architect b+0x1C,
    # key b-0x14), the replaceable default buildings (set S+0xB0, keys at node+0x10) and the replacements (map
    # S+0x8C: node+0x10 default key, node+0x1C user key). Default building prototypes: map OM+0x1C (key node+0x10,
    # P node+0x1C; P name cRZString +0xC, type id +8, size +0x24, current replacement +0x120).
    REPLACE_CATEGORIES = ("residential", "commercial", "industrial", "rewards", "other")

    def _om(self) -> int:
        g = self.g
        app = g.u32(g.mod("sc3u.exe") + 0xFA86C)
        return g.u32(g.u32(app + 0xDC) + 0x10)

    def _tree(self, head: int, limit: int = 20000) -> list[int]:
        out, stack, n = [], [], self.g.u32(head + 4) if head else 0
        while (stack or n) and len(out) < limit:
            while n and n != head:
                stack.append(n)
                n = self.g.u32(n + 8)
            if not stack:
                break
            n = stack.pop()
            out.append(n)
            n = self.g.u32(n + 0xC)
            if n == head:
                n = 0
        return out

    def user_buildings(self) -> list[dict]:
        g, S = self.g, self._scheme()
        C = g.call(g.vfn(S, 0x9C // 4), [], this=S)
        a, b = g.u32(C + 4), g.u32(C + 8)
        out = []
        for p in (struct.unpack(f"<{(b - a) // 4}I", g.proc.read(a, b - a)) if b > a else ()):
            key = struct.unpack("<3I", g.proc.read(p - 0x14, 12))
            out.append({"name": g.rz_string(p + 8), "architect": g.rz_string(p + 0x1C), "size": g.proc.read(p + 4, 1)[0],
                        "_key": key, "_b": p})
        return out

    def replaceable_buildings(self) -> list[dict]:
        g, S = self.g, self._scheme()
        protos = {struct.unpack("<3I", g.proc.read(n + 0x10, 12)): g.u32(n + 0x1C)
                  for n in self._tree(g.u32(self._om() + 0x1C))}
        users = {u["_b"]: u["name"] for u in self.user_buildings()}
        GM = g.u32(g.u32(g.u32(g.mod("sc3u.exe") + 0xFA86C) + 0xDC) + 0xC)
        cat_cache = {}

        def category(t):
            if t not in cat_cache:
                c = 4
                for i, valve in enumerate((3000, 5000, 8000)):
                    if g.call(g.vfn(GM, 0x24 // 4), [valve, t], this=GM) & 0xFF:
                        c = i
                        break
                else:
                    if g.call(g.vfn(S, 0x94 // 4), [t], this=S) & 0xFF:
                        c = 3
                cat_cache[t] = self.REPLACE_CATEGORIES[c]
            return cat_cache[t]

        out = []
        for n in self._tree(g.u32(S + 0xB0)):
            key = struct.unpack("<3I", g.proc.read(n + 0x10, 12))
            P = protos.get(key)
            if not P:
                continue
            t, rep = g.u32(P + 8), g.u32(P + 0x120)
            out.append({"id": key[2], "name": g.rz_string(P + 0xC), "size": g.i32(P + 0x24), "category": category(t),
                        "replaced_by": users.get(rep) if rep else None, "_key": key})
        return out

    def replacements(self) -> list[dict]:
        g, S = self.g, self._scheme()
        users = {u["_key"]: u["name"] for u in self.user_buildings()}
        protos = {struct.unpack("<3I", g.proc.read(n + 0x10, 12)): g.u32(n + 0x1C)
                  for n in self._tree(g.u32(self._om() + 0x1C))}
        out = []
        for n in self._tree(g.u32(S + 0x8C)):
            dk = struct.unpack("<3I", g.proc.read(n + 0x10, 12))
            uk = struct.unpack("<3I", g.proc.read(n + 0x1C, 12))
            P = protos.get(dk)
            out.append({"building": g.rz_string(P + 0xC) if P else f"{dk[2]:#x}", "id": dk[2],
                        "replaced_by": users.get(uk, f"{uk[2]:#x}")})
        return out

    def _find_default(self, building) -> dict:
        rows = self.replaceable_buildings()
        if isinstance(building, int) or str(building).lower().startswith("0x") or str(building).isdigit():
            bid = int(str(building), 0)
            hit = [r for r in rows if r["id"] == bid]
        else:
            hit = [r for r in rows if r["name"].lower() == str(building).lower()]
        if not hit:
            raise GameError(f"no replaceable building {building!r} (building_replacements(list_replaceable=True))")
        if len(hit) > 1:
            raise GameError(f"{building!r} is ambiguous; use its id: {[hex(r['id']) for r in hit]}")
        return hit[0]

    def replace_building(self, building, user_building: str | None) -> dict:
        """As the Building Replacement Manager's Replace / Revert + OK: S vt[0xA8](&defaultKey, &userKey)
        (SIMINIT 0x10005B95) or S vt[0xAC](&defaultKey) to revert; the game swaps the sprites of the existing
        buildings at once (cosmetic; saved with the city)."""
        g, S = self.g, self._scheme()
        g.need_city()
        row = self._find_default(building)
        buf = g.scratch() + 0x1800
        g.proc.write(buf, struct.pack("<3I", *row["_key"]))
        if user_building:
            u = next((u for u in self.user_buildings() if u["name"].lower() == user_building.lower()), None)
            if not u:
                raise GameError(f"no user-made building {user_building!r}; available: "
                                f"{[x['name'] for x in self.user_buildings()]}")
            if u["size"] != row["size"]:
                raise GameError(f"{u['name']} is {u['size']}x{u['size']} but {row['name']} is "
                                f"{row['size']}x{row['size']} (the game's manager only pairs equal sizes)")
            g.proc.write(buf + 0xC, struct.pack("<3I", *u["_key"]))
            g.call(g.vfn(S, 0xA8 // 4), [buf, buf + 0xC], this=S)
        else:
            g.call(g.vfn(S, 0xAC // 4), [buf], this=S)
        now = self._find_default(row["id"])
        if (now["replaced_by"] or None) != (next((u["name"] for u in self.user_buildings()
                                                  if user_building and u["name"].lower() == user_building.lower()),
                                                 None)):
            raise GameError(f"the replacement did not take: {now}")
        return {k: v for k, v in now.items() if not k.startswith("_")}

    def clear_replacements(self) -> list:
        g, S = self.g, self._scheme()
        g.call(g.vfn(S, 0xBC // 4), [], this=S)                 # what "Clear Set" does after its Yes/No box
        return self.replacements()

    def import_replacements(self, city_file: str, merge: bool = True) -> list:
        """"Import Set from Selected City": S vt[0xB8](path) merges that saved city's replacements (SIMINIT
        0x100057F9); merge=False clears the current set first (as Clear Set)."""
        from .bridge import GAME_DIR
        g, S = self.g, self._scheme()
        base = os.path.splitext(os.path.basename(city_file))[0]
        path = os.path.join(GAME_DIR, "Cities", base + ".sc3")
        if not os.path.exists(path):
            raise GameError(f"no saved city {base}.sc3 (list_cities)")
        if not merge:
            g.call(g.vfn(S, 0xBC // 4), [], this=S)
        data = path.encode("cp1252")
        buf = g.scratch() + 0x1900
        p = buf + 0x20
        g.proc.write(p, data + b"\0")
        g.proc.write(buf, struct.pack("<5I", g.mod("siminit.dll") + 0x2F230, p, p + len(data), p + len(data), 100))
        g.call(g.vfn(S, 0xB8 // 4), [buf], this=S)
        return self.replacements()

    # ------------------------------------------------------------ snapshots (re/agents/viewsnap/REPORT.md s. 3)
    SNAP_FRAME = 0x85202C0E
    SNAP_SIZES = {"small": 1, "medium": 2, "large": 3}

    def _root(self) -> int:
        return self.g.u32(self.g.u32(self.g.mod("sc3u.exe") + 0xFAC90) + 0x38)

    def _find_window(self, wid: int = 0, title: str | None = None) -> dict | None:
        for w in self.widgets(self._root()):
            if (wid and w["id"] == wid) or (title and w["text"] == title and w["depth"] <= 1):
                return w
        return None

    def close_window(self, title: str) -> bool:
        """Close a non-modal game window (e.g. the Photo Album) with its title-bar X button."""
        win = self._find_window(title=title)
        if not win:
            return False
        w = self.widgets(win["window"])
        bars = [x for x in w if x["text"] == title and x["class"] not in (self.GZ_BUTTON, self.GZ_TEXT)]
        for bar in bars:
            x0, y0, x1, y1 = bar["rect"]
            for b in w:
                bx0, by0, bx1, by1 = b["rect"]
                if b["class"] == self.GZ_BUTTON and y0 <= by0 and by1 <= y1 and x1 - 16 <= bx1 <= x1:
                    self.g.click((bx0 + bx1) // 2, (by0 + by1) // 2, wait_ms=400)
                    return self._find_window(title=title) is None
        return False

    def snapshots(self) -> list[dict]:
        from .bridge import GAME_DIR
        root = os.path.join(GAME_DIR, "Albums")
        out = []
        for d, _, files in os.walk(root):
            for f in sorted(files):
                if f.lower().endswith(".jpg"):
                    p = os.path.join(d, f)
                    out.append({"album": os.path.basename(d), "file": f, "path": p, "bytes": os.path.getsize(p),
                                "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(p)))})
        return out

    def take_snapshot(self, size: str = "medium") -> dict:
        """Take a snapshot as the game's Take Snapshot does: its frame (PMSG {0x2435FF70, size}) is placed over
        the middle of the city view, hidden (as Return does) so the picture shows only the city, and saved by the
        frame's own handler ({0x1A5D056D, 1, 1}: capture, JPG in Albums, close); the Photo Album the game then
        opens is closed again."""
        from .bridge import GAME_DIR
        if size not in self.SNAP_SIZES:
            raise GameError(f"size must be one of {list(self.SNAP_SIZES)}")
        g = self.g
        g.need_city()
        if self.modal():
            raise GameError("close the open game dialog first")
        before = {s["path"] for s in self.snapshots()}
        g.post_message(0x2435FF70, self.SNAP_SIZES[size], 0, 0)
        win = None
        for _ in range(40):
            time.sleep(0.1)
            w = self._find_window(self.SNAP_FRAME)
            if w:
                win = w["window"]
                break
        if not win:
            raise GameError("the snapshot frame did not open")
        x0, y0, x1, y1 = struct.unpack("<4i", g.proc.read(win + 0x80, 16))
        w, h = x1 - x0, y1 - y0
        g.call(g.vfn(win, 0xCC // 4), [(1024 - w) // 2, (768 - h) // 2], this=win)    # move to the middle
        g.call(g.vfn(win, 0xFC // 4), [], this=win)                                   # hide, as Return does
        time.sleep(0.4)                                                               # let the view redraw
        buf = g.scratch() + 0x3E0
        g.proc.write(buf, struct.pack("<4I", 0x1A5D056D, 1, 1, 0))
        g.call(g.vfn(win, 0x0C // 4), [buf], this=win)                                # save + close
        new = []
        for _ in range(50):
            time.sleep(0.1)
            new = [s for s in self.snapshots() if s["path"] not in before]
            if new:
                break
        time.sleep(0.3)
        album_closed = self.close_window("View Snapshots")
        if not new:
            raise GameError(f"no new snapshot appeared in {os.path.join(GAME_DIR, 'Albums')}")
        return {**new[0], "size": [w, h], "album_window_closed": album_closed}

    def _audio(self) -> int:
        g = self.g
        aud = g.call(g.mod("simui.dll") + 0x8E95F)            # audio manager getter (SIMUI 0x1008E95F)
        if not aud:
            raise GameError("no audio manager")
        return aud

    def music_tracks(self) -> list[dict]:
        """The songs as the Preferences window lists them (audio manager vt[0x14](0x3F7) reset, then 0x3F8 per song
        with an id and a cRZString name) and whether each is in the rotation (PR vt[0x8C](id); re/agents/viewsnap
        REPORT section 8)."""
        g = self.g
        aud, PR = self._audio(), self._prefs_ptr()
        buf = g.scratch() + 0x400
        g.proc.write(buf, b"\0" * 0x30)
        g.call(g.mod("simui.dll") + 0x5EB6, [], this=buf + 0x10)    # construct the name string (cRZString)
        g.call(g.vfn(aud, 0x14 // 4), [0x3F7, 0, 0, 0, 0], this=aud)
        out = []
        for _ in range(100):
            g.proc.write(buf, b"\0" * 4)
            if g.call(g.vfn(aud, 0x14 // 4), [0x3F8, buf, buf + 0x10, 0, 0], this=aud) or not g.u32(buf):
                break
            sid = g.u32(buf)
            out.append({"id": sid, "name": g.rz_string(buf + 0x10),
                        "enabled": bool(g.call(g.vfn(PR, 0x8C // 4), [sid], this=PR) & 0xFF)})
        return out

    def set_music_tracks(self, want: dict) -> list[dict]:
        """Turn songs on or off as the Preferences window's song check boxes do (SIMUI 0x10059000: audio manager
        vt[0x14](0x3F4, id, on) then PR vt[0x90](id, on))."""
        g = self.g
        tracks = self.music_tracks()
        by = {t["name"].lower(): t for t in tracks}
        unknown = [n for n in want if n.lower() not in by]
        if unknown:
            raise GameError(f"unknown song(s) {unknown}; songs: {[t['name'] for t in tracks]}")
        aud, PR = self._audio(), self._prefs_ptr()
        for n, on in want.items():
            sid = by[n.lower()]["id"]
            g.call(g.vfn(aud, 0x14 // 4), [0x3F4, sid, 1 if on else 0, 0, 0], this=aud)
            g.call(g.vfn(PR, 0x90 // 4), [sid, 1 if on else 0], this=PR)
        got = self.music_tracks()
        bad = [t["name"] for t in got if t["name"].lower() in {k.lower() for k in want}
               and t["enabled"] != bool({k.lower(): v for k, v in want.items()}[t["name"].lower()])]
        if bad:
            raise GameError(f"songs did not change: {bad}")
        return got

    def set_preferences(self, **want) -> dict:
        """Change preferences as a player does: open the Preferences window, set the controls, press OK; the result
        is read back from the preferences object."""
        want = {k: v for k, v in want.items() if v is not None}
        tracks = want.pop("music_tracks", None)
        if tracks:
            self.set_music_tracks(tracks)
        if not want:
            return self.preferences()
        unknown = set(want) - set(self.PREF_CHECKS) - set(self.PREF_RADIOS) - set(self.PREF_SLIDERS)
        if unknown:
            raise GameError(f"unknown preference(s) {sorted(unknown)}")
        for k, v in want.items():
            if k in self.PREF_RADIOS:
                key = bool(v) if k == "other_animations" else int(v)
                if key not in self.PREF_RADIOS[k]:
                    raise GameError(f"{k} must be one of {sorted(self.PREF_RADIOS[k], key=int)}")
        if self.modal():
            raise GameError("close the open game dialog first")
        g = self.g
        r = g.bridge.command(COMMANDS["preferences"], [0, 0, 0], defer=True)
        if not r.ok:
            raise GameError(f"preferences command failed: {r}")
        m = self.wait_modal(timeout=10)
        if m.get("title") != "Preferences":
            raise GameError(f"expected the Preferences window, got {m.get('title')!r}")
        try:
            byid = {w["id"]: w for w in self.widgets(m["window"])}

            def click(wid):
                x0, y0, x1, y1 = byid[wid]["rect"]
                g.click((x0 + x1) // 2, (y0 + y1) // 2, wait_ms=150)

            for k, v in want.items():
                if k in self.PREF_CHECKS:
                    if byid[self.PREF_CHECKS[k]].get("checked") != bool(v):
                        click(self.PREF_CHECKS[k])
                elif k in self.PREF_RADIOS:
                    click(self.PREF_RADIOS[k][bool(v) if k == "other_animations" else int(v)])
                else:
                    iface = byid[self.PREF_SLIDERS[k]]["window"] + 0xA4
                    g.call(g.vfn(iface, 0x14 // 4), [max(0, min(1024, round(float(v) * 1024 / 100)))], this=iface)
            now = {w["id"]: w for w in self.widgets(m["window"])}
            wrong = [k for k, v in want.items()
                     if (k in self.PREF_CHECKS and now[self.PREF_CHECKS[k]].get("checked") != bool(v))
                     or (k in self.PREF_RADIOS and not now[self.PREF_RADIOS[k][bool(v) if k == "other_animations"
                                                                            else int(v)]].get("checked"))]
            if wrong:
                raise GameError(f"the window did not take {wrong}; nothing changed")
        except Exception:
            self.close()
            raise
        click(self.PREF_OK)
        self.wait_no_modal(timeout=10)
        got = self.preferences()
        off = {k: got[k] for k, v in want.items()
               if (got[k] != (round(float(v)) if k in self.PREF_SLIDERS else
                              (bool(v) if isinstance(got[k], bool) else int(v))))
               and not (k in self.PREF_SLIDERS and abs(got[k] - float(v)) <= 1)}
        if off:
            raise GameError(f"preferences after OK differ from the request: {off}")
        return got

    def _set_slider(self, sl: dict, pct: float, te_off: int) -> None:
        """Set a terrain slider through its own SetValue (the panel then updates the controller)."""
        target = max(0, min(255, round(pct * 255 / 100)))
        iface = sl["window"] + 0xA4
        self.g.call(self.g.vfn(iface, 0x14 // 4), [target], this=iface)
        if abs(self.g.proc.read(self._te() + te_off, 1)[0] - target) > 1:
            raise GameError("the terrain editor did not take the slider value")

    def set_terrain(self, hills=None, water=None, trees=None, feature=None, coasts=None,
                    regenerate: bool = True) -> dict:
        """Set the terrain editor's parameters as a player would and (by default) press Re-Generate; every
        change is checked in the editor's controller object."""
        p, w = self._editor()
        te = self._te()
        sliders = {x["id"]: x for x in w if x["class"] == self.SLIDER_CLASS}
        for (name, sid), v, off in zip(self.SLIDER_IDS.items(), (hills, water, trees), (0x12, 0x13, 0x14)):
            if v is not None:
                if sid not in sliders:
                    raise GameError(f"{name} slider not found")
                self._set_slider(sliders[sid], v, off)
        pv = self._preview(w)
        x0, y0, x1, y1 = pv["rect"]
        if feature is not None:
            want = {v: k for k, v in self.FEATURES.items()}.get(feature)
            if want is None:
                raise GameError(f"feature must be one of {list(self.FEATURES.values())}")
            for _ in range(6):
                if self.g.u32(te + 0x0C) == want:
                    break
                self.g.click((x0 + x1) // 2, (y0 + y1) // 2, wait_ms=300)
            if self.g.u32(te + 0x0C) != want:
                raise GameError("could not select the terrain feature")
        if coasts is not None:
            want = {c.upper() for c in coasts}
            if not want <= set(self.COAST_BITS):
                raise GameError("coasts: any of NW, NE, SE, SW (edges as the Pick Features preview shows them)")
            for _ in range(3):
                mask = struct.unpack("<H", self.g.proc.read(te + 0x10, 2))[0]
                have = {e for e, bit in self.COAST_BITS.items() if mask & bit}
                if have == want:
                    break
                for e in have ^ want:
                    dx, dy = self.COAST_CLICK[e]
                    self.g.click(x0 + dx, y0 + dy, wait_ms=300)
            if set(self.terrain_settings()["coasts"]) != want:
                raise GameError("could not set the coastlines")
        if regenerate:
            self._press_in(w, "Re-Generate Terrain", 2500)
        return self.terrain_settings()

    def _press_in(self, w, label: str, wait_ms: int = 500) -> None:
        for x in w:
            if x["class"] == self.GZ_BUTTON and x["text"] == label:
                x0, y0, x1, y1 = x["rect"]
                self.g.click((x0 + x1) // 2, (y0 + y1) // 2, wait_ms=wait_ms)
                return
        raise GameError(f"{label!r} not found in the terrain editor")

    def editor_tool(self, name: str) -> int:
        """Pick one of the terrain editor's six tools (free while editing); returns the installed tool."""
        if name not in self.EDITOR_TOOLS:
            raise GameError(f"tool must be one of {list(self.EDITOR_TOOLS)}")
        p, w = self._editor()
        btns = sorted((x for x in w if x["class"] == self.GZ_BUTTON and x["depth"] == 0 and not x["text"]
                       and x["rect"][3] - x["rect"][1] >= 35), key=lambda x: (x["rect"][1], x["rect"][0]))
        if len(btns) != 6:
            raise GameError(f"expected 6 terrain tool buttons, found {len(btns)}")
        x0, y0, x1, y1 = btns[self.EDITOR_TOOLS.index(name)]["rect"]
        self.g.click((x0 + x1) // 2, (y0 + y1) // 2, wait_ms=300)
        tool = self.g.u32(self.g.view() + 0x228)
        if not tool:
            raise GameError("the terrain tool did not install")
        return tool

    def accept_terrain(self) -> dict:
        p, w = self._editor()
        self._press_in(w, "Accept this Terrain", 2000)
        self.close_tips(4.0)
        return {**self.g.status(), "options": self._apply_flags()}

    def rename_city(self, name: str | None = None, mayor: str | None = None) -> dict:
        """Change the city's and/or mayor's name in the game's City Options window (COMM 0x855A2DC4 [0, 0, 0]),
        checking the fields from memory before pressing OK."""
        g = self.g
        g.need_city()
        if self.modal():
            raise GameError("close the open game dialog first")
        r = g.bridge.command(COMMANDS["city_properties"], [0, 0, 0], defer=True)
        if not r.ok:
            raise GameError(f"city options command failed: {r}")
        m = self.wait_modal("new_city_options", timeout=10)
        if name:
            self._fill_rel(m, NCO["name"], name)
        if mayor:
            self._fill_rel(m, NCO["mayor"], mayor)
        edits = sorted((x for x in self.widgets(m["window"]) if x["class"] == self.GZ_EDIT),
                       key=lambda x: x["rect"][1])
        have = [x["text"] for x in edits]
        want = [name or have[0], mayor or have[1]] if len(have) >= 2 else have
        if have[:2] != want:
            self.end_modal("cancel")
            raise GameError(f"the fields read {have[:2]}, expected {want}; nothing changed")
        self._click_rel(m, NCO["ok"], 800)
        self.wait_no_modal(timeout=10)
        b = g.city_basics(g.need_city())
        return {"name": b["name"], "mayor": b["mayor"]}

    def save_city(self, file_name: str, overwrite: bool = False) -> dict:
        g = self.g
        g.need_city()
        if self.modal():
            raise GameError("close the open game dialog first")
        base = os.path.splitext(os.path.basename(file_name))[0]
        if (base + ".sc3").lower() in shipped_files():
            raise GameError(f"{base}.sc3 is one of the game's own cities; save under another name")
        if os.path.exists(os.path.join(CITIES_DIR, base + ".sc3")) and not overwrite:
            raise GameError(f"{base}.sc3 already exists; pass overwrite=True to replace it")
        r = g.bridge.command(COMMANDS["save"], [SAVE_AS], defer=True)
        if not r.ok:
            raise GameError(f"save command failed: {r}")
        m = self.wait_modal("file", timeout=15)
        self._fill_rel(m, FILE_DLG["file_name"], base)
        self._click_rel(m, FILE_DLG["ok"], 800)
        deadline = time.time() + 20
        while time.time() < deadline:
            m2 = self.modal()
            if not m2:
                break
            if m2["kind"] == "prompt":             # "replace existing file?"
                self.end_modal("yes")
            time.sleep(0.2)
        path = os.path.join(CITIES_DIR, base + ".sc3")
        return {"saved": os.path.exists(path), "path": path, "size": os.path.getsize(path) if os.path.exists(path) else 0}

    LOAD_FILES = {"city": ("", ".sc3", "saved_city"), "starter_town": ("StarterTowns", ".st3", "starter_town"),
                  "terrain": ("Terrains", ".sct", "real_city_terrain"), "scenario": ("Scenarios", ".snr", "scenario")}

    def load_city(self, file_name: str, save_current: bool = False, kind: str = "city", name: str = "",
                  mayor: str = "", difficulty: str = "easy", disasters: bool = False,
                  auto_budget: bool = False) -> dict:
        """Load a saved city, starter town, real-city terrain or scenario through the game's Load command
        (COMM 0x610438A4 [kind, 0, 0], as the Load submenu does) and its file dialog. Starter towns and
        terrains go on to the New City Options (name, mayor, difficulty...); a terrain then opens the terrain
        editor (accept with accept_terrain)."""
        g = self.g
        g.ensure()
        if kind not in self.LOAD_FILES:
            raise GameError(f"kind must be one of {list(self.LOAD_FILES)}")
        if self.modal():
            raise GameError("close the open game dialog first")
        folder, ext, load_kind = self.LOAD_FILES[kind]
        base = os.path.splitext(os.path.basename(file_name))[0]
        d = os.path.join(CITIES_DIR, folder)
        if not any(f.lower() == (base + ext).lower() for f in os.listdir(d)):
            raise GameError(f"no {kind} file {base}{ext} in {d} (see list_cities)")
        old_city = g.city()
        if self.at_main_menu():
            # the menu's own entries close the menu window after loading (the command would leave it open)
            m = self._menu_entry(MAIN_MENU["load_city" if kind == "city" else kind])
        else:
            r = g.bridge.command(COMMANDS["load"], [LOAD_KINDS[load_kind], 0, 0], defer=True)
            if not r.ok:
                raise GameError(f"load command failed: {r}")
            m = self.wait_modal(timeout=20)
        if m["kind"] == "prompt":
            if save_current:
                self.end_modal("no")
                raise GameError("save the city first with save_city; then load with save_current=False")
            self.end_modal("no")
        m = self.wait_modal("file", timeout=20)
        self._fill_rel(m, FILE_DLG["file_name"], base)
        self._click_rel(m, FILE_DLG["ok"], 1000)
        out = {}
        deadline = time.time() + 90
        went_away = False              # the old city object is destroyed for ~0.1 s; the new one may reuse its address
        while time.time() < deadline:
            cur = g.city()
            went_away = went_away or not cur
            m2 = self.modal()
            fresh = cur and (cur != old_city or went_away)
            if m2 and m2["kind"] == "tip":
                self.end_modal("ok")
            elif m2 and m2["kind"] == "new_city_options":
                self._fill_options(m2, name, mayor, difficulty, None, None, disasters, auto_budget)
            elif m2 and m2["kind"] not in ("file", "prompt") and kind == "scenario" and fresh:
                out["intro"] = {k: m2.get(k) for k in ("title", "text")}      # the scenario briefing
                self.press_ok()          # its OK (not the X) also dismisses the main menu when started from it
                break
            elif not m2 and fresh:
                if kind == "scenario" and "briefing_wait" not in out:
                    out["briefing_wait"] = time.time() + 10      # its briefing opens a moment after the city
                elif kind == "scenario" and time.time() < out["briefing_wait"]:
                    pass
                else:
                    if kind == "terrain" and self.terrain_panel():
                        out["screen"] = "terrain_editor"
                    break
            time.sleep(0.02 if not went_away else 0.1)
        else:
            raise GameError(f"the {kind} did not finish loading (dialog: {self.modal()})")
        out.pop("briefing_wait", None)
        if kind in ("starter_town", "terrain"):
            out["options"] = self._apply_flags()
        if out.get("screen") != "terrain_editor":
            self.close_tips(3.0)
        return {**g.status(), **out}

    # ------------------------------------------------------------ building pickers
    PICKER_LIST = {"x": 223, "y0": 64, "row": 14}      # first row centre and row height, relative to the window
    PICKER_OK = (337, 385)

    # Neighbors Map window (menu command COMM 0x630288e9): quadrant centres relative to the window's top-left,
    # in the order of the neighbor records at *(city+0xF4)+0x50 (verified in two cities: NE, NW, SW, SE)
    NEIGHBOR_QUADRANTS = (("NE", (231, 143)), ("NW", (133, 143)), ("SW", (133, 241)), ("SE", (231, 241)))

    NEIGHBORS_DISCUSS = (341, 326)      # "Discuss Deal" button, relative to the Neighbors Map's top-left

    def discuss_deal(self, neighbor: int) -> dict:
        """Open the Neighbors Map, select neighbor `neighbor` (record index) and press Discuss Deal: the game
        opens the deal's terms (a petition window: Cancel Deal / Keep Deal / Impact Analysis). Returns that
        dialog; the Neighbors Map stays open underneath. Closes the map and raises if there is no deal."""
        if self.modal():
            raise GameError("close the open game dialog first")
        self.g.bridge.command(0x630288e9, defer=True)
        m = self.wait_modal(timeout=10)
        x0, y0 = m["rect"][:2]
        cx, cy = self.NEIGHBOR_QUADRANTS[neighbor][1]
        self.g.click(x0 + cx, y0 + cy, wait_ms=350)
        rows = next(iter(self.lists(m["window"])), [])
        if not rows:
            self.close()
            raise GameError("no current deal with this neighbor")
        self.g.click(x0 + self.NEIGHBORS_DISCUSS[0], y0 + self.NEIGHBORS_DISCUSS[1], wait_ms=300)
        deadline = time.time() + 5
        while time.time() < deadline:
            n = self.modal()
            if n and n["depth"] > m["depth"]:
                return n
            time.sleep(0.1)
        self.close()
        raise GameError("the game opened no deal window")

    GZ_LIST = 0x2C710            # list-box window class; its list interface (vtable GZWIND+0x2C64C) is at +0xA4

    def list_items(self, list_win: int) -> list[dict]:
        """Rows of a GZWIND list box: interface at window+0xA4, rows = std::list at interface+4
        {next, prev, cRZString text, .., +0x1C id}."""
        iface = list_win + 0xA4
        if self.g.u32(iface) != self.g.mod("gzwind.dll") + 0x2C64C:
            raise GameError("not a list box")
        head = self.g.u32(iface + 4)
        items, node = [], self.g.u32(head)
        while node and node != head and len(items) < 400:
            items.append({"index": len(items), "name": self.g.rz_string(node + 8), "id": self.g.u32(node + 0x1C)})
            node = self.g.u32(node)
        return items

    def lists(self, win: int) -> list[list[dict]]:
        """The rows of every list box in a window (in child order)."""
        return [self.list_items(w["window"]) for w in self.widgets(win) if w["class"] == self.GZ_LIST]

    def _picker_list(self, win: int) -> list[dict]:
        """Items of the picker's list box. The list cuts long names ("Waste to Energy Inciner..."): those are given
        back in full from the building catalog when the prefix names exactly one building."""
        from .catalog import buildings
        for rows in self.lists(win):
            if rows:
                full = sorted({v["name"] for v in buildings().values() if v.get("name")})
                for r in rows:
                    n = r.get("name", "")
                    if n.endswith("..."):
                        hits = [f for f in full if f.lower().startswith(n[:-3].lower())]
                        if len(hits) == 1:
                            r["name"] = hits[0]
                return rows
        return []

    def picker_items(self, picker_param: int) -> list[dict]:
        """Open a building picker, read what the game offers now, close it."""
        if self.modal():
            raise GameError("close the open game dialog first")
        self.g.bridge.command(0xE2ED3560, [picker_param], defer=True)
        m = self.wait_modal("picker", timeout=10)
        try:
            return self._picker_list(m["window"])
        finally:
            self.end_modal("cancel")

    def choose_in_picker(self, picker_param: int, name: str) -> int:
        """Open a building picker, select `name` (as the game lists it) and press OK; returns the installed tool."""
        if self.modal():
            raise GameError("close the open game dialog first")
        self.g.bridge.command(0xE2ED3560, [picker_param], defer=True)
        m = self.wait_modal("picker", timeout=10)
        items = self._picker_list(m["window"])
        match = [it for it in items if it["name"].lower() == name.lower()] or \
                [it for it in items if name.lower() in it["name"].lower()]
        if not match:
            self.end_modal("cancel")
            raise GameError(f"{name!r} is not offered now; available: {[it['name'] for it in items]}")
        i = match[0]["index"]
        self._click_rel(m, (self.PICKER_LIST["x"], self.PICKER_LIST["y0"] + i * self.PICKER_LIST["row"]), 300)
        self._click_rel(m, self.PICKER_OK, 500)
        self.wait_no_modal(timeout=10)
        tool = self.g.u32(self.g.view() + 0x228)
        if not tool:
            raise GameError("the picker did not install a building tool")
        return tool

    def list_cities(self) -> list[dict]:
        out = []
        for kind, (folder, ext, _) in self.LOAD_FILES.items():
            d = os.path.join(CITIES_DIR, folder)
            for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
                if f.lower().endswith(ext):
                    out.append({"name": f[: -len(ext)], "kind": kind, "bytes": os.path.getsize(os.path.join(d, f))})
        return out

    def exit_game(self) -> dict:
        g = self.g
        r = g.bridge.command(COMMANDS["quit"], defer=True)
        if not r.ok:
            raise GameError(f"quit command failed: {r}")
        m = self.wait_modal(timeout=10)
        self.end_modal("ok")
        deadline = time.time() + 20
        while time.time() < deadline:
            m2 = self.modal() if g.proc.alive() else None
            if not g.proc.alive():
                return {"exited": True}
            if m2 and m2["kind"] == "prompt":
                self.end_modal("no")             # don't save
            time.sleep(0.3)
        return {"exited": not g.proc.alive()}
