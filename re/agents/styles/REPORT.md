# City Options styles, user-made buildings, description, speed 4, grid / toolbars (static RE by subagent; saved by main)

Module preferred VAs (exe 0x400000, DLLs 0x10000000), thiscall, UI thread. app = *(SC3U 0x4FA86C); appIface = app+0x30
(= *(SIMUI 0x100BFC8C) = *(SIMSPR 0x10072F24)); city = *(STRTSIM 0x10032C9C); S = city-scheme manager; dlg = City
Options window object (vtable SIMUI 0x100AA8E8); view / r (camera-renderer) / lm (layer manager). re/agents/styles/
check.py re-checks 20 facts (all pass). 4 of 5 questions answered; Hide/Show Toolbars OPEN; Zone Demand has no own
recipe (value = city.demand()).

## 1. Landscape / Trees / Buildings styles
S = *(app+0x108) = appIface vt[0x80]() (CONFIRMED): app-global, not per city object. SIMINIT class GZCOM 0x23D9722C,
IID 0x43D9722C, 0xBC bytes, vtable SIMINIT 0x1002F528, ctor 0x100050CD. Init vt[0xC] 0x1000583E parses
\Sys\SC3CityScheme.ini [LandScapes] / [FloraSets] / [BuildingSets] / [ReplaceableBuildings] (line parsers 0x10004B54,
0x100048E8, 0x1000467C, 0x10004E42). "0x85535958,0x1xxx" pairs are image keys in Res\UI\Shared\85535958_CitySchemeUI.ixf.
The buttons have no text and no tooltips (row builder 0x1005B0D7); names below from decoding the icons / GAME_UI.DAT
previews (icons.py, sprite.py).

Landscape (buttons 0xE558C351..55; palette = instance in Res\Dirt\PALETTE\455A72B1_LandPalettes.IXF):
index 0 id 0 (icon 0x1003, preview 0x3FC40000, palette 1) default temperate, green, olive hills; 1 0xC55A6D62 (0x1002,
0x3FC30000, 3) snow / winter; 2 0xC55A6D84 (0x1001, 0x3FC20000, 2) red-brown desert; 3 0x655B8076 (0x1004, 0x3FC10000,
5) golden / dry; 4 0xE55B8055 (0x1005, 0x3FC00000, 4) lush bright green (tropical).
Trees (0xE558C356..5A): 0 id 0 (0x2003, 0x3FBE0000) default mixed; 1 0xC55A6D62 (0x2002, 0x3FBC0000) desert
(Joshua-tree style); 2 0xC55A6D84 (0x2001, 0x3FBB0000) deciduous; 3 0x79EF435A (0x2005, 0x3FC70000) palms; 4 0x39EDF62B
(0x2004, 0x3FC60000) tall conifers. Loaded from Res\Sprites\FloraSets\<id>\*.DAT.
Buildings (0xE558C35B..5D): 0 id 0 (0x3001, 0x3FBF0000) North American (built-in sprites); 1 0xE523F3FB (0x3002,
0x3FBD0000) European (BuildingSets\e523f3fb\BST_0004.dat); 2 0x6523F3D5 (0x3003, 0x3FBA0000) Asian
(BuildingSets\6523f3d5\MBE_0015.dat).
Button order = order of S's record lists (LIKELY INI order); dlg+0x108[i] / +0x10C[i] / +0x110[i] map index -> id.

S layout: +0x18 current landscape id (CONFIRMED); +0x2C current tree set id (valid when byte +0x34 loaded); +0x50
current building set id (valid when byte +0x58 loaded); +0x1C / +0x30 / +0x54 fallback ids (always 0); +0x20..+0x24
landscape records (0x28 each: +0 id, +4/+8 icon key, +0xC/+0x10 palette group/instance, +0x14/+0x18 preview,
+0x1C/+0x20/+0x24 INI fields 7-9 (OPEN; vt[0x40]/[0x44]/[0x3C])); +0x38..+0x3C tree-set records (0x20: +0 id, +4/+8
icon, +0xC/+0x10 preview 1, +0x14/+0x18 preview 2, +0x1C last INI field); +0x5C..+0x60 building-set records (0x20);
+0x80..+0x84 user-made building keys (0xC each, LIKELY); +0x8C building replacement map (LIKELY); +0x9C PlugIn scanner
(class 0x852BEAA1, LIKELY).
S vtable: vt[0x18] SetScheme(landscape, trees, buildings, showProgress) = 0x10006589; vt[0x20]/[0x48]/[0x64] get
current into &id (bool); counts vt[0x28]/[0x50]/[0x6C]; lists (buf, max, &n) vt[0x2C]/[0x54]/[0x70]; icon keys
vt[0x30]/[0x58]/[0x74]; previews vt[0x38]/[0x5C]/[0x78]; landscape palette vt[0x34].

