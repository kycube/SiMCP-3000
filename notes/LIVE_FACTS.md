# Facts measured in the running game

Heap addresses change per run; offsets and vtables don't. Module addresses are preferred-base VAs.

## Session 2026-10-07 (new Large city, 1900, Easy, disasters off, paused)

### ROOT: the city object

- **`*(STRTSIM.DLL 0x10032C9C)` = current city** (set with AddRef by `STRTSIM 0x100074B9`, released by
  `0x100074CB`). Also pointed to by `STRTSIM .data 0x10032F54` and `SIMSPR .data 0x10072BC4`.
- City object vtables: +0x00 `SIMCITY 0x10013260`, +0x04 `SIMCITY 0x1001324C`.
- +0x3C/+0x40/+0x44 = 256, 256, 256 (Large city: map size). +0x48 string object (vtable `SIMCITY 0x1001378C`,
  then begin/end/cap char*) = city name "New City"; +0x58 string = mayor name "Defacto"; +0x68 another string.
- **Simulator pointers** (vtables given; module = owner):

| Off | Vtable | Off | Vtable |
|---|---|---|---|
| +0x84,+0x88,+0x8C | SIMGEOM 0x10029E24 (x3) | +0xD8 | SIMSERV 0x1001EA38 |
| +0x90 | SC3U.exe 0x4D1088 | +0xDC | SIMSERV 0x1001F46C |
| +0xA0 | SIMGEOM 0x100292C0 | +0xE0 | SIMSERV 0x1001EE04 |
| +0xA4 | SIMDIRT 0x1002046C | +0xE4 | SIMRCI 0x1004C99C |
| +0xA8 | SIMNTWRK 0x1002C7BC | +0xE8 | SIMRCI 0x1004C208 |
| +0xAC | SimTransit 0x1001A368 | +0xEC | SIMRCI 0x1004C4A4 |
| +0xB0 | SIMGEOM 0x10029ABC | +0xF0 | SIMRCI 0x1004C624 |
| +0xB4 | SIMRCI 0x1004D1E0 | +0xF4 | SIMMISC 0x10040BF4 |
| +0xB8 | SIMUTIL 0x10020550 | +0xF8 | SIMMISC 0x10041000 |
| +0xBC | SIMUTIL 0x10022944 | +0xFC | SIMGEOM 0x1002A7B4 |
| +0xC0 | SIMMISC 0x10040F3C | +0x100 | SCENARIO 0x1001A64C |
| **+0xC4** | **SIMMISC 0x1003C550 = budget** | +0x104..+0x120 | SIMADV x8: 0x100310B4, 0x10030310, 0x1003056C, 0x10030A18, 0x10030884, 0x10030CCC, 0x10030EFC, 0x10031504 |
| +0xC8 | SIMMISC 0x10041324 | +0x124 | SIMCITY 0x10013140 |
| +0xCC | STRTSIM 0x1002C600 | +0x128 | SIMCITY 0x10013F78 |
| +0xD0 | SIMDSTR 0x100325A0 | +0x130 | SIMCITY 0x10013988 |
| +0xD4 | SIMECO 0x1001B984 | | |

- **Date object embedded at +0x134** (vtable `SIMCITY 0x10013978`): **+0x138 = Julian Day Number** (int32;
  2415021 = 1 Jan 1900, went to 2415022 after the sim ran ~8 s), +0x13C = year (1900), +0x140 = month (1),
  +0x14C, +0x150 = 1 (day?). The same JDN also sits at `SIMMISC 0x10040F3C object` + 0x2CC.
- Speed note: at the slowest speed (first of 4 speed boxes lit), unfocused, one day took ~8 s. The sim
  keeps running while the window is unfocused.
- **The simulation runs on its own thread** (not the UI thread). Hardware watchpoint on city+0x138: the only
  writer is `SIMCITY 0x1000566C` (`inc [esi+4]`) in `SIMCITY 0x100054E7` = **city vtable slot 127 (+0x1FC)**,
  thiscall(kind): kind 1 = new day (JDN+1 under the lock at city+0x1F4, posts message 0x43152585); other kinds
  post 0xC2A3FD82 / 0x237CFEE8 / 0x437CFFDE (month / year / ...). Candidate sim-thread loop `SIMCITY 0x100014DC`;
  step `0x100015FB`; message dispatcher `0x10001675` (kinds 0..8, jump table `0x1000172E`).
- Vtable trace over 10 s of running: city slots 141/142 polled ~95x from SIMSERV 0x10007BC2/0x10007CEE, slots
  144/145 ~156x from SIMSPR 0x1001CB64/0x1001CBF1; slots 127/131/138 from SIMCITY's own sim code.

