# DATA MAPS AND CITY STATISTICS (static RE by subagent; saved by main, 2026-10-07)

Preferred-base VAs. C = *(STRTSIM 0x10032C9C). Grid object {+4 dimX, +8 dimY, +0xC rows}, value rows[x][y].
Way in: each simulator's data view (ids 0x27xx; slot 18 (x, y, u32* colour) = overlay value -> colour) and
the per-tile Query text (string group 0x82E0074C). CONFIRMED / LIKELY / OPEN.

## 1. Pollution (SIMECO): P = *(C+0xD4) (iface), M = P-0x1C
- Main grid: shift *(P-8) = 1 (2x2 tiles), grid *(P-4), u32 cells: bits 15..29 air (vt[0x58] 0x10008DDD),
  bits 0..14 water (vt[0x5C] 0x10008E0D) (query 0x1000C95C, views 0x2731/0x2732). CONFIRMED.
- UI maxima air/water 11000 (0x1002025C/60), garbage 30000 (0x10020258); query labels 0 None, <Max/8 Low,
  <Max/4 Medium, <Max/2 High, <4Max/5 Very High, else Hazardous. "Polluted" tests >= 4000 / 2000 / 1.
- Bit 31 radiation (LIKELY; view 0x2735; SIMDSTR 0x10007815 meltdown radius 20). Bit 30 OPEN (SC2K import).
- Garbage per tile: object at P+0x128 (vtable 0x1001BAF0) with grid* at +0xC; full resolution, u16, bits 0..14
  amount (vt[0x60]), bit 15 flag (OPEN). CONFIRMED.
- Generation grids (shift 1): air M+0x58 u32, water M+0x74 u32, garbage M+0x128 s16 (wrapper +0x14 shift,
  +0x18 grid).
- City averages (monthly 0x10007A9E): P+0xD0 air, P+0xD4 water, u16 P+0x138 garbage (over polluting tiles).
- Garbage chart (SIMUI 0x1002248D): produced/yr P+0x154 x 0.1 t; landfill P+0x184, neighbor deals P+0x164,
  incinerators P+0x174 + P+0x17C (L), recycling P+0x16C (int64), collecting in streets u32 P+0x150; P+0x15C
  OPEN; monthly int64[12] at P+0x18C, +0x1EC, +0x24C, +0x2AC, +0x30C, +0x36C, +0x3CC.
- Landfill (query 0x1000D544): capacity t = *(P+0x468) x 0x7FFF x 0.1; % full = ceil(100 used / capacity),
  used = (*(P+0x13C))->vt[0x2C](). Incinerator capacities vt[0xF0](12852/12853).

## 2. Power and water
- Power: main = *(C+0xB8) - 0x14; bit grid B = *(main+0xC) {+4 W, +8 H, +0xC words/row, +0x10 rows};
  powered(x,y) = (rows[x][y>>5] >> (y&31)) & 1. View 0x2722: 0 Powered, 1 Power Failure, painted on zoned tiles
  and consumers. CONFIRMED (conductor tiles LIKELY also set).
- Water: W = *(C+0xBC) main; dim u16 W+8; bit arrays dim x dim, row-major by y (word (y*dim+x)>>5, bit x&31):
  W+0x68 watered (CONFIRMED, query "Watered:", view 0x2720), W+0x40 last month (L), W+0x70 pipe tiles (L), W+0x6C
  OPEN. No water pressure.

## 3. Traffic: T = *(C+0xAC); full-resolution grids
- T+0x5C u16 network flags: 1 road, 2 highway, 4 rail, 8 subway, 0x10 station (L), 0x20 OPEN.
- Density u8: T+0x60 road/rail/station(/0x20), T+0x64 highway, T+0x68 subway; vt[0x60](x, y, u8*, mask) max.
- Labels "Traffic"/"Rail Usage": 0 None, <65 Light, <130 Medium, <180 Heavy, else Congested; 0 when strike byte
  T+0x108 == 1. View 0x2715 (flags & 0x17), colour n*v/231.
