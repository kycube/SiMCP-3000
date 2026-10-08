# MAP subsystem: static RE report (subagent; saved by main)
Addresses `MODULE preferred-VA`; city = *(STRTSIM 0x10032C9C); thiscall; vtable offsets in bytes. Helpers here:
h.py, vtd.py, getter_uses.py, ixf.py (IXF parser), tkb.py (TKB1 property parser), dump_occ.py -> **occupants.tsv**
(1100 occupant ids: name, owner class, category, size, from Res\Occupant\*.IXF).

## 1. Map size, grid ownership, coordinates
- Size per city size CONFIRMED (SIMUI 0x1005ECEA, New City dialog): radio 0x2552484F Miniature 64, 0x25524850 Small
  128, 0x25524851 Medium 192, else Large 256; square. Start year from same dialog: 0x76C 1900, 0x79E 1950.
- city+0x3C W, +0x40 H, +0x44 256 (third dim). Getters city vt+0xCC/+0xD0/+0xD4; vt+0xD8/+0xDC/+0xE0 same <<8.
  Written in city init SIMCITY 0x10003CC8 from params (vt+0x54/+0x5C/+0x58).
- World units 256 per tile; world box = 6 ints {x0,y0,z0,x1,y1,z1}, z vertical (SCENARIO 0x10006149). City floats
  vt+0xF4 = 16.0, vt+0xFC = 3.266 (GUESS metres per tile / per altitude step).
- **No per-tile struct.** Each layer is a 2D array object {+0 vtable, +4 dimX, +8 dimY, +0xC rows}, rows[x] -> row of
  dimY elements: **elem(x,y) = rows[x][y]**, x first (range W).
- Owners: terrain city+0xA4 (SIMDIRT, city vt+0x13C); occupants city+0x84/+0x88/+0x8C (3x SIMGEOM occupant manager,
  city vt+0x11C/+0x120/+0x124); data maps = simulators (section 4).

## 2. Terrain (dirt = city+0xA4, SIMDIRT vtable 0x1002046C, Init(city) vt+0x24 0x10003E50)
| Off | Type | Meaning |
|---|---|---|
| +0x24 | byte | initialized |
| +0x30 | grid<u8> (W+1)x(H+1) | altitude per vertex (init 0x7F; editor clamps 2..0xFD) |
| +0x38 | grid<u8> same | water surface level per vertex (init = sea level) |
| +0x3C | u8 | sea level (vt+0x60; ctor/Init 0xF6, vt+0xA0 sets 0x1E; T1) |
| +0x40, +0x44 | grid<u8> | unknown (+0x44 init 0) |
| +0x48 | bit-grid (vt 0x10020768: +4 dimX, +8 dimY, +0xC words/row, +0x10 rows) | per-vertex flags |
| +0x50..+0x5C | u32[W*H/32] x4 | per-tile bit arrays |
| +0x64 | city* | |
vt+0x4C GetAltitude(x,y,u8*) 0x10005AB0 (= vt+0x68); vt+0x50 GetWaterLevel(x,y,u8*) 0x10005AD0; vt+0x54
AnyCornerSubmerged(tx,ty) 0x100065F0; vt+0x58 submerged corner count (LIKELY). Water: corner wet if water >= alt.
vt+0x84 SetAltitude(x,y,u8) 0x10005DF0; vt+0x8C SetWaterLevel(x,y,u8,flag) 0x10006220 (raw, no cost). vt+0xA8/+0xAC
W/H; vt+0xB0/+0xB4 W+1/H+1; vt+0xD8 IsValidVertex. SIMDIRT 0x1000F240 ShiftAllTerrain(delta) (cheats "Terrain one/ten
up/down": 0xA31CF2EF +1, 0xC31CF2F6 -1, 0xC31CF2FA +10, 0x831CF2FF -10; dispatcher ~0x10005924). vt+0xF0..+0x134 (18
methods) area terraform (GUESS). UI landscape tools with cost not traced. Trees are occupants (SIMGEOM 0xFFD30C03,
0x13C bytes, ctor 0x1000B8F1; key {0xFFD30C03, 0x80F48961, id}, 6..12 densities, 7000+ single trees).

