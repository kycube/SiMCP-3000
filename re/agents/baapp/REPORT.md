# Building Architect (Apps\Baapp.exe) program (static RE by subagent; saved by main)

Baapp.exe VAs (base 0x400000), thiscall unless cdecl; vt[+0xNN] = byte offset. C = confirmed by code, L = likely,
O = open. Scripts here (inv, ixf, vts, allvt, sw, strrefs, getters, funcs; check.py 35/35 pass).

## 0. Framework (C)
GZ app like the game: exports GZDllGetGZCOMDirector (0x451BD7 -> 0x45D694 = director at 0x4971D8); framework at
*(0x4971C8) (getter 0x45BA65), vtable 0x48414C with SC3U's slots (3 AddSystemService, 4 GetSystemService, 8 AddToTick
0x45C0F8 list +0x28, 16 Quit) - the bridge's tick hook works unchanged. GZCOM() 0x451BCB. The 6 DLLs (gzgraphicd,
gzresourced, gzwind, gzserviced, simui, simgeom) are loaded by 0x410EC6 for UI widget classes only; model, palettes,
renderer and .bld I/O are all in Baapp.exe. SIMBABLD.DLL is a game module sharing the code.
Cached getters (cdecl): message server 0x44F773 (cache 0x497104, service 0x64063387); window manager 0x44F7F7 (cache
0x497124, service 0xA417445E, same GZWIND as the game: modal wm+0x30, depth wm+0x194, DoModal wm->vt[0xA0], EndModal
wm->vt[0x44](0xD, win, result), MessageBox wm->vt[0xAC]; button ids OK 0x5301814A, Yes ..4C, No ..49, Cancel ..47 - L);
directory manager 0x44F8B3 (service 0x2073215D); command server 0x46F43F (cache 0x4DFBB0, service 0xA4B5E41F): command
srv->vt[0xC](clsid, 0x6856F7, &cmd) or 0x441194(this=&out, clsid). Messages {id, p1, p2, p3}: post ms->vt[0x10](&msg,
0), send ms->vt[0xC](&msg). Command parameters: number v = 0x479692(0x28) (new), 0x453A05(this=v, value, type) (3 =
uint32); string 0x4539CB(this=v, &BaString); cmd->vt[0xC](v); run cmd->vt[0x2C](); release cmd->vt[8]().
BaString (0x14): {vtable 0x480344, begin, end, cap, refcount}; construct 0x402C4C(this, char*); assign vt[0x28] =
0x44F39B(this, char*); copy 0x402D25; c_str = +4; fake {0x480344, begin, end, end, 1} fine for read-only args.

## 1. Objects
App (cIGZApp at +0x18) *(0x4954DC) (ctor 0x401FEE, 0x68, vtable 0x480464; app->vt[0x34](0,0) = 0x411309 exit prompt +
quit). BA manager M *(0x4954E0), getter 0x4010C9 / 0x40F6A8 (cdecl, creates on first use); ctor 0x405189, 0x78, vtable
0x480C78; M+0x1C library, M+0x2C main window, M+0x34 current file path (BaString). M vtable: +0x10 / +0x18 render into a
.DAT (0x40446B / 0x404488 -> 0x4044A9); +0x14 ReadBuildingInfo(path, ...); +0x1C GetMainWindow 0x405369; +0x20
GetCurrentBuilding 0x4053C1; +0x24 GetView 0x4053E2; +0x28 ensure main window; +0x2C GetLibrary 0x405468; +0x30
SetCurrentBuilding(model, resetPath) 0x40601D (posts 0x63CC69AC); +0x34 LoadBuilding(char* path, Model** out) 0x4063C8;
+0x38 SaveBuilding(Model*, char* path) 0x4060EB; +0x3C / +0x40 write / read the .bld header only; +0x44
GetCurrentPath(BaString* out) 0x4060C8 (true if the file exists); +0x48 / +0x4C building-set stubs (return 0). cdecl
helpers: 0x40F6AD current building, 0x40F6D3 view, 0x40F6C0 library, 0x40F6E6 = M vt[+0x28].
Main window A = M->vt[0x1C]() (= M+0x2C; class vtable 0x48160C, 0xDC; DoMessage 0x41D4E5): A+0xBC main-menu screen,
A+0xC4 toolkit screen, A+0xCC current screen (0 menu, 2 toolkit, 3 Architect Assistant L), A+0xA4 view.
Building view V = M->vt[0x24]() (= A+0xA4; vtable 0x4817FC, 0x2258, ctor 0x41E852; DoMessage 0x439360).
Toolkit controller: toolbar callback 0x440718 -> 0x440760(win, buttonId); DoMessage 0x4411F6 (ctor 0x44041A, 0xDC).
Palette controller: callback 0x445988 (ctor 0x447D6D); palette windows blocks 0xA429FBBA, paints ..BB, details ..BC,
props ..BD. Library L = M+0x1C (getter 0x40F6C0; ctor 0x41A639, 0x54). Current building 0x40F6AD() = V->vt[0x1F8]() =
V+0x674.