### Dynamic RE tools in the bridge (live/ scripts)

- `live/trace_run.py run SECONDS | click X Y` - logs every virtual call on the city and budget objects (or
  `obj=ADDR:NSLOTS`), grouped by slot and caller. Bridge `trace_object`/`trace_class`/`trace_read`/`trace_stop`.
- `live/watch_run.py city+OFF|budget+OFF|ADDR [len] run SECONDS | click X Y [w|rw]` - hardware watchpoint
  (DR0-3 on all game threads + VEH), lists writer instructions with counts and thread ids.
- `live/memscan.py` (value scans, snapshots/diffs), `live/refs.py` (who points here), `live/dump.py`
  (annotated dump), `live/globals.py` (module globals -> objects), `live/com_classes.py` (class registry).

### Budget/finance object (SIMMISC.DLL)

- Object with vtables at +0x00 `SIMMISC 0x1003C550`, +0x04 `0x1003C508`, +0x08 `0x1003C5C0`
  (constructor stores them around `SIMMISC 0x100051B4..0x100051CC`, second ctor-like site `0x1000526E..7B`).
- **Funds = int64 at +0x38 and again at +0x40** (both changed 50,000 -> 49,615 when a 14-tile road was
  built for $385 with the game's own road tool). Status bar showed the same number.
- Pointers in the object: +0x14 -> object with vtable `SIMCITY 0x10013260`; +0x18 -> `SIMMISC 0x10040F3C`;
  +0x1C -> `SimTransit 0x1001A368`; +0x20 -> `SIMRCI 0x1004C624`; +0x24 -> `SIMMISC 0x10040BF4`;
  +0x28 -> `SIMRCI 0x1004C99C`; +0x2C and the dword before the object -> `SIMINIT 0x1002F350`;
  +0x30 -> `SIMRCI 0x1004CEE4`; +0x48 -> `SIMMISC 0x10041C04`.
- From +0x4C: an array of 0x24-byte named entries: vtable `SIMMISC 0x1003C434`, then a string object
  (begin/end/cap char*) whose text is `"Funds"`, then (0, ptr, 6, 0xAD, 0); next entry `"Residential Tax Rate"`
  ... (looks like named budget variables / line items).
- About 35 heap objects point at the budget object; no module `.data` points to it directly.

### Other objects seen

- `cRZCOM` (= `GZCOM()`), vtable `SC3U.exe 0x4D6D18`; class registry `std::map`-like tree at +0x4C
  (node: +4 parent, +8 left, +0xC right, +0x10 clsid, +0x14 version, +0x18 library*).
- Framework, vtable `SC3U.exe 0x4D6BF4` = `cIGZCOM->vtable[4]()`; holds the command line string.
- Directory manager `*(SC3U.exe 0x4FAC9C)`, vtable `0x4D8B4C`.
- A `SIMINIT 0x1002F350` object is referenced from `SIMGEOM.DLL` `.data` (+0x30928) and from the budget
  object; `SIMGEOM .data +0x3092C` -> `SIMINIT 0x1002FB44` object.
- `SC3U.exe .data 0x4FAA30` -> an object with vtable `SIMUI 0x100A2FC8`.
- Window: the `Gonzo` window procedure is `GZGraphicD.dll 0x10017E11`; it forwards mouse messages to
  `[obj+0x30]->vtable[0x64](msg*)` (a GZWIND window manager). GZWIND checks the real cursor with
  `GetCursorPos` (`GZWIND 0x10020271`), so synthetic clicks need the cursor faked (the bridge does this).

### UI flow that works with synthetic clicks (client coords, 1024x768 window, menu art 800x600 centred)

Main menu "Start New City" (357, 400) -> "New City Options" dialog (name, mayor, difficulty Easy/Medium/Hard,
start 1900/1950/2000, size Miniature/Small/Medium/Large, Disasters, Auto Budget; OK = (797, 544)) ->
"Terrain Edit" screen ("Accept this Terrain" = (937, 590)) -> city view, simulator paused, a "Llama Suggests"
tip (OK = (635, 497)). City toolbar on the right edge; transport menu (988, 174) -> road (943, 133).

## Verified recipes (2026-10-07, implemented in sc3k_mcp/)

Corrections to the above (from the core agent, confirmed): city+0x13C = founding year, +0x140 = user pause count,
+0x144 = system/modal pause count, +0x14C/+0x150 = effective/requested speed. Day step = slot 127 kind **2**.

- **Deterministic time** (game.advance_days): clk = *(city+0x130); clock Pause (vt slot 11); city ResumeSim
  (slot 132); call the clock's own AdvanceDay `SIMCITY+0xAA4D` (or AdvanceHour `+0xA9B1` x24 / AdvanceMinute
  `+0xA915` x1440 when the clock has hour/minute listeners, exactly like its timer callback `+0xA854`) via
  OP_REPEAT; post a no-op message (type 99) to the engine queue (*(city+0x124)+0x14, vt slot 3) and wait until the
  queue (std::list at q+4) is empty and the JDN reached the target; PauseSim + clock Resume. 40 days in 0.03 s
  (empty city). Stops early if city+0x144 > 0 (a modal dialog holds the engine).