## 3. Occupants
Occupant manager SIMGEOM vtable 0x10029E24 (class 0xE150E7BB, 0xC4 bytes); three at city+0x84/+0x88/+0x8C
(cmdCountStructures SCENARIO 0x10006194 searches all three; roles open, T2).
| Off | Meaning |
|---|---|
| +0x28/+0x2C/+0x30 | std::vector<occ*> (LIKELY all occupants) |
| +0x90, +0x94 | locks (vt+4 lock, vt+8 unlock) |
| +0x98 | grid<u32 occ*> rows[x][y]: tile -> occupant |
| +0x9C | grid<u8> flags: bit0 occupied; bit1 cell holds packed x | y<<16 of the anchor cell |
| +0xA0/+0xA4/+0xA8 | W-1, H-1, D-1 |
| +0xB0 / +0xB8 | layer id / listeners vector |
Methods: vt+0x60 IsOccupied(x,y) 0x1000F070; vt+0x6C IsValidTile; vt+0x70 NewIterator(iter**); **vt+0x74
NewIterator(iter**, worldBox* or 0, filter*) 0x1000EB50**; vt+0x84/+0x88 rectangle queries (5 args).
**DANGER: vt+0x4C (0x1000E310) RemoveOccupantAt(x,y), vt+0x44 same for a world point. Never call to query.**
Iterator (SIMGEOM vtable 0x10029F90): vt+0x14 First() -> occ*|0; vt+0x1C Next(); vt+0x18 Current(); vt+0x08 Release
(loop pattern SCENARIO 0x10006011). Occupant: vt+0x04/+0x08 AddRef/Release; **vt+0xD0 GetTileRect(int r[4])**
{x0,y0,x1,y1} inclusive; **vt+0x88 GetTypeID() -> u32** (LIKELY); vt+0x54 -> u8.
Classes: building 0x207EDC0E (0x14C bytes, ctor SIMGEOM 0x100230F8, vtables +0 0x1002B860, +0x14 0x1002B7B0, +0x18
0x1002B794, +0x13C 0x1002B8A0); base occupant 0xC179C042 (ctor 0x10022364); flora 0xFFD30C03; pier 0x220055E1;
network pieces SIMNTWRK class 0xE223741F. Type key {owner clsid, type, id}: buildings {0x207EDC0E, 0x57E, id};
networks {0xE223741F, 0xA317745F, id}; flora {0xFFD30C03, 0x80F48961, id}; pier {0x220055E1, 0x57E, id}. Names in
Sys\Occupant.ini [OccupantKeys] and Res\Occupant\OccupantAttribs*.IXF (TKB1 property sets: 0x64 name, 0x65 category
(16000 road, 17000 rail, 3100-3700 res ...), 0x66 [x-size, height, y-size] (LIKELY), 0x67/0x6D sprite/text keys).

