# SIMULATION STATE: demand, population, services, statistics (static RE by subagent; saved by main)
Addresses `MODULE preferred-VA`; C = *(STRTSIM 0x10032C9C); thiscall. Helpers here: unpak.py, ini2txt.py (-> ini\),
classes.py (classes_out.txt), who.py, vtdump.py, scencmds.py, layerids.py, writes.py, getteruse.py, funcs.py.
Main lever: SCENARIO.DLL script getters (cmdGetPopulation, cmdGetSurplusPower, cmdGetCrimeValue, cmdGetLandValue,
cmdGetAura, ...) read layer pointers copied from the city by setup SCENARIO 0x10007C10 (handler this = setup - 4);
"SCN" = confirmed by one of those handlers.

## 0. City getters and layer lookup (CONFIRMED)
Plain getters SIMCITY vtable 0x10013260 vt[0x11C..0x1D8] -> C+0x84..C+0x124 (vt[0x150] C+0xB8, [0x154] C+0xBC,
[0x158] C+0xC0, [0x15C] C+0xC4 budget, [0x16C] C+0xD4, [0x170] C+0xD8, [0x17C] C+0xE4, [0x188] C+0xF0, [0x144] C+0xAC;
[0xCC]/[0xD0]/[0xD4] W/H/?). Layer list std::vector<cISCLayer*> at C+0x94/C+0x98; C->vt[0x1B8](layerId) (SIMCITY
0x10005CE4) returns the layer whose vt[0x3C]() == id (layer interface: obj+4/+0x10/+0x14/+0x20); vt[0x1BC](id, iid,
void**) + QI; vt[0x1C0] count; vt[0x1D4](msg*, visitor) broadcast.
Layer ids: Residential 0xC106C4F5, Commercial 0x60F1E6FB, Industrial 0x4106CF1F, Valve 0x80F1E6D3, Land value
0xC0AB8A88, Zone 0xC0AB8A56, Crime 0xA0AA9DAE, Police 0x80ABF2BE, Neighbors 0x82937B60, World 0x411BDDDA, Fire
0xC0F42262, Flammability 0xC144ACA9, Power 0xE0AFDF68, Water 0x02BF0033, Pollution 0x00AAA1BB, Traffic 0x029CA804,
Aura 0x0259C03F, Budget 0xA11BCC54, Ordinances 0xE1193C2A, Weather 0xC2ED2A04.

## Class identification (CONFIRMED)
| Pointer | Vtable | clsid / size | Simulator |
|---|---|---|---|
| C+0xB4 | SIMRCI 0x1004D1E0 (= obj+0x10) | 0x409FF3BA / 0x2D0 | Zone layer |
| C+0xE4 | SIMRCI 0x1004C99C | 0xA106C520 / 0x6D8 | Residential: population, ages, EQ/HQ, strikes |
| C+0xE8 | SIMRCI 0x1004C208 | 0x20EC9849 / 0x20 | Commercial |
| C+0xEC | SIMRCI 0x1004C4A4 | 0xA106CF3D / 0x24 | Industrial |
| C+0xF0, budget+0x20 | SIMRCI 0x1004C624 (obj+0x1C) | 0x60A2966E / 0xE0 | Land value |
| budget+0x30 | SIMRCI 0x1004CEE4 | 0x60A42F32 / 0x58 | Valve layer = RCI demand |
| C+0xD8 | SIMSERV 0x1001EA38 (obj+0x1C) | 0x20A7AE7F / 0xE0 | Crime |
| C+0xDC | SIMSERV 0x1001F46C (obj+0x1C) | 0x00ABF2EC / 0xF0 | Police |
| C+0xE0 | SIMSERV 0x1001EE04 (obj+0x1C) | 0xA0F42214 / 0xE0 | Fire |
| C+0xB8 | SIMUTIL 0x10020550 (obj+0x14) | 0x20AFDF44 / 0x2FC | Power |
| C+0xBC | SIMUTIL 0x10022944 | 0x82BF0042 / 0xE8 | Water |
| C+0xD4 | SIMECO 0x1001B984 (obj+0x1C) | layer 0x00AAA1BB | Pollution |
| C+0xC0 | SIMMISC 0x10040F3C | 0x41193C4B / 0x78 | Ordinance manager |
| C+0xC4 | SIMMISC 0x1003C550 | 0xC11BCC75 / 0x598 | Budget |
| C+0xC8 | SIMMISC 0x10041324 | 0xE11BDDF6 / 0xC8 | World layer (ExternalJobDemand, EconomicPhases) |
| C+0xF4 | SIMMISC 0x10040BF4 | 0x02910E84 / 0x204 | Neighbors + neighbor deals |
| C+0xF8 | SIMMISC 0x10041000 | 0xE2ED2A04 / 0x98 | Weather |
| C+0xAC | SimTransit 0x1001A368 | 0x029CA806 / 0x110 | Traffic |
Others: SIMSERV 0x61448030 Flammability, 0x40FC7753 FireStation, 0x210D4D78 PoliceStation, 0x22EE7A5B Jail; SIMUTIL
0x814A0FBD, 0xE14A102C ... power plants, 0x02FD2C92/0xA2FD2580/0xC2FD2C98 water bldgs, 0x62FD2C9F treatment; SIMRCI
0x612A8F75 School, 0xC2EC529C College, 0x2123CB83 Hospital, 0xE3319EB4 Library, 0xA3319F62 Museum; zone developers
0x619BA64E R, 0x41A3ADC1 C, 0xE1A53B30 I, 0x82348DE5 Landfill; 0xC0F1EC40 valve; 0x?22C9Dxx/0x?D3FDxx
ZoneDeveloperRules; SIMMISC 0x?3127xxx LIKELY ordinances. (The JDN seen at "SIMMISC 0x10040F3C obj+0x2CC" must be in
another object: that class is 0x78 bytes.)

