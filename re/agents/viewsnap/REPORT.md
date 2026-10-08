# Messages, view/camera, snapshots, Map View, airport/seaport, demographics, civic Query windows, music prefs
(static RE by subagent; saved by main)

All MODULE preferred-VA, thiscall unless noted. C = city, R = *(C+0xE4), V = view = (*(SIMSPR 0x10072F24))->vt[0x74]()
(that iface is the app iface, app+0x30), cam = *(V+0xB8). Helpers in re/agents/viewsnap/: check.py (re-verifies 22 of
the facts below - all pass), jt.py (switch-table decoder), gp.py (instruction-pair grep), camfind.py (vtables by
argument signature); dumps view_domsg.txt, view_cmd80.txt, view_setdataview.txt, snap_take.txt, snap_save.txt,
album_*.txt, airport_q*.txt, seaport_q.txt, police_q.txt.

## 1. Posting GZ messages (CONFIRMED)
Message server = framework service (service id 0x64063387, iid 0xC1085722, GZServiceD), the pointer used is the iface
at object+0x18 (vtable GZServiceD 0x10014618). Getters (cdecl, cached): SC3U 0x470247 (cache SC3U 0x4FAC70), SIMUI
0x1008500D (0x100BFA9C), SIMADV 0x10027B11 (0x1003892C), SIMSPR 0x1004FE8E (0x10072DE8) - all return the same.
Message = plain 16-byte struct {u32 id, p1, p2, p3} (no vtable).
- vt[0x0C](msg*) = 0x10003922: SEND synchronously on the caller's thread: listeners by id in map iface+0xF8, each
  listener->vt[0x0C](msg*). Query messages write answers back into the struct.
- vt[0x10](msg*, bool urgent) = 0x10003F2A: POST: copies the 16 bytes into a list node (0x10004782) -> scratch is fine.
  Queue at iface+0x70 (vtable 0x10014484): vt[0x0C] append, vt[0x10] prepend (urgent).
- vt[0x14](listener, id) AddNotification; vt[0x18](listener, id) RemoveNotification; vt[0x28](msg*, x) copies into a
  timed list at +0x110 (LIKELY delayed post).
- The posted queue is drained by the service tick (main vtable 0x10014668 slot 0x2C = 0x1000416B) from the framework
  main loop = UI thread (LIKELY).
Recipe (UI thread): ms = call(SC3U 0x470247); write {id,p1,p2,p3} to scratch; post: call(*(*ms+0x10), [scratch, 0],
this=ms); send/query: call(*(*ms+0x0C), [scratch], this=ms) then read scratch+4/+8.
Menu dispatch: menu item class SIMUI vtable 0x100A31B0 (ctor 0x10016242): +0x45 type (1 COMM, 2 PMSG, 3 SMSG; parsed
0x10016789..), +0x48 id, +0x4C/+0x50/+0x54 p1..p3. Execute = SIMUI 0x10016329: PMSG -> ms->vt[0x10]({id, p1, p2, 0}, 0)
(p3 dropped); SMSG -> ms->vt[0x0C]({id, p1, p2, 0}); COMM -> COM->vt[0x0C](id, 0x6856F7, &cmd), three uint32 variants
(operator new 0x28 + SIMUI 0x10085825(v, val, 3)) to cmd->vt[0x0C], cmd->vt[0x2C](), Release (= the bridge's
RunCommand SC3U 0x474908; the menu always passes all three params). Hotkeys (Res\Hotkeys\*.IXF) send {0x22CCA9D3, cmd,
a, b}; the view answers with V->vt[0x80](cmd, a, b) (SIMSPR 0x10049A80).

## 2. City view controls
View message handler (CONFIRMED): V+4 is the listener (vtable 0x100676AC), DoMessage SIMSPR 0x10048D7A:
- 0x635EE3C3 {mode, flags, anim} -> V->vt[0xB4](mode, flags, p3 != 0) = SIMSPR 0x10043662
- 0xA35EE145 {x, z, anim} -> V->vt[0x20] centre on tile
- 0xE35EE21F {zoom, rot, anim} -> cam->vt[0x6C](zoom, rot, anim)
- 0x44A42474 {x, z, zoom} -> centre + vt[0xB0](zoom, 0, 1)
- 0x2435FF70 {size} -> snapshot (section 3); 0x22CCA9D3 {cmd, a, b} -> vt[0x80](cmd, a, b); 0xC2A3FD82 -> vt[0xB8]
  (monthly)
