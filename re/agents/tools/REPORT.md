# TOOLS & UI (static RE by subagent; saved by main). Addresses `MODULE preferred-VA`.
Helper scripts in this folder: scan.py, d.py, cmdtab.py, ixf.py, txt.py, budgetsites.py, syspak.txt.

## A. Menu items, commands, messages (CONFIRMED)
- Parser SIMUI 0x100165AE: menu item +0x45 = 1 COMM / 2 PMSG / 3 SMSG (0 NONE); +0x48 id; +0x4C/+0x50/+0x54 p1..p3
  (keywords at SIMUI 0x100BF878/0x100BF860/0x100BF848/0x100BF890).
- Execute on click SIMUI 0x10016329 (this = item):
  - COMM (0x100163AF): command server srv->vt[0x0C](id, 0x006856F7, &cmd); three uint32 variants (p1..p3) via
    cmd->vt[0x0C](v); cmd->vt[0x2C]() executes; cmd->vt[0x08]() releases.
  - PMSG (0x10016380): msgSrv->vt[0x10](&msg, 0) posts {id, p1, p2, 0} (16 bytes).
  - SMSG (0x10016352): msgSrv->vt[0x0C](&msg) sends synchronously.
- Message server = *(SIMUI 0x100BFA9C) (getter 0x1008500D) = *(SC3U.exe 0x4FAC70) (vtable GZServiceD 0x10014618).
  Ctrl+A hotkey = msgSrv->vt[0x10]({0x724A82D0,0,0,0}, 0) (SIMSPR 0x10049BB7).
- Command server = framework system service 0xA4B5E41F (IID 0x20685AA3), SC3U.exe ctor 0x4747E4, vtables 0x4D81C8 /
  +4 0x4D81B0; vt[0x0C] loops registered factories (0x47477B); vt[0x10] adds a factory. Per-DLL factories switch on
  the command id: SIMNTWRK 0x10010521 (road 0xC2B5DE77, highway, onramp, rail, subway, power lines, pipes); SIMRCI
  ~0x1000BB80 (zones, dezone, landfill, airport, seaport); SIMGEOM ~0x1000A8E7..0x1000B072 (ploppables, bulldoze,
  trees); SIMDIRT ~0x10017253 (terrain); SIMUI ~0x10011F10 (pickers, windows); SC3U 0x4114D0 (disasters, dispatch,
  quit); SIMINIT (save, new city, city properties). A tool's Execute installs it in the city view.

## 1. Tool ids (= SYS.PAK [SC3MenuItemInfo])
Res light/med/dense 0x42E88586/0x02E88915/0xA2E8893B; Com 0x02E88949/0xA2E8895A/0x02E88968; Ind 0xC2E8898F/
0xA2E8899D/0x02E889AA; Dezone 0x82E88C9C; Landfill 0xC2E889B6; Seaport 0x02E889C4; Airport 0xE2E889D4; Road 0xC2B5DE77;
Highway 0x42B5DE86; Onramp 0x02B5DEBB; Rail 0x42B5DE98; Subway 0xC2B5DEA6; Power lines 0x42C2F8BF; Pipes 0x22C2F8C5;
Bus stop 0x02FF04FE; Train station 0x22FF058F; Subway station 0x62FF059B; Rail-to-subway 0x22FF0521; Police
0x42FF052F; Jail 0x22FF053F; Fire 0x22FF054C; Hospital 0xE2FF0555; School 0xC2FF0563; College 0xC2FF0571; Library
0xC2FF057A; Museum 0x62FF0585; Small park 0x02FF05AA; Big park 0x82FF05B7; Marina 0x42FF05C2; Zoo 0x22FF05CA; Baseball
0x62FF05D1; Playground 0xC2FF05E0; Pond 0x22FF05EA; Fountain 0x22FF05F3; Bulldoze 0xE3166801; Trees 0x4253EC3F;
Water 0x02E763C1; Raise 0x825AD7F6; Lower 0xC25AD94F; Level 0x825AD954; Building picker 0xE2ED3560 with p1 = power
0x62E925A2 / water 0xE2E92527 / garbage 0xC2F291A9 / landmarks 0x22E92581 / rewards 0x62E92553 (opens a chooser;
chosen -> placement tool not traced). Highway/subway/bus stop gated by tech: city->vt[0x1AC]()->vt[0x0C](4/1/2).
No toll booth / tunnel tool ids in menu data.