- **Commands** (OP_COMMAND): SC3U 0x474908(&holder, id) -> command; uint32 params via operator new 0x4B4890(0x28)
  + 0x46F260(v, value, 3), AddRef, cmd->vt[0x0C](v); cmd->vt[0x2C]() executes; Release. Tool commands install the
  tool in the city view: view = (*(SIMSPR+0x72F24))->vt[0x74](); current tool *(view+0x228); camera *(view+0xB8).
  Commands that open modal windows must be run deferred (OP_COMMAND defer / OP_DEFER), else the bridge call blocks.
- **Tools by tile coordinates** (OP_TOOL_POINTS): the camera object's vtable is swapped for a copy whose slot 35
  (vt+0x8C, bool Pick(sx, sy, int out[3], flag)) returns our world points (tile*256, 0) for fake screen points
  (7+i, 7); then the tool's own handlers run: slot 12 move, 8 down (keys 0x10), 12 move..., 10 up. Works for line
  tools (SIMNTWRK), zone/area tools (SIMRCI), ploppables/trees/bulldoze (SIMGEOM), terrain (SIMDIRT). The game's own
  costs/rules apply (e.g. road $10/tile, police $500, power lines refused next to road+plant).
- **Any building by occupant id**: SIMGEOM operator new `+0x262A6`(0x120); ctor `+0x9443`(this, &key{0x207EDC0E,
  0x57E, occId}, 0, 0); cmd = obj+0x58; **AddRef**, cmd->vt[0x2C]() (installs; the view takes a ref), Release.
  (Without the AddRef the final Release freed the tool and the game crashed on the next frame.) Ploppable tool:
  occupant id at tool+0x110. The building pickers install this same class (coal plant = 0xCF).
- **Occupant scan** (OP_OCC_SCAN): walks manager grids (+0x98 cells, +0x9C flags; bit1 = anchor redirect) and calls
  occ vt+0x88 (category = CitySim.ini agent type, e.g. 13130 PoliceStation, 16000 Road, 300 Flora) and vt+0xD0
  (tile rect) per unique occupant: whole map in ~5 ms. Manager 0 (city+0x84) held everything seen so far.
  Building object (SIMGEOM 0x1002B860): +4 owner clsid, +8 type, +0xC occupant id, +0x1C category.
- **Dialogs**: wm = *(SC3U 0x4FAC90); depth wm+0x194; window wm+0x30, rect at window+0x14 {x0,y0,x1,y1};
  EndModal = wm->vt[0x44](0xD, win, result) with result OK 0x5301814A / Cancel ..47 / Yes ..4C / No ..49 (verified
  closing picker, exit prompt, save prompt, tip). Kinds by size: prompt 288x139, New City Options 639x368, file
  dialog 478x353, tip 307x274, picker 367x408.
- **Lifecycle** (lifecycle.py): new city = command 0xE3270FE9 (deferred) -> "save?" prompt (No) -> options dialog
  (controls relative to its rect, see lifecycle.NCO) -> OK -> terrain editor -> Accept (937,590) -> tip (OK).
  Save As = command 0x410438DD + 0xC3172AEA (deferred) -> file dialog (name at +380,+270, OK at +445,+325).
  Load = in-city Settings menu (990,470) -> Load (943,387) -> save prompt (No) -> file dialog (same layout). The
  Load command 0x610438A4 returned 0 when run directly in a city. Quit command = exit the whole game (prompt).
- **Economy (verified)**: set tax = write byte budget+0x8C+z*0x88 and valve->vt[0x6C](float bits from
  budget+0x208+4*rate) under the city lock (slots 141/142) - demand reacted; department funding via budget
  FindItem (vt+0x38) + item vt+0x20 + budget vt+0x40; ordinances map value is a POINTER to the record (+4 enacted,
  +5 available); IssueBond vt+0x5C(10000) -> record {month, maturity year, principal, total due, remaining, ...,
  payment}; funds only settle yearly (no change at month ends in 1900).
- **Display sleep**: monitor sleep stops DDrawCompat presenting until the game window is activated (clicked).

## Verified recipes, round 2 (2026-10-07, implemented)