Apply (CONFIRMED): style clicks -> handler 0x1005E3A1 routes by id range to 0x1005E34A (landscape) / 0x1005DFE5
(trees) / 0x1005B68A (buildings): only the dialog's selection dlg+0x114/+0x118/+0x11C, previews, checked button. OK
(0x2552483D) -> apply 0x1005EB40 (in City Options mode also reads the description), writes the PR new-city defaults
+0x85/+0x86 and +0x88/+0x8C/+0x90 only if changed since opening (0x1005EE78). After EndModal(1), command 0x10011BC5 calls
S->vt[0x18](dlg+0x114, +0x118, +0x11C, mode == 0); in City Options mode (0) then the city setters: name vt[0x7C], mayor
vt[0x8C], description vt[0x84], auto budget vt[0x94], disasters vt[0x9C].
Applied immediately in a running city: SetScheme takes the city lock itself (slots 141/142 via 0x100298B6); showProgress
1 shows "Change in Progress" (text 0x41F2625:0x2D2). Landscape: sends {0xE5464350, id}; SIMDIRT 0x10016C45 stores the id,
reloads the palette, repaints the terrain (posts 0x45462FD2) (CONFIRMED). Trees: unload old, load FloraSets\%08lX\*.DAT
(0x100068A7) (CONFIRMED). Buildings: unload old, load BuildingSets\%08lX\*.DAT (0x1000641B; id 0 = built-in), re-apply
user-made replacements (CONFIRMED). Existing buildings re-skinned at once, sets purely cosmetic: LIKELY.
Saved per city: loader SIMINIT 0x10009E1F (from 0x10008BF8) reads save record {0x0525A6B9, 0x4525A6E2, 1} = 3 dwords
buildings, trees, landscape, then SetScheme(..., 0); no record -> 0/0/0. Writer: the city save (see the replace
report section 4); saved with the city CONFIRMED live (LIVE_FACTS round 8).
Recipes: read S = *(*(SC3U 0x4FA86C)+0x108); landscape *(S+0x18); trees *(S+0x34) ? *(S+0x2C) : 0; buildings *(S+0x58) ?
*(S+0x50) : 0. List: record lists S+0x20 (stride 0x28), S+0x38 (0x20), S+0x5C (0x20), id at +0. Set:
call(SIMINIT 0x10006589, [landscape, trees, buildings, show], this=S) with current values for unchanged ones; no outer
city lock; sets are 13-26 MB (use deferred / long timeout); PR defaults not updated. Or via the window: open COMM
0x855A2DC4 [0,0,0] deferred, call(SIMUI 0x1005E3A1, [buttonId], this=dlg) per style, then with 0x2552483D (OK); ranges
dlg+0xF4 (last landscape id), +0xF8/+0xFC (trees first/last), +0x100/+0x104 (buildings first/last).

## 2. User-Made Buildings: Select, and the two folders
Select (0x2552485A) runs COMM 0x75942963 (SIMUI ctor 0x10012448, execute 0x1001B3FA): the modal "Building Replacement
Manager" (text 0x41F2625:0x135) (CONFIRMED). GZCOM 0xA2A79FD0 / IID 0x5386D516; model 0x1001B85E (0x64 bytes); strings
0x130..0x13A: Replace, Revert, Architect:, Size:, Import Set, Clear Set, Filters:, "%x% of %y% Buildings Selected", Name:,
Type:. City Options hides itself while it is open (dlg vt[0xF4](1,0)); on OK (1) 0x1001B38D calls
S->vt[0xA4](row->vt[0x14](), choice) per changed row.
Manages (LIKELY): replacing default buildings listed in [ReplaceableBuildings] (~300; occupant keys {0x207EDC0E, 0x57E,
occupantId} + name) with user-made BAT buildings from Apps\BARender\*.DAT (BAT.DAT), scanned by S vt[0x80] 0x10005AE2;
keys in S+0x80 as {0x856CD19A, group, instance} (count vt[0x88]); mapping std::map S+0x8C (replacement key at
node+0x1C..+0x24); setters vt[0xA4](key, building), vt[0xA8](key, id), revert vt[0xAC](key); saved per city as record
{0x99F47014, 0x79F4702D} via vt[0xB0](db, isLoad).
<game>\Buildings\*.bld are Building Architect (Baapp.exe) projects; only buildings rendered into a BARender DAT appear.
Text table 0x541F07DB (SC3PStringsUI "Load Building Set", .scs, BuildingSet.cfg) is not referenced by the exe/DLLs
(unused or BAT-side; SIMBABLD.DLL holds "*.scs" / "BuildingSets" strings - OPEN). 6523f3d5 / e523f3fb = the Asian /
European building styles (folder name = set id).
Recipes: sets S+0x5C list (0, 0xE523F3FB, 0x6523F3D5); current S+0x50; choose SetScheme(*(S+0x18), trees, id, 1).
User-made buildings: count (*(S+0x84) - *(S+0x80)) / 0xC; map at S+0x8C = current replacements.