## 2. Model (document)
Model (C): ctor 0x40A8FA, vtable 0x480D70, 0x1A0190 bytes; AddRef 0x40A8C6, Release 0x40A8D9 (count +0x1A018C).
+0x0C byte default 2 (header); +0x10 BaString architect (default "Maxis", BAT string 0x1D1); +0x24 BaString name
("New Building", 0x1D2); +0x38 BaString description; +0x4C building type = BAT string index 0x208..0x217 (Residential,
Commercial, Industrial, Police Station, Jail, Fire Station, Hospital, School, College, Library, Museum, Historic
Statue, Mayor's House, City Hall, Performing Arts Center, Other; 0 shows as Other); +0x50..+0x53 bytes defaults 2, 0,
0x1C, 0 (+0x50 >= 2 new-style ground, L version); +0x54 stamp on property change (service 0x441E5070 vt[0x20]); +0x58
thumbnail; +0x5C footprint size in cells (square); +0x60 max height in cells; +0x68 block count; +0x6C / +0x78 content
bbox {x,y,z} / {dx,dy,dz} (updated by 0x40F336, L); +0x84 default rotation of shape-0 blocks; +0x88 free-list head;
+0x8C block pool Block[] (0x20 each; index 0 = null); +0x90 column grid u32 head[x][y] = *(*(m+0x90)+4x) then [4y];
+0x190 dirty; +0x1AC texture table 256 x {u32 refcount, Item*} (count +0x800); +0x1B0 undo recording disabled; +0x1B4
undo log 0x7FFF x 0x14 (position +0xA01A0); +0xA01A4 saved block copies (0x7FFF x 0x20; count +0x1A0188).
Grid: 8 cells per tile; CreateNewBuilding size tables 0x493EC0: footprint 8/16/24/32/40 cells, height 28/64/108/144/80
cells for tile sizes 1..5. Layer z = 0 is always a full ground layer of shape-0 blocks (0x409E58); user blocks start
at z = 1.
Block (0x20, C except face directions): u32 bits [0:16] next block in the column (sorted by z) | [17:25] z (0x1FF unset)
| [26:29] shape 0..15 | [30:31] rotation 0..3; u32 visibleFaces (bit i = face i visible; derived; init 0xFF);
face[6] at +8 x 4 bytes {u8 paintSlot, u8 paintParam, u8 decalSlot, u8 decalParam} (slot 0 = none). Default block
0x409FD9(this=buf): z = 0x1FF, +4 = 0xFF, faces 0. Shape geometry table 0x494228 (16 x 0x78: up to 8 polygons of 9
bytes {flags, 4 vertex ids, 4 uv ids} + per-rotation face lists). Cube faces: 0 top, 1-4 sides, 5 bottom (L: 1 +x,
2 +y, 3 -x, 4 -y; vertex ids 8..11 mid-height). Shapes (palette = shapes 0-7 and 9-14 x rotations 3,2,1,0; tables
0x482720 / 0x482714; labels L): 0 cube, 1 vertical half (triangular prism), 2 ramp / wedge, 3 three-corner slope,
4 corner pyramid, 5 slanted wall, 6 variant of 3, 7 tetrahedron, 8 flat floor (bottom face only; old-style ground),
9-14 half-height (low pitch) slope variants, 15 special anchor block (cube geometry) for props (prop slots = the paint
bytes of faces 1-4 (+0xC/+0x10/+0x14/+0x18), indexed by the rotation bits, L).
Model functions (this = model): 0x40B977(pos*, bool incl15, bool) find block -> index (0 none), pos {i32 x, y, z},
x, y < +0x5C, z < +0x60; 0x40BA33(pos*, Block*) SetBlock (insert/replace, undo, dirty, neighbour visibility; shape-0
blocks get rotation from +0x84; the template's z bits must equal pos.z, next bits ignored); 0x40C5FF(pos*) RemoveBlock;
0x40CC6F(from*, to*, Block*) / 0x40CFBC(from*, to*) fill / erase line; 0x40D2D8(a*, b*, Block*) / 0x40D3AA(a*, b*)
fill / erase rectangle; 0x40DFD8(Block*, face, Item*) set face paint (Item* 0 clears; edits a COPY - commit with
SetBlock); 0x40E042(Block*, face, Item*, param) paint with param; 0x40E0B4(Block*, face, Item*) set decal; 0x40E11E(...,
param) decal with param; 0x40B263(dir) rotate the whole building; 0x40F5DD / 0x40F622 / 0x40F674 Undo / Redo /
ClearUndo; 0x40D9B0 / 0x40D913 / 0x40DAD2 (&V+0x6C8) copy / cut / paste plane; 0x40AC79(footprint, height) init,
0x409E58 then ground layer.
Recipes: read: m = call(0x40F6AD); for x, y < m+0x5C: idx = head[x][y]; while idx: b = *(m+0x8C) + 32*idx (z, shape,
rot from bits; faces); idx = b.bits & 0x1FFFF; texture of slot s: item = *(*(m+0x1AC) + 8*s + 4), name BaString item+0x48
(c_str item+0x4C). Add: call(0x409FD9, this=blk); blk.bits = rot<<30 | shape<<26 | z<<17; pos {x, y, z};
call(0x40BA33, [pos, blk], this=m); refresh call(0x40F336, [m+0x6C], this=m) (L), call(0x43628E, [1], this=V), post
{0x63CC69AD}. Paint one face: idx = call(0x40B977, [pos, 1, 0], this=m); copy the 32 bytes to blk; item via
call(0x418705, [paletteId, &item], this=L) or by name call(0x41874A, [&BaString, &item], this=L); call(0x40DFD8, [blk,
face, item], this=m) (decal 0x40E0B4); call(0x40BA33, [pos, blk], this=m). Through the view's tools (multi-face
decals, flood fill, prop footprints): hit struct {u8 face; u32 blockIdx; i32 x, y, z (at +5); u16 type = 0x80 (at
+0x11)} for a face of an existing block (ground counts), this = V: Fill 0x43C1EA(hit*, paintId); Decal 0x43C486(hit*,
detailId; 0 removes); Place prop 0x43CA7C(hit*, propId) (L); Remove prop 0x43C803(hit*) (returns the prop id).
Remove / undo / redo: 0x40C5FF / 0x40F5DD / 0x40F622 on the model, or post {0x63CC69A7, 1} undo / {.., 2} redo.
Properties: call(0x44F39B, [char*], this=m+0x24) name (m+0x10 architect, m+0x38 description); type -> m+0x4C
(0x208..0x217); dirty byte m+0x190 = 1; saved into the header by SaveBuilding.

## 3. Palettes / library
Items: L+0x3C .. L+0x40 = vector<Item*>; id map L+0x24; find by id 0x418705(id, &item), by name 0x41874A(&BaString,
&item), for-each 0x4186C3(cat, callback, ctx). Item (0x84, ctor 0x41860F): +0x0C category, +0x10 id (palette/message
id), +0x48 BaString file name, +0x5C BaString directory. The id is a hash of the image pixels (0x418010, L): stable,
not readable - list live. Categories (M init 0x40569D, C): 0/1/2 Res\BA\PAINTS\Ground / Roofs / Walls; 3 Colors
(generated solid colours "color r,g,b", 0x4054B2); 4/5 Res\BA\DETAILS\Contemporary / Traditional (each subfolder a
detail set); 6/7 BACustom\Paints / Details; 8-15 Res\BA\PROPS\{Architecture, Building Decoration, Plaza and Street, Yard
Objects, Flora, Industrial, Rooftops, Vehicles}; 16 BACustom\Props. IsCustom 0x4185E3 (6, 7, 16); IsProp 0x4185F9
(>= 8). MET (C, parser 0x419D88, strtok ",:\r\n"): one line per prop orientation `W,D,H:"b0.bmp","b1.bmp","b2.bmp",
"b3.bmp"` (W, D footprint cells 1..7, H height cells; 4 bitmaps = views for camera rotations 0-3; the 4 lines of one
prop list the same bitmaps rotated); prop palette loads 0x419D46(cat); custom props in BACustom\Props. Paints/details:
.tga/.bmp (also .plt L); DETAILS tiles named "set NN". Block palette: 56 items, item data 0xEAEA0000 | rot<<8 | shape;
selecting posts {0x63CC69A9, shape, rot}. Text: BATStringsMain = table 0x63DE4715 (174), BAMBEStringsMain = 0x9A0884AD
(prop category names, render messages); block palette has no text names.

## 4. File operations (C)
New, no dialog: ok = call(0x41DA42, [size 1..5]) (cdecl): creates + initialises the model with the ground layer, clears
undo, M->vt[0x30](m, 1), posts SetMode(0); then post {0x63CC699D} to show the toolkit. With the UI dialog: post
{0x63CC6994} (asks to save if dirty, then the tile-size dialog).
Load: m = 0; ok = M->vt[0x34](char* path, &m) (0x4063C8; blocks, header, thumbnail; M+0x34 = path); M->vt[0x30](m, 0);
0x40A8D9(this=m) release; post {0x63CC69B9, 1} and {0x63CC699D} (= the Load dialog's commit 0x426D0C for kind
0x83172AD7).
Save As: M->vt[0x38](m, char* path) (0x4060EB) writes {0xE3F87B0C, 0xC3F8D4A9, 0xA3F8D615} blocks; {0xE3F87B0F, ..,
0x63FBE1CC} header (name, architect, description, type, +0x50..53, registry "ergc"); {0xE3F87B0E, .., 0xE3F8D655}
thumbnail; texture records 0xE3F87B0D / 0xE3F87B10; sets M+0x34, clears dirty. Save to the current path:
M->vt[0x44](&BaString) then M->vt[0x38](m, c_str). Exit: post {0x63CC698E} (prompts) or framework Quit.
Render to SimCity (button 0x45C78D0A, GZ command 0x25C7D05A, class vtable 0x48038C, Execute 0x401776): command with
param 1 = string variant .bld path, param 2 = uint32 (1 interactive prompts, 0 silent); or call(0x401C73, [&BaString
path, interactive], this=any) (L) -> 0 ok or 0x65C8BC66 cancelled / declined, ..67 path, ..68 BAT.DAT locked ("exit the
game"), ..69 open failed, ..6A duplicate name while silent, ..6B no M. The building must be saved on disk; writes
<Apps>\BARender\BAT.dat (0x4018CA) via M->vt[0x18](&datPath, 1, ...) and keeps Res\BA\RenderedBuildingsBackup.IXF;
interactive prompts "Duplicate Name Exists - replace?" (MBE 0x0E), "Update Building List..." (0x25), "Render Building
Complete" (0x11); the game must be closed. The toolbar button first asks "must be saved..." (MBE 0x36) if dirty and
posts Save As 0x63CC6996. Building sets (.bst/.scs): stubs in this build.

## 5. Screens, modes, tools, messages, hotkeys
View fields (C): +0x674 model; +0x690 renderer; +0x6AC mode; +0x6C8 view volume {x,y,z} (+0x6D4 size); +0x700 cursor;
+0x778 zoom 0..5; +0x781 / +0x782 add / erase drag; +0x7FC block shape, +0x800 block rotation; +0x804 detail id;
+0x808 paint id; +0x80C prop id; +0x81C / +0x820 tool; +0x824..+0x830 last tool per mode. View vtable: vt[0x1E0](code,
value) = 0x436735 (0x63CC69A6 SetMode, ..A7 SetTool, ..A8 palette select); vt[0x1E8](cmd) hotkey handler 0x436940;
vt[0x1F4] SetModel 0x41ECC4; vt[0x1F8] GetModel. Direct: SetMode 0x41FB20(mode), SetTool 0x41FC71(tool), Zoom
0x43AC76(+-1), RotateBuilding 0x43A8E5(+-1, 1), ResetView 0x43A82F(), Redraw 0x43628E(bool), SetCursor 0x43A45E(pos*).
Modes (V+0x6AC): 0 Construct, 1 Paint, 2 Detail, 3 Props, 4 File / preview (initial). Tools (V+0x820): 1 Undo, 2 Redo,
3 Erase, 4 Eyedropper, 5 Block (Construct default), 6 Line, 7 Plane, 8 Paintbrush, 9 Fill (Paint default), 10 Apply
Decal (Detail default), 11 Place Prop (Props default), 19 select (temp), 21 = default tool of the mode.
Toolbar ids -> 0x440760: mode tabs 0xE4161B03 Construct, ..04 Paint, ..05 Detail, ..38 Props, ..06 File; tools ..07
Block, ..08 Line, ..09 Plane, ..0B Paintbrush, ..0A Fill, ..0C Decal, ..39 Prop; 0x75B3D3C1 Erase; 0x55B3D3BC
Eyedropper; 0x75B3D3BF Undo; 0x65B3D3BB Redo; file ..0D Save, ..0E Save As, ..0F Load, ..10 New, ..11 Exit;
0x45C78D0A Render; 0x65B3D4C8 -> command 0x45C50AFF (opens a web page).
Main menu buttons (0x42F052): 0xA3CCA1C0 New -> 0x63CC6994; ..C1 Load -> 6995; 0xE2FBA4B4 -> 6993; 0x63FA2883 -> 699A
(Credits, L); 0x42B7C353 / 0xA2FBB0B3 Exit.
Messages 0x63CC69xx: 8E Exit; 8F Edit Building / show toolkit; 91 / 92 main menu; 94 New; 95 Load; 96 Save As; 9A
dialog; 9D / 9E show toolkit; 9F / A0 zoom in / out; A1 / A2 rotate building -/+; B0 / B1 rotate view volume only; A7
{tool}; A8 {id}; A9 {shape, rot}; AB pan {x+1000000, y+1000000}; AC building changed; AD model edited; B6 palette sync;
B7 {3, code, value} -> V vt[0x1E0] (post {0x63CC69B7, 3, 0x63CC69A6, mode} = change mode as the tabs do); B9 {n} select
tab; 0x22CCA9D3 {cmd} hotkey -> V vt[0x1E8].
Hotkeys group B1: Num+ / = zoom in; Num- / - zoom out; Space / Ctrl+Space rotate building; B / N working plane down /
up; G, H, Num1/3/7/9, arrows, PgUp/PgDn plane / cursor (L); Q cycle tools; E Erase; R Eyedropper; U / Ctrl+Z undo; Y /
Ctrl+Y redo; Ctrl+C / X / V copy / cut / paste plane; Ctrl+S / F1 Save; Ctrl+A / F2 Save As; Ctrl+L / F3 Load; Ctrl+N /
F4 -> 6993; Num5 / Ctrl+PgDn reset view; F9 / F11 renderer toggles; F10 grid (V+0x84C). Group B2 handler not found (O).

## 6. Camera
No free camera: zoom V+0x778 (0..5; messages 0x63CC699F / A0 or 0x43AC76(+-1)); view volume / working plane
V+0x6C8 / +0x6D4, cursor V+0x700; pan 0x63CC69AB. Rotate turns the building itself (0x40B263 via 0x43A8E5). Renderer
V+0x690 uses BATConfig light sets per mode (0x425D57(mode)).

## 7. Open (live)
1. Face index -> compass direction; shape names. 2. Handler of 0x63CC6993 and the B2 hotkeys. 3. Texture-table
refcounts when replacing a face texture via SetBlock (limit 255 per building). 4. How props are stored in shape-15
blocks; hit-struct size; prop ids for .met entries. 5. One SetBlock = one undo step? Is 0x40F336(m+0x6C) needed?
6. Render via 0x401C73 with a dummy this; toolkit visibility. 7. Library item name format. 8. .bld path on the
command line (string 0x2CF).