- **Load command, corrected**: COMM 0x610438A4 needs THREE params [kind, 0, 0] (MenuItem.INI lines 0x10009301..04);
  with one param it returns 0. Kinds: saved city 0x83172AD7, starter town 0x63172B74, real-city terrain
  0x23172AF2, scenario 0xA42C7725. Deferred, in a city: save prompt -> file dialog (title "Load Scenario" etc.,
  same layout as Save As). Starter towns and terrains then show New City Options (year/size fixed by the file);
  a real-city terrain loaded straight into a city (Paris, medium, $20,000). From the main menu the command loads
  but leaves the menu window on top: use the menu's own entries instead (lifecycle.MAIN_MENU).
- **Main menu** is itself a modal window (640x480, depth 1). lifecycle treats it as a screen, not a dialog.
- **Dialog contents**: every GZWIND window has +0x14 rect (client coords), +0x34 -> std::list of child windows
  {next, prev, child*}, +0x44 its text (cRZString). Classes by GZWIND RVA of the vtable: 0x2B190 button,
  0x2BBD0 static text, 0x2BF10 rich text (text at +0xA8, not +0x44), 0x2C710 list box (list interface at +0xA4,
  vtable GZWIND+0x2C64C, rows = std::list at iface+4 {next, prev, cRZString, .., +0x1C id}), 0x2AEB4 slider
  (+0xAC min, +0xB0 max, +0xB4 value, +0xB8 thumb travel px, +0xBC thumb offset from the top = max), 0x2A8CC
  edit field. Option buttons (radio) have no text; their label is the static text right next to them. The root
  of all windows is *(wm+0x38). Some windows (Neighbors Map) reopen themselves after EndModal(cancel); their
  title-bar X (rightmost button inside the title bar) closes them for good.
- **Tool operations that ask questions**: building a line to the map edge asks "Do you want to make a connection
  to your neighbor for $2,000?"; a road over water asks "Bridge construction costs will be $500...". The tool's
  handler runs a nested modal loop, so OP_TOOL_POINTS now has a defer flag (runs from the message loop); the
  server returns {"pending": ...} with the dialog and finishes the action when close_dialog answers it.
  The bridge refuses re-entrant calls (-99) while a non-deferred call is inside a modal loop; IAT slots are found
  by import name so a fresh bridge can hook over a busy one, and an old bridge is only unloaded when idle.
- **Pipes**: the game refuses pipes along some terrain (row 26 next to a slope bump in the e2e city) - a real
  mouse drag also costs 0. build() reports cost 0 with a note.
- **Neighbors** (re/agents/deals/REPORT.md): records N+0x50+i*0x54 (N = *(city+0xF4)); neighbor i borders
  x=0 / y=0 / x=max / y=max for i = 0..3 = Neighbors Map quadrants NE / NW / SW / SE (verified: Berlin's
  Upper Marazan deal shows in SW; the e2e power line to x=127 counts for neighbor 2). Connection counts at
  record+0x34..+0x48. Deal objects: active list *(N+0x24), proposals *(N+0x28). Accept via PM answer
  (0x1002096A) moved Madrid's water offer to the active list dated today; cancel_deal (answer 233-238 with 1)
  removed it and set N+0x1A8 = 4,400 penalty due.
- **Discuss Deal** (Neighbors Map, button rel (341,326)) opens the terms petition window (233-238) for the selected
  neighbor's deal: rich text with the real numbers, options Cancel Deal / Keep Deal / Impact Analysis.
- **Advisors**: advice list *(advisor+0x84), entries with +0x13 == 0 are shown; message id +4 indexes the advisor
  text tables. Matches the ticker's advisor headlines. Reading memory has no side effects (asking the advisor
  object for text marks it read).
- **Scenarios**: s = *(city+0x100); running byte +9; goals tree *(s+0x8C0) (node +0x10 id, +0x18 met, +0x1C/+0x20
  text); months elapsed from +0x5C..+0x6C; byte +0x9A9 = 0 for "cannot be paused" scenarios (Rags To Riches:
  speed fixed at 3, unpaused). advance_time steps the scenario clock (+0x58, minutes) and stops at the script's
  dialogs (e.g. month 1 "Crime is rampant", button "Scenario Status").
- **Budget is settled once a year** (month-end code adds income/expenses to funds only when month == 11 ->
  1 January): mid-year funds stay flat while the YTD ledgers move (watchpoint on funds: 0 writes in a month).