## 1. RCI demand (CONFIRMED)
Valve (base vtable SIMRCI 0x1004CC14, size 0x44; residential subclass 0x1004CB84): +0x08 id; +0x0C supply last
month; +0x10 demand last month; +0x14/+0x18 accumulating supply/demand; +0x1C/+0x20 persistent external
supply/demand; +0x24 max (2000); +0x28 min (-2000); **+0x2C value int32**; +0x34/+0x38 float modifiers; +0x3C cap %.
vt[0x8C] (0x10042E89): target = clamp(demand - supply, min, max) + (f34 + f38)*max, capped at (100-cap)%*max; moves
by <= 7% of (max-min) per step. Monthly roll-over vt[0x78] (0x10042E62). vt[0x14] posts 0x426840A0 {id, v*1000/max
or v*1000/|min|} (do not call). SIMUI meter (0x10065329): x 0.001, R 3000 / C 5000 / I 8000, range +-1.0.
Valves: R *(*(C+0xE4)+0x24) = 3000 (+0x28 = 3001 amenity); C *(*(C+0xE8)+0x18) = 5000 (+0x1C 5001, +0x14 valve
layer); I *(*(C+0xEC)+0x1C) = 8000 (+0x20 8001, +0x14 valve layer); 7000 = workers/jobs. Valve layer V =
*(budget+0x30): std::map<id, valve*> head V+0x18, count V+0x1C (node +4 parent, +8 left, +0xC right, +0x10 key,
+0x14 valve*); V->vt[0x14](id, 0x00F1EC30, void**) get. Getters vt[0x28] supply, [0x2C] demand, [0x30] value.
Building contributions: SC3ValveLayer.ini AgentValveEffects. No wealth split in demand.

## 2. Population, jobs, graphs
Population (SCN cmdGetPopulation, %POPULATION%) = *(*(*(C+0xE4)+0x24)+0x0C) or res->vt[0x78]() (SIMRCI 0x10025199).
C/I jobs LIKELY supply (+0x0C) of valves 5000/8000. R = *(C+0xE4): float[90] by age: +0x84 EQ, +0x354 population,
+0x4BC HQ; vt[0x80](minAge, maxAge) pop sum (float); vt[0x7C] ages 20..65; vt[0x88]/[0x90](a, b) avg EQ/HQ (int);
vt[0x84]/[0x8C] same 20..65. Strikes bytes R+0x650..0x652. R+0x664..0x68C 11 dwords (vt[0x48..0x70]) unknown.
Graph object (0xF0, ctor SIMRCI 0x100418BF), interface at +8 vtable 0x1004DE78: vt[0x0C] name, [0x24](int*) latest,
[0x28](int[12]) months, [0x34](int[10]) years, [0x40](int[10]) decades; std::deque<int> at +0x78/+0xA0/+0xC8.
Residential graphs R+0x690/694/698 (iface = ptr + 8). Layers hand out graphs on message {0xE41D8FEE, 0xE404E938} via
layer->vt[0x10](msg, visitor); SIMUI snapshot export 0x1000D6D7 (callback 0x1000D7AD) enumerates with C->vt[0x1D4].