- Passengers/day = T+0x60 at the station tile x 4.3 (0 on strike). Station categories 12210 bus, 12230 train,
  12360 subway, 12361 subway-rail. No per-station ridership object.

## 4. Health and education: city-wide (no coverage maps), R = *(C+0xE4)
u8 +0x660 school / +0x661 college / +0x662 health grade 0..4 = A..F (vt[0x40]/[0x44]/[0x3C]); +0x664 patients,
+0x668 beds, +0x68C doctors; +0x66C students, +0x670 desks, +0x684 teachers; +0x674 college students, +0x678
capacity, +0x688 professors; +0x67C library books (L), +0x680 OPEN. Strike bytes R+0x650 schools, +0x651
colleges, +0x652 health (L).

## 5. Demographics (CONFIRMED)
R+0x354 float[90] = population FRACTION per age (sums to 1.0); head count = frac x pop (pop =
*(*(R+0x24)+0x0C)). R+0x84 float[90] EQ per age; R+0x4BC float[90] HQ = life expectancy in years per age;
R+0x1EC OPEN. Population EQ / LE = u8 round(unweighted mean over ages 0..89 with frac > 0) (vt[0x88]/[0x90](0,89));
workforce EQ / LE over 20..65. Workforce % = round(100 x sum frac[20..65]).

## 6. Jobs, unemployment, aura
Wl = *(C+0xC8): R valve 3000 *(Wl+0x1C), workers/jobs valve 7000 *(Wl+0x28), R *(Wl+0x14). J = valve-7000
demand (+0x10); Wk = round(pop x sum frac[20..65]); unemployment % = 0 if pop == 0 or J >= Wk; 100 if J == 0;
else (100 Wk - 100 J) / (2 Wk) (integer). Graphs (iface ptrs; object = ptr - 8): Wl+0x2C City Size, +0x44
Nat'l Pop, +0x5C Commerce, +0x74 Industry, +0x8C Unemployment.
Aura: SIMMISC main vtable 0x1003C250; shift *(M+0x14) = 2; grid *(M+0x18) u8 (signed: higher better); city
aura byte M+0xA4. Find via the layer vector *(C+0x94)..*(C+0x98) by vtable (aura main offsets: 0x1003C250 +0,
0x1003C208 +0x1C, 0x1003C1C0 +0x20, 0x1003C190 +0x24, 0x1003C168 +0x28, 0x1003C150 +0x2C).

## 7. Other
Flammability (SIMSERV main vtable 0x1001F2C8, vtables 0x1001F2B0 +0x10, 0x1001F268 +0x14, 0x1001F238 +0x18,
0x1001F220 +0x1C, 0x1001F20C +0x20): grid *(M+0xC) u8 full resolution, lazily filled (0 = not computed).
Crime labels: 0 None, <47 Low, <84 Medium, <122 High, <151 Very High, else Rampant. Land value labels: <35
(0x1C0), 35-74 Low, 75-129 Medium, 130-174 High, 175-224 Very High, >= 225 Astronomical. Valve layer
V = *(budget+0x30): u8 grid V+0x38 (view 0x2724, n*(160-min(v,160))/160), V+0x34 OPEN.
View ids: 0x2711 terrain, 0x2715 traffic, 0x271C aura, 0x271D crime, 0x271E police (L), 0x2720 water, 0x2722
power, 0x2724 valve grid, 0x2726-0x2729/0x272B zones, 0x272C flammability, 0x272D fire (L), 0x2731/32/33/35
air/water/garbage/radiation.

## Open
Pollution bit order on a coal plant; bit 30; power bit on lines; W+0x6C/W+0x70; flag 0x20; V+0x34/V+0x38;
R+0x1EC, R+0x680; strike bytes; approval-rating object; aura sign.