- **Terrain editor** (new city, before Accept): panel "Terrain Edit" under the root window. Sliders hills/water/
  trees (0..255). Pick Features preview (SIMUI class +0xAAB14): +0xA8 centre feature 0 none, 1 lake, 2 river
  NW-SE, 3 river SW-NE, 4 mountain (click its centre to cycle); clicking an edge strip toggles a coast (preview
  rel NW (31,16), NE (93,16), SE (87,44), SW (37,44); state read from the preview's blue pixels). Changes apply on
  Re-Generate. Coast NW = map edge y=0, NE = x=0, SW = x=max, SE = y=max. Editor tools (lower, raise, level,
  trees, water, bulldoze) work by tile coordinates and charge the editor's $1,000,000,000 pool; Accept resets
  funds to the difficulty's amount.
- **Ticker entries** carry a sequence number at entry+4 (monotonic): game_events / advance_time report new ones.

## Verified, round 3 (2026-10-07)
- **Year-end Budget window**: budget+0x13 is the Auto Budget flag the year-end code tests (SIMMISC 0x100083B3:
  == 0 or funds < 0 -> post 0x25F0A91 {MenuItem 0x10008001} = the Budget window on 1 January). city+0x1F1 is the
  option itself (get vt[0x90], set vt[0x94]); the setter's message 0x6569DE54 syncs budget+0x13 on the next
  engine turn. A loaded save can carry city+0x1F1 = 0 with budget+0x13 = 1 until the option is touched.
- **advance_days** now steps to a target JDN, drains days left queued by an interrupted call first, and steps
  the 1st of each month alone (the game's monthly/yearly windows open there): exact end dates across auto-closed
  Budget windows (1911-01-21 + 2 years -> 1913-01-21).
- **Menu commands take three params**: MenuItem.INI COMM lines carry p1..p3; City Properties 0x855A2DC4 opens with
  [0, 0, 0] (with none it did nothing), like Load [kind, 0, 0].
- **City Options** window = New City Options layout (639x368): City Name / Mayor Name edit fields (GZWIND class
  0x2A8CC, text cRZString at +0xC4), Auto Budget / Disasters check boxes, OK at rel (610, 346).
- **New City Options check boxes are not read from pixels any more**: the city's Disasters (+0x1F2, set vt[0x9C])
  and Auto Budget (+0x1F1, set vt[0x94]) are applied with the game's setters after the terrain is accepted
  (Accept re-applies the dialog's boxes, so setting them in the editor is overwritten), then read back.
- **Soak**: Berlin 28 simulated years, 5.2-6.0 s per year, handles ~793 flat, game private bytes +1 MB/year.
- Residential R = *(city+0xE4): float[90] at +0x354 sums to 1.0 (age distribution, fractions); +0x84 / +0x4BC
  per-age education / health values (small e2e city).

## Verified, round 4 (2026-10-07): data layers, buildings, demographics (all memory-only)
Reports: re/agents/layers, re/agents/buildings, re/agents/uistate (REPORT.md each). Checked live in Berlin:
- Pollution grid *(P-4) (P = *(city+0xD4)), shift 1, u32: air = bits 15..29 (non-zero average 2051 = the city's
  air average 2058), water = bits 0..14, radiation bit 31; bit 30 seen on 975 cells (meaning open).
- Garbage grid *(P+0x128+0xC), u16 per tile: landfill contents (0..32767), bit 15 set on exactly the landfill
  tiles (720 = *(P+0x468), the landfill tile count). Garbage flows: produced P+0x154 = landfill P+0x184 +
  recycled P+0x16C (x 0.1 t/year).
- Power bits *(*(city+0xB8)-0x14+0xC): rows[x][y>>5]; all 23,836 zoned tiles and power lines powered.
- Water bits *(*(city+0xBC)+0x68) (watered) and +0x70 (pipes) are row-major by y (400/400 pipe occupants hit).
- Traffic grids *(T+0x5C) u16 flags, +0x60/+0x64/+0x68 u8 densities (T = *(city+0xAC)); strike byte T+0x108 = 2.
- Aura: SIMMISC main found by vtable in the layer vector city+0x94..0x98; shift 2, signed bytes, city byte 68.
- Buildings: occupant-scan records now carry the agent state dword (+0x14): 1 working, 2 abandoned, 4 under
  construction, 8 destroyed. Residents = footprint x SC3ValveLayer.ini supply of valve 3000 for working
  buildings: sum 793,960 vs the game's 794,278. Coal plant P = O-0x30: usage 4962, capacity 6000/6000, built
  2048-02-10, life 912 months, aging from 730. Water tower W = O+0x24: 600/598/202.
- Demographics: unemployment formula gives 8% = the game's Unemployment graph; schools 155,982 students for
  120,000 desks (grade D).
- Terrain editor parameters read from the controller TE = *(*(SC3U 0x4FAA30)+0x28) (feature +0xC, coast mask
  +0x10, hills/water/trees +0x12..+0x14); sliders set with their own SetValue (iface vt[0x14]). No pixel reads
  remain anywhere in the server (screenshot is only for viewing).

## Determinism (investigated 2026-10-07; ACHIEVED with start_trial - see the resolution at the end)
- Same save + same actions + same advance_time -> different results (mcp_e2e, 1 year: population 4209..4531).
- Randomness sources found: (1) LCG objects {state, seed, 0} embedded in many simulator objects, Next =
  state*0x41C64E6D+0x3039, Seed(-1) = timeGetTime() (pattern `8B 44 24 04 56 83 F8 FF 8B F1 75 06 FF 15 <IAT>` in
  21 modules); (2) 49 global LCG objects created at DLL load (sc3k_mcp/data/global_rngs.json, found from
  constructor/Next call sites, validated live: seed ~ uptime at game start); (3) MSVCRT rand() in SIMRCI, SIMSERV,
  SIMECO, SIMDSTR, SimTransit (per-thread state, never srand-ed; the engine thread is recreated per city load).
- Research hook (bridge OP_RNG, game.set_random_seed): redirects Seed(-1) to a seeded sequence, hooks rand() off the
  UI thread, resets the global generators. Seed draws then match exactly between runs (62 at load, 231/year) and
  rand() counts nearly match, but results still differ - also in fresh game processes.
- The engine has wall-clock-dependent work: with an empty queue it self-posts "type 0" throttle messages
  (SIMCITY 0x1000155B: queue <= 3 or > 500 ms -> city vt[0x22C] BeginStep (clock pause, +0x148++), type 0 ->
  vt[0x230] EndStep). Slower stepping drew 2011 vs ~1330 values from SimTransit's global generator for the same 30
  days. Engine message types: 3/4 -> broadcast kinds 0/1, 5 day (kind 2), 6 week (kind 3), 7 month (kind 4),
  8 year (kind 5); broadcasts call 0x1000155B / the pause wait between listeners.
- First divergence (with every generator seeded): the first weekly traffic pass (SimTransit handler 0x100097B9,
  kind-3 listener): one run takes the Next(100) >= threshold branch, the other not. Remaining suspects: traffic
  agents registered by view/UI timing, or a dynamic threshold ([global+0xC9]).
- Stepping entirely inside the UI thread (tried, removed): 8x faster on the tiny city but 6x slower on Berlin and
  not reproducible either.
- Never put a vtable call tracer on cross-thread objects (the engine queue: game crashed) and never use read
  ("rw") hardware watchpoints (crashed twice); write watchpoints with call chains are fine.
Practical consequence: compare strategies over several runs (save_city once, then load_city + advance_time per
trial) and look at averages; fast stepping also runs fewer background traffic passes per game day than slow
real-time play.

### Determinism - resolution (2026-10-07)
- Draw tracing (bridge OP_RNG 3/4: every module's generator Next() hooked via a 5-byte jump to a logging stub;
  live/t8g_draws.py) found the first divergence: identical generator state, but the weekly traffic handler
  (SimTransit 0x100099F1) processed a different traffic agent first. Two causes:
  1. 7-day chunks: AdvanceDay x7 runs on the UI thread while the engine processes; the traffic handler reads the
     clock's date (city vt[0x1E4]) to pick the agents of the week, so how far the clock ran ahead was a race
     (77 vs 341 agent actions in the same 6 days). advance_days now steps one day at a time (chunk=1).
  2. SimTransit's 16 traffic agents (vtable +0x1A594, at the same addresses every load) get their types
     (+0x4: 3, 4, 11, 12, 15, 16, 17) in a different order after each load in the same process: state that
     survives city loads. A fresh game process assigns them consistently.
  Plus the UI thread's rand() during a load (24,573 calls, e.g. SimTransit setting up) is now seeded too (the bridge
  resets that sequence when the city global *(STRTSIM+0x32C9C) becomes 0 at load).
- Recipe = start_trial: quit, launch, set_random_seed(seed), load. Verified: 3 fresh runs x 365 days identical
  (hash 5727c0652e0c), a build in between replays identically, another seed differs. In the same process runs
  still differ (cause 2).

### Round 5 (2026-10-07): ledgers, ordinance amounts, stations
- Budget ledgers B=[city+0xC4]: int64[12] by calendar month (index month-1; later months still hold last year's
  amounts) then the YTD int64 at +0x60: +0x3A0 transit fares, +0x470 neighbor deal income, +0x408 neighbor deal
  expense, +0x4E8 business deals, +0x2D0 ordinance income, +0x268 ordinance expense, +0x338 other income;
  +0x588 bond payments YTD. Verified in Berlin on 9 Feb 2067: income_ytd 12,695 = taxes 10,324 + fares 100 +
  neighbor deals 1,071 + business 650 + ordinances 550; expense_ytd 12,438 = departments 8,642 + ordinances 3,796.
- Ordinances: record +0x20 = monthly amount (+ income / - cost) of enacted ones; totals O+0x68 income 550,
  O+0x6C cost 3,796 in Berlin (= the ledgers).
- Station passengers/day (Query): the traffic density byte T+0x60 at the station tile x 4.3 (max over the
  footprint); 0 while transit workers strike (T+0x108 == 1). Berlin: 53 subway (18,376/day), 27 rail (9,945),
  6 subway-rail (3,491). Station categories 12210 bus, 12230 rail, 12360 subway, 12361 subway-rail.

### Round 6 (2026-10-07): features and fields reports verified live (Berlin unless noted)
- Ordinances: O vt[0x30](id) (SIMMISC 0x1001ABDD) = the Ordinances window's monthly estimate for every ordinance,
  enacted or not; for the 20 enacted ones it equals record+0x20 and sums to O+0x68 (550) / O+0x6C (3,796).
- Advisor mood = sum(AdvisorMoods.INI mood of each visible message, 0 if unlisted) // count, 3 when empty
  (data/advisor_moods.json, 232 ids). Berlin: utilities 2, budget 1, planner 1, environment 2, health/education 3,
  public safety 3, transportation 1.
- Disasters: DM = *(city+0xD0); trigger_disaster("fire") -> disaster_mode (city+0x38 bit 0) on, one active instance
  in the tree *(DM+0x20) (keys at node+0x10), inst vt[0x20] = 0x621CDA33 fire, vt[0x10](&x,&y) = the burning
  residential tile (moved 204,224 -> 202,226 as it spread), vt[0x30]/vt[0x34] 0 (nothing destroyed);
  dispatch("fire", x, y) put it out within one 5 s real-time slice; disaster mode then off.
- Preferences PR = *(*(SC3U 0x4FA86C)+0xF8) (vtable 0x4CFDAC checked): +0x6C 3D sound, +0x6D music, +0x70 music
  volume 0..1024, +0x74/+0x78 sound effects on/volume, +0x7C/+0x80 ambient on/volume, +0x84 auto go to disasters,
  +0x85/+0x86 new-city auto budget/disasters, +0x94 traffic visible 0..3, +0x98 sims visible 0..2, +0x9C other
  animations, +0xA0 tips. Preferences window (COMM 0xC3001401) controls have absolute rects; clicking check boxes /
  radio items, slider iface (+0xA4) vt[0x14](0..1024) and OK 0x2F95AD8 applies them (verified set + restore by
  reading PR). Traffic/sims/animations on or off: no measurable effect on advance_time speed (~77 days/s).
- Density data map: V = *(*(city+0xC4)+0x30); grid = *(*(V+0x38)+0xC) u8 [x][y]; a 1x1 working ResLow building
  reads 23 = its residents. Residential tiles mean 89, max 157; whole map max 255.
- Garbage scale: SIMECO float 0x10020274 read live = 0.1 (0x3DCCCCCD), so tons = units x 0.1 (the fields report's
  0.125 is wrong). Landfill valve V = *(P+0x13C): V+0x10 free units; Berlin 43% used, 1,359,693 t free of
  2,359,224 t (720 tiles); recycled fraction float P+0x148 = 0.43; imported P+0x15C 142,869 t/yr.
- Approval: aura main (SIMMISC vtable 0x3C250) s8 +0xA4 = 68 in Berlin; graphs()["Approval Rating"] = 195 = 68 + 127.
- Power: int[10] P+0x29C = MWh per plant type over 12 months (coal 717,480, nuclear 1,116,129, solar 63,402, wind
  9,926 - the types present); plant vt[0x4C]() = type (1 coal, 5 nuclear, 7 solar, 9 wind checked). P+0x2D0
  (10,532) and P+0x2CC (10,501) do not agree exactly; not exposed.
- Water: W+0xC0 13,718 consumers, W+0xC4 25 unwatered -> 99.8% served. Water buildings: u16 W+0xE source (2 tower).
- Transit: T+0x108 2 = normal; T+0xE4/+0xE5 = roads/transit funding 112/120 (= the budget's).
- Libraries / museums capacity R+0x67C / R+0x680: Berlin 0 libraries (the ticker complains), 7 museums = 581,000.
- advance_time(max_seconds=...) splits a run into 30-day checks and stops early with remaining_days; fresh seeded
  trials: one call, 30-day checks, and 7 forced partial calls all end with the same hash (live/t11_budget.py);
  record="week"/"month" also identical (live/t10_record.py).

### Round 7 (2026-10-07): view, snapshots, query, styles, music, speed 4 (verified live)
- GZ messages: message server = call(SC3U 0x470247); post vt[0x10](&{id,p1,p2,p3}, 0), send vt[0x0C](&msg) (query
  answers come back in p1..p3: {0x235EE5D4} -> zoom, rotation; {0x835EE5EB} -> centre x, y; {0x435EE5C0} -> data view
  mode, layer flags 0x7F).
- Camera: view vt[0xB0](zoom, rot, 1) - rot -1 keeps the rotation (0 resets it: center_view used to reset rotation);
  state: cam = *(view+0xB8), P = *(cam+0x158) +0x28 zoom / +0x2C rotation, centre cam+0xB0/+0xB4, lm = *(cam+0x154)
  +0xCC data-view mode / +0xD0 layer flags (bit 0 = terrain grid, 2 zones, 4 transport, 8 power lines, 0x10 trees,
  0x20 zoned buildings, 0x40 other buildings). Data views via view vt[0xB4](mode, flags, 1). Grid via renderer
  vt[0x34](1, on, 1): verified by snapshots (grid lines visible / not).
- Snapshots: post {0x2435FF70, 1|2|3}; frame window id 0x85202C0E (SC3U class, rect at +0x80, vt[0xCC](x, y) move,
  vt[0xFC] hide = what Return does first); then its DoMessage vt[0x0C](&{0x1A5D056D, 1, 1, 0}) captures + saves + closes.
  File: <game>\Albums\<city>-<id>\<city>-<Mon. d, yyyy>-<n>.jpg (sizes at 1024x768: small 480x360, medium 640x480,
  large 800x600). Rendered from the game's own buffer: works while the window is not presenting. After a save the
  game opens its "View Snapshots" album window (non-modal; closed by its title-bar X).
- The game's Query tool = command 0x0339DA69 (what view vt[0xA0](1, 0) installs; mode 1 = temp query, 2 = temp
  bulldoze - the tools report had them swapped). Clicking a tile opens the modal "Query" window; its lines are a
  std::list at (line-table widget, SIMUI class vtable 0x100AAF64)+0xC4: node {next, prev, label cRZString +8, value
  cRZString +0x1C}. Fire station: Fires 29/Month, Calls 37/Month (= the static formulas), Performance Rating Excellent
  (the static "funding/500" rating formula is wrong); police Crimes 55 / Arrests 31 (formula gave 54 / 29); jail
  Conditions Poor at 300/300 inmates (formula said Good): building_info now carries the game's own lines.
- Zones: 14 = AIRPORT (tarmac, parked airplanes), 15 = SEAPORT (cranes, cargo) - ZONE_NAMES had them swapped; fixed.
  Airport Query: Air Traffic Light, On Time Flights 98% = the formula (transit()).
- Styles: scheme manager S = *(*(SC3U 0x4FA86C)+0x108); SetScheme S vt[0x18](landscape, trees, buildings, 0) took 0.5 s;
  European buildings + desert landscape visible in a snapshot; reverted. Description: city vt[0x84](fake cRZString
  {SIMCITY+0x1378C, begin, end, end, 1}) writes city+0x70 (read back OK). 15 user-made (BAT) buildings available in
  this install, no replacements set.
- Music: 17 songs via audio manager (SIMUI 0x1008E95F) vt[0x14](0x3F7) reset, vt[0x14](0x3F8, &id, &cRZString) per
  song (the name must be a constructed cRZString: SIMUI 0x10005EB6 - a plain pointer crashed, caught by the bridge);
  enabled = PR vt[0x8C](id); toggle = audio vt[0x14](0x3F4, id, on) + PR vt[0x90](id, on). Verified off and on.
- Speed 4 (african swallow): 31 game days in 5 s real time vs 8 at speed 3.
- Building replacements (re/agents/replace/REPORT.md): user-made buildings = S vt[0x9C] collection (15 here: The
  Joneses 1x1 ... Longview Park 4x4, names / architects / sizes as the static list); 338 replaceable defaults (set
  S+0xB0; prototypes in OM+0x1C, OM = *(*(app+0xDC)+0x10)); categories via GM vt[0x24](3000|5000|8000, type) and
  S vt[0x94] (rewards): residential 1x1 = 60 = the manager's default "60 of 338". S vt[0xA8](&{0x207EDC0E, 0x57E, id},
  &{0x856CD19A, 0xBA1DBF1E, inst}) replaced Squat St. with The Joneses: the game's Query then titled the house "The
  Joneses"; S vt[0xAC] reverted; S vt[0xBC] clears. Saved in the .sc3 (record {0x99F47014, 0x79F4702D}; repl.py read it
  from Cities\mcp_repl_test.sc3) and S vt[0xB8](cRZString path, vtable SIMINIT+0x2F230) imported it back.