## 3. City description
city+0x70 cRZString (0x14: vtable SIMCITY 0x1001378C, begin, end, cap, refcount); text *(city+0x74)..*(city+0x78)
(CONFIRMED). Getter vt[0x80] -> &city+0x70; setter vt[0x84](cIGZString*) = 0x100070C0 (copies via s->vt[0x18]() data and
vt[0x1C]() length) (CONFIRMED). Name +0x48 (vt[0x78]/[0x7C]), mayor +0x5C (vt[0x88]/[0x8C]); both setters use copy
routine 0x10005116. (LIVE_FACTS listed mayor +0x58 / "another string" +0x68: the code says mayor +0x5C, description +0x70.)
Window: in City Options mode only, the builder copies the description into dlg+0x148 and shows it in multi-line edit
0x25524843 (GZCOM 0x231A1C58, iface 0x231A1C57); OK reads it back (iface vt[0x8C]) and calls city vt[0x84] - editable
there (LIKELY). New City Options ignores it.
Recipes: read rz_string(city+0x70). Write without the window: {SIMCITY+0x1378C, p, p+len, p+len, 1} + text in bridge
memory, then city vt[0x84](&fake) (same for name vt[0x7C], mayor vt[0x8C]).

## 4. Speed 4 ("African Swallow")
A normal player speed: the 4th (rightmost) of the 4 status-bar speed boxes, no cheat (CONFIRMED). Control (SIMUI message
handler 0x10026144, click 0x1002624F): 4 hit rects at ctrl+0xA8 (0x10 each), box 0..3 -> speed 1..4 (Turtle, Llama,
Cheetah, African Swallow; GUI 0x66..0x69); a click posts {0xC2684065, speed} to the city; lit box byte ctrl+0xA6 =
speed-1 (synced from 0xC2684066). Disabled in disaster mode (0xE31E2463 sets ctrl+0xA5; 0x231E2493 / 0x632ABA43
re-enable) and by a scenario lock (0x54E23EE9 arg 0 -> ctrl+0x114).
SetSpeed(4) is safe: SetSpeed 0x10005ADA (city vt[0x204]) accepts 1..4 outside disaster mode (0 or > 4 ignored), sets
+0x14C = +0x150 = s and the clock rate (0..4: 120 / 10080 / 43200 / 129600 / 525600; speed 4 ~0.16 s per game day); the
engine pauses its clock when its queue backs up.
Disaster mode runs at speed 0: city vt[0x44](1) (0x100072D8, city+0x38 bit 0) saves +0x14C into +0x150, SetSpeed(0)
(rate 120, ~12 real minutes per game day), and resumes the sim if it was paused; meanwhile SetSpeed(s) only stores the
request in +0x150 (capped at 4), GetSpeed returns +0x150; at the end SetSpeed(+0x150) restores the speed.
Hotkeys: no speed keys; keys 1-5 -> view vt[0xB0](0..4, -1, 1) (zoom, LIKELY).

## 5. Grid, toolbars, Layer Views, Zone Demand
Terrain grid = bit 0 of lm+0xD0 (CONFIRMED): view = *(app+0x40) (= appIface vt[0x74]()); r = *(view+0xB8) (SIMSPR
0x10063390); lm = *(r+0x154) (SIMSPR 0x100630E4). Read: *(lm+0xD0) & 1. Toggle as the game: r->vt[0x34](1, on, 1)
(SIMSPR 0x1001C409 -> lm SetFlags 0x10018156, then redraw; redraw must be 1 - with 0 the flags are not written).
Also: G hotkey = view command 63 (view->vt[0x80](63, 0, 0), 0x10049A80) or post {0x22CCA9D3, 63, 0, 0}; the Layer Views
window button 0x2AFB uses r vt[0x30](1) to read and vt[0x34] to set.
Layer Views (0xA7): toolbar button (class 0x22ECFC47, built at SIMUI 0x10050078) opens the City Layer Views panel (setup
0x100410D3, clicks 0x10040E14): 0x2904 / 0x2905 / 0x2906 above-ground / underground choice (0x10041579); 0xBB9..0xBBF
data-view items (Crime .. Traffic, text 0x29541F4:0x277..); 0x2AF8 Default View (0x10041671); 0x2AF9 Apply (0x1004163D);
0x2AFB grid toggle; 0x2AFA and 0x42B7C353 close.
Hide/Show Toolbars (0xA6/0xA9): OPEN (SIMUI tab-button class vtable 0x100A9F0C, ctor 0x1004ED85; init 0x1004EFFA loads
both tooltips into +0xD4 / +0xE8, chosen by +0xD0 == 1, only written in the ctor; the hide action/state not found).
Zone Demand (0xE): OPEN, low value (tooltip from a UI layout resource; value = city.demand()).

Helpers (re/agents/styles/): d.py (dis / xref / function start), vtd.py (vtable dump + first instructions), check.py,
icons.py (RefPack decoder; City Options icons -> PNG), sprite.py (GAME_UI.DAT sprites -> PNG), s_users3.py (readers of
S), viewcmd.py (city view command switch / hotkey actions).

## Live questions
1. Button order vs S lists (dlg+0x108/+0x10C/+0x110). 2. Does a building-set change re-skin and rename existing
buildings; does a landscape change repaint at once? 3. SetScheme from the bridge (show 0/1): duration, nested modal
loop? 4. Save/reload and compare S+0x18/+0x2C/+0x50 (writer not found). 5. Is the description editable; does the
fake-string vt[0x84] call work? 6. Landscape INI fields 7-9. 7. Toolbar hide action/state. 8. Keys 1-5 = zoom?