## 2. City view, current tool, click -> placement
Roots (CONFIRMED): iface = *(SIMSPR 0x10072F24) (= SIMNTWRK 0x10032528; vtable SC3U 0x4CF59C, app object +0x30);
city = iface vt slot 0x18; **view = iface vt slot 0x74** ([iface+0x10]). Command server: SC3U 0x406E0C (thiscall,
this = &holder) AddRef'd server into holder; SC3U 0x474908 (thiscall, this = &holder, cmdId) created command into
holder (0 if unknown).
View: SIMSPR vtable 0x10067894 (msg target iface +4 0x100676AC), ctor 0x100484C2, size 0x238. +0x0B8 camera
(vt[0x8C](sx, sy, &out{x,z,y}, 0) screen -> world, world = tile*256); +0x104/+0x108 default/current cursor;
+0x204/+0x208 last mouse x/y; +0x220 mode (-1/0 none, 1 temp bulldoze, 2 temp query, 4 tool installed); +0x224/
+0x22C saved mode/tool; **+0x228 current tool** (vtable identifies it; road = SIMNTWRK 0x1002BEF8); +0x230 cmd srv.
View methods: vt[0x58](tool) set input control (0 clears = Esc) -> vt[0xA0](mode, tool) at 0x10048A2D;
vt[0x80](cmd, p1, p2) hotkey dispatcher 0x10049A80 (cmds 1..115, via GZ message 0x22CCA9D3); vt[0x20](tileX,
tileZ, 1) centre on tile; vt[0x24]/[0x28] zoom; vt[0x2C]/[0x30] rotate; vt[0xB0](layer, -1, 1) view layer.
Tool install (CONFIRMED): road Execute SIMNTWRK 0x1000E537 (this = tool+0x64) gets networks sim (city->vt[0x140]),
terrain sim (vt[0x13C]), vt[0x11C], budget (vt[0x15C]); drag helper (ctor 0x10010BE8) at tool+0x114;
0x10025825(view): tool->QI(0x22B66D3D), view->vt[0x58](tool).
Mouse path: Gonzo wndproc -> GZWIND -> view -> tool vt slots 6..12 (x, y[, keys]); slot 9 (SIMNTWRK 0x100256EE)
= button down (captures via view->vt[0x3C]); road drag points: tool->vt[0x54] (0x1000E845) ->
helper->vt[0x0C](a, b, c, &dirtyRect). Sim-level build call NOT found statically.
Budget (city+0xC4, SIMMISC 0x1003C550) CONFIRMED: vt[0x0C](lo, hi) SetFunds; vt[0x10] GetFunds (edx:eax);
**vt[0x14](u32) Spend -> 0 and no change if it would go negative**, broadcasts 0x229A8A90 on success; vt[0x18]
AddFunds; vt[0x1C] add to month expense ledger. Cost tables: SYS.PAK [BuildingPlacementCosts], [SpecialCosts].

## 3. Dialogs
MessageBoxA only for crashes/asserts (SC3U 0x461447 "Exception encountered", 0x4838FC assert, GZGraphicD
0x100127A2 fallback). Window manager = *(SC3U 0x4FAC90) (vtable GZWIND 0x1002DB80). **DoModal(win) = wm->vt[0xA0]
(win)** (GZWIND 0x10020971, CONFIRMED): **wm+0x30 current modal window; wm+0x194 modal depth**; broadcasts 0x62BA7B42
start / 0x62BA7B43 end; nested PeekMessage loop exits on Win32 message 0x700 wParam = win; returns lParam.
EndModal = wm->vt[0x44](0xD, win, result) posts 0x700 (LIKELY). Button ids: Abort 0x53018146, Cancel 0x53018147,
Ignore 0x53018148, No 0x53018149, OK 0x5301814A, Retry 0x5301814B, Yes 0x5301814C (result = button id, LIKELY).