Camera (class vtable SIMSPR 0x10063390; listener at cam+4, DoMessage 0x1001BFC9): synchronous query messages (send with
vt[0x0C], read p1/p2): {0x235EE5D4} -> p1 zoom, p2 rotation; {0x435EE5C0} -> p1 data-view mode, p2 layer flags (the
advisor checks p1 != 0 then posts {0x635EE3C3, 0, -1, 1}); {0x835EE5EB} -> p1/p2 centre tile x/z.
Methods: vt[0x68](&zoom,&rot) get; vt[0x6C](zoom, rot, anim) set; vt[0x60] zoom in (+1, max 4), vt[0x64] zoom out;
vt[0x70] rot = rot ? rot-1 : 3; vt[0x74] rot = (rot+1)%4; vt[0x54](x, z, anim) centre (bounds-checked; cam+0xB0 = x,
cam+0xB4 = z tiles); vt[0x58](&x,&z) get centre. Every change broadcasts 0xA36CF3D1 / 0xC35EE786.
Memory (CONFIRMED): projection P = *(cam+0x158) (vtable 0x1006250C): zoom = *(P+0x28) (0..4, 4 closest), rotation =
*(P+0x2C) (0..3); centre = *(cam+0xB0), *(cam+0xB4) (tile x, z).
View wrappers (add sound/redraw): vt[0x24](1) zoom in, vt[0x28](1) zoom out, vt[0x2C](1) = cam vt[0x70], vt[0x30](1) =
cam vt[0x74]; vt[0xB0](zoom, rot, anim) = 0x100430C4 -> cam->vt[0x6C](zoom, rot == -1 ? current rot : rot, anim):
passing 0 as the 2nd argument RESETS rotation to 0; use -1 to keep it. Hotkeys: PgDn = cmd 0x2B -> vt[0x2C]; PgUp = cmd
0x2C -> vt[0x30]; Num+/Num- = 0x29/0x2A; keys 1..5 = cmds 0x4B..0x54 -> vt[0xB0](0..4, -1, 1) (zoom). Which rotation
direction is clockwise on screen: OPEN (read P+0x2C after PgUp).
Rotation: absolute call(*(*V+0xB0), [*(P+0x28), rot, 1], this=V), or post {0xE35EE21F, zoom, rot, 1}.
Data views: V->vt[0xB4](mode, flags, anim) = 0x10043662: *(V+0xBC)->vt[0x28](mode, 0) (0x1001C34E; entering/leaving
mode 1/2 shifts the camera height by zoom*8, then lm->vt[0x18](mode, 0)), then ->vt[0x3C](flags, anim) -> lm->vt[0x24]
(broadcasts 0xE35EE78E). flags = -1 means current | 0xFE (all layers). lm = *(cam+0x154) (vtable 0x100630E4), lm+0xCC
mode, lm+0xD0 flags. Direct recipe (CONFIRMED): call(SIMSPR 0x10043662, [mode, flags, 1], this=V) or post {0x635EE3C3,
mode, flags, 1}. Layer Views panel radios (handler SIMSPR 0x1004A799): group 0x2904 (layer checkboxes) values 0x3E8 ->
4, 0x3ED -> 2, 0x3E9 -> 8, 0x3EA -> 0x10, 0x3EB -> 0x20, 0x3EC -> 0x40; group 0x2905 (underground) 2000 -> mode 1,
2001 -> mode 2; group 0x2906 (data views) 3000 aura 0xA, 3001 crime 0xB, 3002 density 0x11, 3003 power 0xC, 3004
flammability 0xD, 3005 land value 0xE, 3006 pollution 0xF, 3007 traffic 0x10. No police/fire/education/health overlay
modes in the city view (police and fire coverage exist only as SIMUI data-map windows, views 0x271E / 0x272D).