## 3. Services and utilities
Power P = *(C+0xB8) (SCN): int P+0x5C capacity (vt[0x58]); P+0x2D8 consumption (vt[0x5C]); P+0x2D4 unpowered
buildings (vt[0x60]); P+0x2D0 unknown (vt[0x64]); int[10] P+0x29C capacity per plant type (vt[0x50](i), total
vt[0x4C]). Surplus = capacity - consumption.
Water W = *(C+0xBC) (SCN): int64 W+0xB0 supply, int64 W+0xB8 consumption, W+0xC0 unknown, W+0xC4 unwatered count;
all from W->vt[0x50](a1, &sup64, &dem64, &c0, &c4) (SIMUTIL 0x1000F066).
Crime avg byte *(C+0xD8)+0xA8 (SCN, SIMSERV 0x10009CD8); fire iface vt[0x58] same function (avg coverage LIKELY);
police iface vt[0x50] -> +0xB0, vt[0x58] -> byte +0x1C. Health/education in residential layer (EQ/HQ, strikes).
Garbage supply/demand: OPEN (garbage is a pollution type in SIMECO; landfill zones; neighbor deal exports).

## 4. Averages and per-area maps
Land value avg byte *(C+0xF0)+0xA4 (SCN). Aura (SCN cmdGetAura): L = C->vt[0x1B8](0x0259C03F); L->vt[0](0x4259C018,
&A); byte A+0x88. Traffic T = *(C+0xAC); T->vt[0x5C](x0,y0,x1,y1, byte* out, 3) (SimTransit 0x10006DB9) avg density
(SCN). Pollution Pl = *(C+0xD4): vt[0x78] int Pl+0xD0, vt[0x7C] int Pl+0xD4, vt[0x80] u16 Pl+0x138 (cmdGetPollution
types 0/1/2; air/water/garbage GUESS). Funds budget+0x38 (int64); total debt budget+0x590 (int64, vt[0x60]).
Map-layer base: +0x0C width, +0x10 height, +0x14 shift, +0x18 grid* (+4 cols, +8 rows, +0xC column ptrs); value
byte col[x>>shift][y>>shift]; land value/crime main = iface - 0x1C. Traffic T: per-tile maps T+0x5C (u16 network
flags), T+0x60 road density, T+0x64/T+0x68 (rail/other).

## 5. Zone development
Zone layer Z = *(C+0xB4) - 0x10; grid *(Z+0x0C), byte zone type per tile; iface->vt[0x14](x, y, int*); per-type
counts dword[23] at iface+0x40 (vt[0x44](type)). Types: 0 none, 1-3 R low/med/high, 5-7 C, 9-11 I, 13 military, 16
spaceport, 17 landfill, 14/15 seaport/airport (GUESS order). Zone developers pick agent type by density and
land-value band (e.g. low-density R: 3100 LV 1-75, 3300 LV 76-150, 3500 LV 151-255); industry D/C/A. Rules gate
development; demand from valves; SC3Tune.INI MaxDistFromTransport, AnarchyFactor, *RedevelopmentPct. Per-lot
building/abandonment storage: OPEN.

## Recipes
1. Demand: valve as above; v = +0x2C, max +0x24, min +0x28; meter = v/max (v>=0) else v/|min|.
2. Population: *(*(*(C+0xE4)+0x24)+0x0C) or SIMRCI 0x10025199 (this = *(C+0xE4)).
3. Power P+0x5C/+0x2D8/+0x2D4. 4. Water W+0xB0/+0xB8 (int64), +0xC4.
5. Land value byte *(C+0xF0)+0xA4; crime byte *(C+0xD8)+0xA8; pollution +0xD0/+0xD4/+0x138; debt budget+0x590;
   aura via layer 0x0259C03F.
6. Graphs: graph->vt[0x28](int[12]) on interfaces at R+0x690.. (ptr + 8). 7. Any layer: C->vt[0x1B8](id).
All getters are side-effect free; do not call valve vt[0x14].

## Open questions (live)
Valve +0x2C vs RCI meter; population vs status bar and sum R+0x354[0..89]; coal plant -> P+0x5C up, P+0x2D4 down;
pump -> W+0xB0; pollution after industry/landfill; zone grid index order; residential graph names.