## 4. Menus and screens
Main menu handler SC3U 0x43E858 (button ids 0x712BF5C1..C5): Load 0x610438A4, New 0xE3270FE9 (New City Options in
SIMINIT), Preferences 0xC3001401 (0x712BF5C4). Starter town / real terrain / scenario = 0x610438A4 with p1
0x63172B74 / 0x23172AF2 / 0xA42C7725; saved city p1 0x83172AD7. Options: Save 0x410438DD; Save As same + p1
0xC3172AEA; Quit 0xA10438E9; City properties 0x855A2DC4. Res\UI\*.ixf are compressed bitmaps; dialogs built in code.
Not traced: New City Options fields, terrain editor Accept (SC3StringsWindow 0x2CD), file browser.

## 5. Hotkeys (Res\Hotkeys\*.IXF; group 1 city, 2 terrain editor): `Ctrl Shift Alt VK = 0x22CCA9D3 cmd 0 0`
Zones Q/W/E res L/M/D, A/S/D com, Z/X/C ind, V dezone, Y landfill. R road, Shift+R bus stop, Alt+R highway, T rail,
Shift+T train station, Alt+T subway, Alt+Shift+T subway station. L power lines, I pipes, Ctrl+E power plants,
Ctrl+I water bldgs, Ctrl+Y garbage. P police, Alt+P jail, F fire, H hospital, K school, Alt+K college, J small park,
Alt+J big park, Ctrl+D landmarks, Ctrl+R rewards. B bulldoze, U trees, Alt+U water. Ctrl+A advisors, Ctrl+B budget,
Ctrl+O ordinances, Ctrl+M map, Ctrl+W neighbours. Esc drops tool; Space centre on cursor; G grid; Num+/- zoom;
PgDn/PgUp rotate; 1..5 view layers. '/' toggles pause (city->vt[0x214] ? vt[0x210] : vt[0x20C]); ',' slower, '.'
faster (vt[0x208] get, vt[0x204](1..4) set) LIKELY. Ctrl+S/F2 save, Ctrl+L/F3 load, Ctrl+N/F5 new, F10/Ctrl+Q quit.
Modifiers read with GetKeyState (bridge fakes it).

## 6. Bridge recipes (UI thread)
- Run a command / select a tool: h = alloc(4); SC3U 0x474908 (thiscall, this = h, cmdId); cmd = *h; per param:
  v = SC3U 0x4B4890(0x28) (operator new), SC3U 0x46F260 (thiscall, this = v, value, 3) -> uint32 variant,
  v->vt[4]() AddRef, cmd->vt[0x0C](v); ok = cmd->vt[0x2C](); release variants and cmd (vt[8]). Plain tools need no
  params (SIMUI 0x1006090E runs bulldoze with none); pickers need p1.
- PMSG/SMSG: {id, p1, p2, 0}; ms = *(SC3U 0x4FAC70); ms->vt[0x10](&m, 0) / ms->vt[0x0C](&m).
- Tool state: [view+0x220] == 4, vtable of [view+0x228]; clear view->vt[0x58](0).
- Place: select tool, synthetic drag/click in the view; centre with view->vt[0x20](tx, tz, 0); check a screen point
  with [view+0xB8]->vt[0x8C].
- Prompt: modal open when [wm+0x194] > 0; click, or wm->vt[0x44](0xD, [wm+0x30], 0x5301814A OK | 0x5301814C Yes).

## 7. Open questions (live)
1. Execute 0xC2B5DE77 with no params: [view+0x220] 0 -> 4, [view+0x228] vt SIMNTWRK 0x1002BEF8; drag; funds drop.
2. PMSG 0x724A82D0 (Meet Advisors) opens the advisor window. 3. With the tip open read [wm+0x194]/[wm+0x30]; EndModal.
4. Breakpoint SIMMISC 0x10008946 (Spend) while building road/zone/police: callers are the real placement functions.
5. [view+0xB8]->vt[0x8C] >> 8 == tile under cursor; '/' pauses.