## 3. Snapshots (path CONFIRMED, folder/name LIKELY)
PMSG {0x2435FF70, p1}: p1 = 0 -> V->vt[0x80](0x71); p1 = 1..3 -> V->vt[0x80](0x72, p1) -> S->vt[0x28](size) = SC3U
0x41D29A, S = *(X+0x240) = X->vt[0x44]() (snapshot manager, vtable SC3U 0x4D0BF4), X = *(app+0x104) (A->vt[0x7C], class
vtable 0x4D0974). 0x41D29A -> 0x43159C finds/creates the Snapshot frame window (id 0x85202C0E, class vtable 0x4D2044,
0xB8 bytes), sizes it from table SC3U 0x4FA958 ({w,h} by screen width W; window+0xB0 = index), broadcasts 0x62BA7B42.
It does not save immediately: the frame is interactive. Sizes: W > 1200: 640x480 / 800x600 / 1024x768; W > 1000
(1024x768): 480x360 / 640x480 / 800x600; W > 700: 480x360 / 512x384 / 640x480; else 320x240 / 480x360 / 512x384.
Save: the window's DoMessage SC3U 0x43191F handles {0x1A5D056D, p1, p2}: p2 = 0 re-posts itself (one frame later);
p2 = 1, p1 = 1 -> 0x431A6E(1) then close (0x431655). 0x431A6E: captures the window's rect (vt[0xAC]), opens the album
(S->vt[0x1C](1,1,0,0)), album = S->vt[0x24]() (= *(S+0x38)+4), new file name album->vt[0x7C] (SC3U 0x4308F5), writes
with SC3U 0x43CB11 (format by extension).
File (LIKELY): JPG (extension global 0x4F7504 ".jpg"); folder = dirs->vt[0x1C]() + "Albums\\" (0x4F74F4; dirs =
*(SC3U 0x4FAC9C)), probably Apps\Albums\ (std::string at album+0x48); name sprintf("%s-%u%s") = "<city name <=20
chars>-<game date>-<n>.jpg", first free n (<= 10000). No Albums folder in the install yet.
"View Snapshots" (p1 = 0, menu 0x10008010): S->vt[0x1C](1, 1, 0, 1) opens the Photo Album browser over that folder.
Recipe: post {0x2435FF70, size, 0, 0}; next frame find the window (root->vt[0x7C](0x85202C0E), root =
((*(SC3U 0x4FAE74))->vt[0x70]())->vt[0x0C]() LIKELY); optionally move it; SC3U 0x43191F(win, &{0x1A5D056D, 1, 1, 0})
or SC3U 0x431A6E(win, 1); find the new .jpg under the Albums folder.

## 4. Map View (COMM 0x411164F1) (LIKELY)
Command class SIMUI vtable 0x100A2D00 (factory case in SIMUI 0x10011F0B, execute 0x1000F347): finds child 0x42F0DA12
under the main window (exists -> AddRef, return), else creates it via factory (0x1008489D()->vt[0x0C](0x5A3, 0x59A,
&w)), adds and shows it. The overview minimap; no simulation state worth reading.

## 5. Airport / seaport Query (CONFIRMED)
v = valve->vt[0x28]() = valve+0xC (valve objects via layer 0x80F1E6D3 -> QI 0x40A42F1C -> vt[0x14](id, 0xF1EC30,
&valve); 5000 commercial, 8000 industrial; LIKELY city.py's *(*(C+0xE8)+0x18)+0xC = commercial_jobs and
*(*(C+0xEC)+0x1C)+0xC = industrial_jobs). n = building count of the category: C->vt[0x138]() (= C+0xA0, SIMGEOM)
->vt[0x60](cat) = SIMGEOM 0x10003D85(cat) (this unused; static map 0x10030910 category -> occupant count, -1 absent);
n == 0 -> no lines. aura = s8 *(M+0xA4) (city aura; aura layer 0x0259C03F -> QI 0x4259C018 -> vt[0x44]; M+0x1C iface
reads +0x88).
Airport (SIMMISC 0x1000F49C): r = C5000 / (4000*n); "Air Traffic:" (254): r < 0.8 Light (255), < 1.1 Medium (256),
< 1.5 Heavy (257), else Congested (258); "On Time Flights:" (259) "%d%%" = min(98, trunc((aura+128)/255 / r * 100)).
Seaport (SIMMISC 0x1000FC5D): r = I8000 / (4000*n(12330)); "Port Traffic:" (261) same thresholds, labels 262..265;
"Barnacles Removed:" (266) = trunc((1 - (aura+128)/255) * r * 1,000,000). Strings table 0x82E0074C
(re/agents/buildings/txt_82e0074c.txt).

