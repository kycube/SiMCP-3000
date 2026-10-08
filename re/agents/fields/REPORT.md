# Open fields, round 5 (static RE by subagent; saved by main; SC3U GOG 2.0.949)

All 8 field groups resolved except: approval graph value -> %, agent O+0xC bits 16..31 / O+0x18 meaning, W+0xC0
semantics (partly). Addresses are preferred-base VAs. C = city. P/M as in the earlier reports. Helpers in
`re/agents/fields/` (`h.py` wraps the layers `hl.py` + LIN path to linear disassembly; `vcall.py` finds virtual calls
by slot; `fstart.py` finds the enclosing SEH-prologue function start). Linear disassemblies of the DLLs are in the
scratchpad `lin\`.

## 1. Pollution / garbage (SIMECO; P = *(C+0xD4), main M = P-0x1C)
- **Cell *(P-4) bit 30 = salt water (CONFIRMED).** Getter P vt[0x50](x,y) 0x10008D90, setter vt[0x90](x,y,b)
  0x10008ECD (posts msg 0xDA6DD2CB); bit 31 = vt[0x54]/vt[0x94] (posts 0x5A6DD1D1). Writer: the terrain object SIMDIRT
  (city+0xA4) - SetWaterLevel(x,y,level,isSalt) = SIMDIRT 0x10006220 (iface vt[0x8C]) keeps a per-vertex water level
  (byte grid +0x38) and a salt bit array +0x48; a rebuild pass (0x10005230 etc.) first clears bit 30 everywhere, then
  sets each tile from the OR of its 4 corner salt bits (the setter writes the cell at tile>>1, so the cell keeps the
  value of tile (2cx+1, 2cy+1)). Used by Query SIMUI 0x10010ED1: water tile (terrain vt[0x54]) + bit 30 -> "Salt
  Water" (string 195) else "Fresh Water" (194); SIMDIRT 0x1000F4D4 / 0x10018ED6 test bit 30 at the four map-edge
  midpoints to find coastal edges. Bit 30 is also set on shore land cells: test together with a water tile.
- **Garbage grid bit 15 = landfill tile (CONFIRMED)**: 0x100093EC(x,y,add) with this = P reads the zone type via
  P+0x24; zone 0x11 (landfill) -> set bit 15 and P+0x468++ (clear and -- on removal). P vt[0x104] tests, vt[0x108](x,y,b)
  sets.
- **P+0x15C (int64) = garbage IMPORTED from neighbours, last 12 months (CONFIRMED)** (neighbour deal type 5
  ImportGarbage; Berlin has one with Upper Marazan); included in produced (P+0x154); not one of the "goes to" slices
  of the SIMUI garbage chart. Feed: sim step (main vt[0x50], 0x10008249) calls M+0x4C (neighbours)->vt[0x8C](5,&info)
  and adds info+8 / 30 to both month accumulators P+0x42C (produced) and P+0x434 (imported).
  Full ledger: 7 current-month int64 accumulators, rolled at month end (main vt[0x48]) into int64[12] histories
  (slot = month just ended); year totals = sum of the 12 slots:

| what | month acc | int64[12] history | 12-month total (int64) |
|---|---|---|---|
| produced (history = produced - P+0x464) | P+0x42C | P+0x18C | P+0x154 |
| imported (deal type 5) | P+0x434 | P+0x1EC | P+0x15C |
| exported (deal type 4) | P+0x43C | P+0x24C | P+0x164 |
| recycled | P+0x444 | P+0x2AC | P+0x16C |
| incinerators (L) | P+0x44C | P+0x30C | P+0x174 |
| waste-to-energy (L) | P+0x454 | P+0x36C | P+0x17C |
| landfill | P+0x45C | P+0x3CC | P+0x184 |

  P+0x464 (u32) = garbage left uncollected (capped 5000, global 0x10020270). Disposal order (0x100094A2): list at
  M+0xBC, then list at M+0xB8, then landfill valve, then export deal (type 4), rest -> P+0x464. Which list is WTE vs
  incinerators is LIKELY only (M+0xBC entries have the WTE interface: vt[0x34] capacity, vt[0x38] remaining).
  P+0x148 float = recycled fraction; P vt[0xB4] = round(P+0x148*100) (recycling query compares with
  OptimalPctReduction 45).
- **Landfill fullness (CONFIRMED)**: V = *(P+0x13C) valve (class vtable SIMECO 0x1001BDFC, id 0xA2C9E821,
  registered in the valve layer, min/max +-2e9). V vt[0x2C] = `mov eax,[ecx+0x10]; ret` (pure getter). V+0x10 = free
  landfill capacity in garbage units (SIMRCI landfill developer 0x1001ACCB adds/removes per-tile capacity on zoning via
  V vt[0x44]; SIMECO subtracts 32767 when a landfill tile disappears 0x1000861F; placing n units on tiles SIMRCI
  0x10019F30 does V+0x0C -= n and V+0x10 -= n). V+0x0C = garbage delivered but not yet placed on tiles (SIMECO
  deposits with V vt[0x40] (+n)). V vt[0x30] = clamp(V+0x10 - V+0x0C) = space still available. Query 0x1000D544:
  capacity (tons) = P+0x468 * 32767 * 0.125 (float 0x10020274 is 0.125, not 0.1); % full = ceil(100 * (cap -
  min(cap, V+0x10)) / cap). Used = cap - V+0x10. Garbage on tiles = garbage grid bits 0..14 on bit-15 tiles.

## 2. Water (SIMUTIL; W = *(C+0xBC), dim = u16 W+8, bit index y*dim+x)
- **W+0x6C = bit per water-consuming building, at its footprint centre tile ((x0+x1)/2, (y0+y1)/2) (CONFIRMED).**
  Set/cleared by 0x1000DFF3 / 0x1000E054 on agent add/remove (msgs 0x826CB9B6 / 0x426CB9B3). Every building passing
  agent vt[0x54]==1 except pumps 12810, towers 12840 and desalination 12830 (treatment 12820 does count). 13,770 in
  Berlin = number of buildings that need water.
- **W+0x40 = bits whose watered state CHANGED in the last pass (CONFIRMED).** Water pass 0x1000E940 (ret 0x1000EF66):
  at start W+0x40 = copy(W+0x68) (0x1000B804) and W+0x68 cleared; at end W+0x40 ^= W+0x68 (0x1000B7D8 at 0x1000EF39) -
  hence only 199 bits.
- **W+0xC4 / W+0xC0 (code read, meaning LIKELY)**: a temporary copy of W+0x6C has served consumers cleared during
  distribution; W+0xC4 = popcount(temp) = buildings without water; if W+0xC4 > 0: W+0xC0 = popcount(W+0x6C) = total
  consumers; else W+0xC0 = 100 if any consumer exists (so served % = 100 * (C0 - C4) / C0 works either way). vt[0x50]
  out param 4 = W+0xC0, param 5 = W+0xC4.

## 3. Traffic (SimTransit; T = *(C+0xAC))
- **Network flag 0x20 in u16 grid *(T+0x5C) = Subway<->Rail transfer station tile (category 12361) (CONFIRMED).**
  Station add (0x10005A8D) ORs 0x10 plus: bus 12210 -> 1, train 12230 -> 4, subway 12360 -> 8, subway-rail 12361 ->
  0x2C (4|8|0x20); remove (0x10005FB7) clears. Other bits LIKELY: 0x40 from occupant flag 0x200000; 0x80/0x100/0x4000
  from occupant vt[0x18]/[0x20]/[0x40]; 0x400/0x800 from T+0xF4->vt[0x58](1 or 4, x, y) (road / highway); 0x1000 rail
  variant, 0x2000 subway variant.
- **Strike byte T+0x108: 2 = normal, 0 = strike threatened, 1 = ON STRIKE (CONFIRMED).** State machine 0x1000929A
  (periodic transit step): from 2, if funding T+0xE5 < MinFundingForNoStrike (70) and T+0xE0 > 0, with chance
  (70 - funding) * 0.5 % (StrikeChanceAtZeroFunding 35/70) -> 0 (msg 0xE3067BF3); from 0: still underfunded -> 1
  (msg 0x6306796B) else -> 2 (0x030679AE); from 1: T+0x10C months on strike counts up, ends at >
  MaxLengthofStrikeInMonths (24, STTraffic.ini) or when funding restored -> 2. vt[0xB4] = (T+0x108 == 1); vt[0xB8]
  forces a strike unless state is 2. T+0xE5 = transit funding % (setter vt[0xA0]); T+0xE4 set by vt[0x9C] (fares, L).
  Berlin's 2 = no strike.

## 4. Valve layer V = *(budget+0x30): Density Data Map
- **V+0x38 = per-tile "density" map of last month; V+0x3C = this month's map being built (CONFIRMED).** Both map
  objects (vtable SIMRCI 0x1004CF58): grid = *(map+0xC) {+4 W, +8 H, +0xC column ptrs}, value u8 rows[x][y], full
  resolution (dims from city vt[0xCC]/[0xD0]). Agent valve applier 0x1002F5AF: for each working building over its
  footprint tiles, valves 3000/5000/8000 add the supply per tile (residents for R, C or I units) and valve 7000 adds
  the jobs demand per tile, clamped to 255 (e.g. R 3100 adds 23/tile; C 5100 adds 18 + 17). Monthly (main vt[0xC],
  0x1002EFE8): V+0x38 = V+0x3C, then V+0x3C cleared.
- **V+0x34 is NOT a grid**: a service object (SIMRCI 0x1003D02D) used as vt[0x24](valveId, category) to filter
  buildings; passing buildings add area*supply to V+0x4C / +0x50 / +0x54 (R 3000 / C 5000 / I 8000), rolled monthly
  into V+0x40 / +0x44 / +0x48 (getters main vt[0x28] / [0x2C] / [0x30]) (CONFIRMED).
- UI: window SIMUI 0x10049180, title string 0x115 "Density Data Map" (group 0x029541F4), binds view 0x2711 (terrain)
  and view 0x2724; legend 0x242 "High"/"Low"; painting n * (160 - min(v,160)) / 160.

## 5. Residential R = *(C+0xE4)
- **R+0x1EC float[90] = health points (HQ) per age (CONFIRMED).** Reset (0x1002532E): HQ[a] = max(0, (LE[a] - 50) *
  1.1125) (HQ[0] = 16.69 at LE 65). Monthly (0x10024BBD): HQ grows by the health bonus or decays * 0.999, then LE[a] =
  R+0x4BC[a] = 50 + HQ[a] * 0.8989 (capped 89). The displayed "life expectancy" (vt[0x90]) averages R+0x4BC. EQ R+0x84
  capped at 150.
- **R+0x67C / R+0x680 = total library / museum capacity (CONFIRMED)**: sum of facility vt[0x10] ("PopServed") over the
  education facility map R+0x54 by type: 0 school -> desks +0x670, teachers +0x684; 1 college -> +0x678, +0x688; 2
  library -> +0x67C; 3 museum -> +0x680. SC3Tune.ini Library PopServed 41000, Museum 83000; both serve ages 25..(89).
  R getters vt[0x6C] = +0x67C, vt[0x70] = +0x680.
- Library query (SIMRCI 0x10007F76): "Funding Cost" = O+0x28; "Books Systemwide" = 19*EQwork + 10*R+0x67C +
  13*schoolGrade(R+0x660) + year%17 - 52; "Books in Circulation" = min(pop, EQwork*Books/303 + dayOfYear%17); "Grade"
  from funding * min(100, 100*R+0x67C/pop).
- Museum query (0x100091xx): "Attendance (last year)" = 83000*pop/(R+0x680+1) if R+0x680 > pop else 83000; plus a
  Grade line and "Dinosaur Bones" (flavour, from year/staff).

## 6. Building agents
- O+0xC bit fields (init 0x03000000; SIMGEOM agent vtable 0x1002BBE8): bits 0..15 refcount; 16..23 byte O+0xE
  (vt[0x58] get, vt[0x104] set) OPEN; bit 24 vt[0x6C]/[0x70] OPEN; bit 25 vt[0x74]/[0x78] OPEN; bits 26..30 5-bit flag
  set (vt[0x28] any, [0x2C] test, [0x30] get, [0x34] set, [0x38] clear) OPEN; bit 31 vt[0xF8]/[0xFC] OPEN.
- O+0x18 = AddRef'd pointer = *(B14+0x30), obtained as B14->vt[0x4C]() when the agent is placed (A vt[0x18] =
  0x10024197, A = O-8); released in A vt[0x20] and the destructor; the agent forwards calls to it (vt[0x20](A+4,x),
  0x10024583). The building's (L) owner/lot object; meaning OPEN. O+0x1C / O+0x20 lazily cached lookups. O+0x14 =
  state.
- **Water treatment** (class 0x62FD2C9F, object 0x4C, Tt = O+0x24 = obj+0x2C, iface vtable SIMUTIL 0x100201F8; LIKELY,
  offsets CONFIRMED): Tt+8 (O+0x2C) current treatment capacity per day (OptimalPollutionCap 60000, declining with age);
  Tt+0xC date object (built JDN Tt+0x10); Tt+0x14 (O+0x38) amount treated this month (vt[0x3C] adds); vt[0x38] =
  max(0, cap*30 - used); Tt+0x1C (O+0x40) u8 flag (vt[0x24] sets); life 840 / decline 768 months.
- **Recycling center** (SIMECO 0xC34ACD28, object 0x44, Rc = O+0x24, iface vtable 0x1001B5D0) (CONFIRMED): O+0x28
  current % reduction (45, declining linearly from DeclineAge 810 to MaxLifespan 900 months; 0 if not working); O+0x2C
  current population served (50000, same decline); date object O+0x30; u8 flag O+0x38. Query "Milk Containers
  Processed" = round(pop * sum frac[0..4]) * O+0x28 / 100.
- **Waste-to-energy** (P = O-0x30; garbage iface at P+0x54, vtable 0x100221B8; power-plant type 8) (CONFIRMED): P+0x58
  current garbage capacity per day (OptimalGarbageCap, declines with age); P+0x5C garbage burned this month (vt[0x3C]
  adds); P+0x60 last month's burned (rolled 0x1000A01F); vt[0x38] = max(0, cap*30 - P+0x5C).
- **Water buildings W = O+0x24** (CONFIRMED): u16 W+0x0E source type: 2 tower, 3 pump, 5 desalination (set by add
  handlers via vt[0x50]); u16 W+0x10 intake state written back monthly (0x1000F74D): pump 0 = water within 1 tile,
  1 = water only within 2 tiles (capacity * 20%, WaterPumpDistanceFactor, L), 3 = no water (capacity 0); desalination:
  salt water nearby -> 0, else 3.

## 7. Power P = *(C+0xB8), main M = P-0x14
- **P+0x2D0 (vt[0x64]) = number of consumer buildings that got power in the last pass (CONFIRMED)**: cleared at pass
  start (vt[0x44], 0x10004CC0), incremented per powered consumer (M+0x2E4++ at 0x1000506A). Same pass: P+0x2CC = number
  of consumer buildings; P+0x2C8 per-consumer demand byte grid; P+0x2D8 consumption (sum agent vt[0x5C]); P+0x2DC
  (vt[0x68]) working plants; P+0x2E0 (vt[0x6C]) nuclear plants (type 5).
- **int[10] P+0x29C = rolling 12-month energy produced per plant type (MWh) (CONFIRMED)**: ring P+0xB8 int[12][10],
  month index P+0x298; 0x10004132 adds each plant's output = round(capacity * load) at index plant vt[0x4C](). Type
  index: 0 = neighbour power deal (bought, L), 1 coal, 2 fusion, 3 gas, 4 microwave, 5 nuclear, 6 oil, 7 solar, 8
  waste-to-energy, 9 wind (class factory 0x1000C0BC -> ctor -> vtable+0x4C; consistent with the pie chart "Annually
  Averaged Electricity Usage by Type", SIMUI 0x10021E4E, string 0x28A).

## 8. Approval rating
- **No separate approval object; the aura layer owns the "Approval Rating" graph (CONFIRMED).** Aura main M: SIMMISC
  vtable 0x1003C250 (find in the layer vector by vtable); init 0x10002226 with this = M+0x20. Pointers M+0x34 city,
  +0x38 service object (0x1003216B), +0x3C police, +0x40 fire, +0x44 crime, +0x48 pollution, +0x4C zone, +0x50
  ordinances, +0x54 residential, +0x58 occupant manager (C+0x84). M+0xA8 = graph interface (object = ptr - 8; 0xF0
  bytes, iface vtable 0x10041B78), name 0x1D2 "Approval Rating"; vt[0x60](0x104) sets G+0x60 = 0x104.
- Computation: the aura scan (~0x10003040) averages <= 16 terms per cell, clamps to +-127, writes the cell; scans with
  step 16 (M+0xB4 / M+0xB8, phase M+0xB0); sums M+0xA0 += value*terms, M+0x9C += terms. Every 16 phases
  (0x10002B98): M+0xA4 (s8) = M+0xA0 / M+0x9C, both reset. M+0xA4 = city aura. Monthly (0x10002BCB): graph
  vt[0x6C](M+0xA4 + 127), so stored values are 0..254; yearly (vt[0x74]) and decade (vt[0x7C]) entries rolled from the
  graph's own averages.
- UI label 0x28D "Approval Rating %s%%". The code turning the 0..254 value into a % was not found (OPEN).

## Recipes (memory reads only)
1. Salt water at (x,y): (rows = *(*(P-4)+0xC))[x>>1][y>>1] >> 30 & 1, on water tiles.
2. Landfill: V = *(P+0x13C); free = *(V+0x10); pending = *(V+0x0C); cap = *(P+0x468) * 32767; used% = ceil(100 *
   (cap - min(cap, free)) / cap); tons = units * 0.125.
3. Garbage year totals (int64): P+0x154 produced, +0x15C imported, +0x164 exported, +0x16C recycled, +0x174 / +0x17C
   burned, +0x184 landfill.
4. Water: consumers = popcount(W+0x6C); unwatered = *(W+0xC4); changed tiles = W+0x40 bits; served % = 100 * (C0 -
   C4) / C0, C0 = *(W+0xC0).
5. Transit: strike = byte T+0x108 (1 on strike, 0 threatened, 2 normal); months on strike *(T+0x10C); funding %
   byte T+0xE5.
6. Density map: map = *(V+0x38); grid = *(map+0xC); value = ((u8**)*(grid+0xC))[x][y]. Last-month R/C/I totals
   V+0x40 / +0x44 / +0x48.
7. Residential: HQ[a] = float R+0x1EC[a]; LE[a] = R+0x4BC[a]; library capacity *(R+0x67C), museum capacity
   *(R+0x680); library/museum query numbers per section 5 (year / day of year from city+0x138).
8. Agents (O = agent iface): water type u16 *(O+0x24+0xE), intake *(O+0x24+0x10); treatment cap *(O+0x2C), used
   *(O+0x38); recycling % *(O+0x28), served *(O+0x2C); WTE (P = O-0x30) cap *(P+0x58), this month *(P+0x5C), last
   month *(P+0x60).
9. Power: powered consumers *(P+0x2D0); consumers *(P+0x2CC); MWh over 12 months per type: int P+0x29C[0..9]
   (index map in section 7).
10. Approval: aura M (by vtable); s8 *(M+0xA4); graph G = *(M+0xA8); current-month value = aura + 127; history in
    std::deque at G+0x78 / +0xA0 / +0xC8 (months / years / decades), or call the pure getters G vt[0x24] (latest) and
    vt[0x28] (int[12]).

## Still open
- Graph value -> displayed approval %.
- Agent O+0xC bits 16..31 meanings; what the O+0x18 object is.
- Which disposal list is incinerators vs WTE (LIKELY as given).
- P+0x29C index 0 = neighbour-bought power (LIKELY).
- W+0xC0 "100" sentinel semantics: check live.