## 4. Data-map layers
Generic layer base (CONFIRMED, ~20 accessors): L+0x14 shift (cell = 2^shift tiles), L+0x18 grid {+4 dimX, +8 dimY,
+0xC rows}, value = rows[x>>shift][y>>shift]; Get(x,y,T*), Set(x,y,T*), GetColor(x,y,u32*) = byte*0x808080.
| city+ | Class | Layer | Elem / shift | Get / Set / Color |
|---|---|---|---|---|
| 0xD8 | SIMSERV 0x1001EA38 | Crime | u8 / 1 | vt+0x7C / +0x84 / +0x5C |
| 0xDC | SIMSERV 0x1001F46C | Police | u8 / 2 | vt+0xB0 / +0xB8 / +0x90 |
| 0xE0 | SIMSERV 0x1001EE04 | Fire | u8 / 2 | vt+0xA4 / +0xAC / +0x84 |
| 0xF0 | SIMRCI 0x1004C624 | Land value | u8 / ? | vt+0x7C / +0x84 / +0x5C |
| 0xD4 | SIMECO 0x1001B984 | Pollution | packed u32: bits 15..29 and 0..14 = 15-bit values, bit 30 flag; UI max 11000 air/water, 30000 garbage | subobject getters 0x10008D90..0x10008E0D, 0x1000B159 |
| 0xB4 | SIMRCI 0x1004D1E0 | Zones; type < 0x17 (1-3 R, 5-7 C, 9-11 I) | ? | vt+0x50 checks type |
| 0xB8/0xBC | SIMUTIL 0x10020550 / 0x10022944 | Power (LIKELY) / Water | bit-grids (rows at +0x10, 32 tiles/u32) | 0x10005850 / 0x100033E9 |
| 0xE4/0xE8/0xEC | SIMRCI | R/C/I zone developers | | |
Not located: health/education coverage, per-tile traffic (candidates SimTransit +0xAC, STRTSIM +0xCC). City-wide:
land value [+0x28]->vt+0x44; pollution vt+0x78/+0x7C/+0x80.

## 5. Query, picking, camera
View = SIMSPR class 0x0410C5C7 (0x238 bytes, factory 0x1004C962, ctor 0x100484C2), vtable SIMSPR 0x10067894, msg
iface +4 (vtable 0x100676AC, DoMessage 0x10048D7A); no global (find live, T4). view->vt+0x20 CenterOnTile(tx,ty,1)
0x10043540; view->vt+0xB0 SetZoom(z,0,1) 0x100430C4 (z 0..4); message 0x44A42474 {x, y, zoom} (SIMSPR 0x10048F04;
cmdMoveCamera SCENARIO 0x10008721 posts it via msgServer->vt+0x10(msg, 0)). Picking: cam = *(view+0xB8);
cam->vt+0x8C(sx, sy, int w[3], 0) -> bool; tile = (w[0]>>8, w[1]>>8) (CONFIRMED in view vt+0x74 CenterOnScreenPoint
0x100499FA). Tile -> screen not found. vt+0x24/+0x28/+0x2C/+0x30 -> camera vt+0x60/+0x64/+0x70/+0x74 (GUESS rotate/
zoom). Query dialog not traced.

## Recipes
R1 Map: W=[city+0x3C], H=[city+0x40]; dirt=[city+0xA4]; alt=[dirt+0x30], wat=[dirt+0x38]; rows=[g+0xC]; row x =
   [rows+4x] (H+1 bytes), W+1 rows; sea=[dirt+0x3C]; tile is water if any corner wat >= alt.
R2 Tile occupant: m=[city+0x84] (+0x88, +0x8C); cells=[[m+0x98]+0xC], flags=[[m+0x9C]+0xC]; f=byte [[flags+4x]+y];
   if f&1: p=[[cells+4x]+4y]; if f&2: p=[[cells+4(p&0xFFFF)]+4(p>>16)].
R3 Enumerate: R2 over all tiles, dedupe; or UI thread m->vt+0x74(&it,0,0); o=it->vt+0x14(); o=it->vt+0x1C() until 0;
   it->vt+0x08(); id=o->vt+0x88(); o->vt+0xD0(&r[4]).
R4 Query tile: R1 + R2 + section-4 layers at rows[x>>shift][y>>shift].
R5 Camera: view->vt+0x20(tx,ty,1); vt+0xB0(z,0,1); picking [view+0xB8]->vt+0x8C(sx,sy,&w,0).
R6 Debug terraform: SIMDIRT 0x1000F240(this=dirt, delta); dirt->vt+0x84(x,y,alt).

## Open questions (live)
T1 sea level / water vs alt at sea and land tiles. T2 manager roles (+0xA0 per manager; build road and house).
T3 iterator with box 0, filter 0. T4 heap scan for view vtable; vt+0x20 centre; vt+0x24..+0x30. T5 shift/dims of
+0xF0, +0xB4, +0xD4, SIMUTIL layers. T6 vector at +0x28 vs R2 unique occupants.