## 6. Civic Query windows (values not in buildings.py)
Hospital / school / college (SIMRCI, LIKELY-CONFIRMED): all numbers are system-wide from R. R getters (vtable SIMRCI
0x1004C99C): vt[0x3C] +0x662, [0x40] +0x660, [0x44] +0x661, [0x48] +0x664, [0x4C] +0x68C, [0x50] +0x66C, [0x54] +0x684,
[0x58] +0x674, [0x5C] +0x688, [0x60] +0x668, [0x64] +0x670, [0x68] +0x678.
Hospital (0x10006CCD): Funding = object+0x34; Doctors R+0x68C; Patients R+0x664; Beds R+0x668 (flagged when patients >
beds); Grade R+0x662 (0..4 = A..F). School: Desks R+0x670; Students R+0x66C; Teachers R+0x684; Grade R+0x660;
"Apples for the Teacher" flavour. College: Capacity R+0x678; Students R+0x674; Professors R+0x688; Grade R+0x661.
Police (SIMSERV 0x10004DC1, arithmetic CONFIRMED): sum the crime layer (C->vt[0x170]()->vt[0x34](x, z, &b)) over a
diamond of radius 20 (byte 0x1002429C) around the station: s1, n1 tiles; sum the police layer (C->vt[0x174]) over a
diamond of the station's own radius (station vt[0x14] = O+0x24): s2, n2. Crimes/Month = 10*s1/n1 + s1 % 13 (0 if
n1 = 0); perf = (s2/n2)*100 / 46 (46 = 20 + (100-20)/3 from bytes 0x1002429E / 0x1002429D); Arrests/Month =
perf*crimes/200 (0x100242AC = 200); rating: perf < 50 Poor, < 80 Fair, perf > 200 and crimes > 0 Oppressive, else
Good. Donuts (flavour): d = distance to a city reference point (C+0xA0+0x70/+0x74): d*10 if no crime, d*(11 - 0.1 *
crimes) if crimes < 100, else d*100/crimes.
Fire (SIMSERV 0x10001A04): Fires/Month = flammability sum (layer 0xC144ACA9 / QI 0x2144802B) over radius 20
(0x100240D0) / (2*tiles); Calls/Month = trunc(fires * (1.5 - 0.3*(aura_at_tile + 127)/255)) (aura layer identity
LIKELY); rating = funding O+0x2C / 500 (0x100240D4): < 0.4 Poor, < 0.7 Fair, < 1.0 Good, else Excellent; Dalmatian
spots = 2/3 * byte at the station tile from C->vt[0x188] layer (flavour).
Jail: Conditions = Overcrowded if inmates > 300 else Good (LIKELY; Poor/Fair strings exist, not traced).
Water building: "Connected to Pipe Network" = W->vt[0x48](x, z) at the building tile, W = C->vt[0x154]() = C+0xBC
(LIKELY). Power plant lines are all covered.

## 7. Population window Education page (CONFIRMED)
Per-age float[90] arrays in R: EQ = R+0x84, HQ (health) = R+0x1EC, age fraction = R+0x354, LE = R+0x4BC. R vt[0x88](a, b)
= 0x10025203: UNWEIGHTED mean of EQ[age] for ages a..min(b, 89) with frac[age] > 0, rounded, returned as u8; vt[0x90]
same over LE; vt[0x80](a, b) sum of fractions; workforce = 20..65 (vt[0x7C]/[0x84]/[0x8C]). No other per-age arrays.

## 8. Preferences: music choices, SC3.cfg
Song list (CONFIRMED): from the audio manager (SIMUI 0x1008E95F): aud->vt[0x14](0x3F7, 0,0,0,0) resets, then
vt[0x14](0x3F8, &songId, &name, 0, 0) loops until it returns nonzero or songId == 0. The window keeps ids at win+0x14,
count +0x24, scroll offset +0x28; rows are check boxes 0x2F95B08 + i.
Enabled flags (CONFIRMED): std::map<songId, bool> at PR+0xB34 (node +0x10 key, +0x14 byte); get PR vt[0x8C](id) = SC3U
0x40A95F (absent = enabled); set PR vt[0x90](id, b) = SC3U 0x40A98B. A toggle writes immediately: aud->vt[0x14](0x3F4,
id, b, 0, 0) then PR->vt[0x90](id, b) (SIMUI 0x10059000); Cancel restores the old values (0x1005644D).
Preview Score: Play 0x2F95B10 -> aud->vt[0x14](0x3F5, selectedId = win+0x30, 0,0,0); Stop 0x2F95B11 -> aud 0x3F6.
PR+0xA8 / +0x8A8 / +0x938 are not music: blocks returned by PR vt[0x3C] / vt[0x40] / vt[0x44]; +0x8A8 is used by the
New City Options builder/apply (0x1005BC23 / 0x1005EB63).
SC3.cfg: path string PR+0xB20 (ctor 0x408C25 from 0x4F4F1C "SC3.cfg"); load PR vt[0x0C] (SC3U 0x409174); save PR
vt[0x10] (SC3U 0x4092A7: DeleteFileA, then every group via 0x409E78; the song map is persisted 0x409770 / 0x40A1FD).
The OK handler does not call Save and no direct caller was found: most likely written at exit (OPEN). Force:
call(SC3U 0x4092A7, [], this=PR).

## Open questions (live)
1. Which way PgUp/PgDn rotate on screen (read P+0x2C). 2. Actual Albums folder and file name after a snapshot.
3. Root-window lookup for the snapshot frame; whether 0x431A6E captures the frame itself. 4. SC3.cfg save timing.
5. The aura layer used for fire calls and the Dalmatian layer (C vt[0x188]).
