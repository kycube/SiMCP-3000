# PER-BUILDING DATA (static RE by subagent; saved by main, 2026-10-07)

Main finding: every grid cell points to a simulator agent object O (A = O - 8), not the building. Figures come
from a few agent fields, city-wide simulator fields and static INI tables keyed by the category. Zone buildings
store no population/jobs/age: residents and jobs follow a per-tile formula. Helpers here: q.py, lin.py, xr.py,
classes.py, qtext.py, textuse.py (textuse.txt), props.py, cls73.py, txt_82e0074c.txt (Query text),
agent_layouts.txt.

## 1. Generic agent (CONFIRMED)
[O] vtable (class/module); [O+4] = B14 building geometry iface (building+0x14, SIMGEOM 0x207EDC0E):
[B14-8] occupant id, [B14+8] category (= O vt+0x88), [B14+0x24]/[+0x28]/[+0x2C] size x/y/z, [B14+0x12C] agent
class (property 0x73; default 0x62B9DA80). [O+0x10] packed position x0 = v & 0x7FF, y0 = (v>>11) & 0x7FF,
z = (v>>22) & 0xFF, rotation v>>30. [O+0x14] state dword: low byte 1 occupied/working, 2 abandoned, 4 under
construction, 8 destroyed, 0x10 fire-damaged, 0x20 eaten crops (LIKELY, SC3BuildingLayer.ini
[DefaultBuildingData]); 0x100 covered in garbage; 0x200 historical. Getters A vt+0x4C (state byte), vt+0x54
TestFlag. [O+0xC] low 16 bits refcount; [O+0x18] OPEN.

## 2. Zone buildings
Agent class 0x62B9DA80 (O vtable SIMGEOM 0x1002BBE8) or 0x5A2 (0x1002A578): generic. Density/wealth from the
category: R 3100/3300/3500 low density (low/med/high value), 3700/3900/4100 medium, 4300/4500/4700 high; C
5100/5500 low, 5700/6100 medium, 6300/6700 high; I 8100/8300/8500 dirty, 8700/8900/9100 clean (low/med/high
density), 9300 agriculture; abandoned/construction/rubble/ashes 15100, 15300, 15410/15411, 15420/15421.
Residents/jobs (SIMRCI 0x1002F5AF, only when state byte == 1): for each `valve:supply:demand` of the category in
SC3ValveLayer.ini [AgentValveEffects] add area x supply / area x demand (area = sx*sy). Residents = area x supply
of valve 3000; jobs = area x demand of valve 7000 (civic and utility buildings too). Land value band from the
land-value byte at the tile (<35 Very Low, <75 Low, <130 Medium, <175 High, <225 Very High, else Astronomical).
Powered: PS = [city+0xB8] - 0x14; grid [PS+0xC]; rows [grid+0x10]; bit rows[x][y>>5] >> (y&31). Watered: Wt =
[city+0xBC]; width u16 [Wt+8]; bits [Wt+0x68]; bit y*width + x. Pollution per category: SC3Pollution.ini
[AgentIDModifiers]. No age for zone buildings.

## 3. Civic
Police/fire (SIMSERV, object = O - 0x10; police O vtable 0x1001E680, fire 0x1001E170): O+0x24 u8 coverage
radius (30 / 25), O+0x25/+0x26 max/min coverage, O+0x28 cost (L), O+0x2C funding cost. Crimes/fires are counted
by the Query from the layers in a diamond of that radius. Jail (O vtable 0x1001E430): O+0x24 inmates, O+0x28
funding cost, cells global SIMSERV 0x1002426C (300). SIMRCI civic (object = O - 0x14): monthly funding cost at
school O+0x30, college O+0x30, hospital O+0x34, library O+0x28, museum O+0x24; other figures city-wide in R =
*(city+0xE4) (see layers report). Parks/landmarks/rewards (SIMMISC, O = object + 8): some store a Date Built JDN
at O+0x30 (A vt+0x40).

## 4. Utilities
Power plants (SIMUTIL, P = O - 0x30; coal O vtable 0x10020A68, P vtable 0x10020C48): P+0x04 usage (MWh/month,
C), P+0x08 current capacity (L), P+0x0C nominal (L), u16 P+0x10 overwork months, P+0x18 construction JDN, P+0x1C
max life months, P+0x20 decline age months, P+0x24 u8 OPEN. Age = months since built; current = 0 at max life;
after decline age nominal - nominal*(age-decline)/(max-decline). Waste-to-energy same layout + 0x54..0x60.
Water pump/tower/desalination (object = O - 8, W = O + 0x24): u16 W+0x08 max capacity, W+0x0A current, W+0x0C
usage (m3/month); W+0x18 construction JDN, W+0x1C max life, W+0x20 decline age. Treatment 0x62FD2C9F OPEN.
Incinerator (SIMECO, O = object + 8): O+0x28 current capacity (x 30 x 0.125 t/month), O+0x30 construction JDN.
Landfill: zone tiles; city capacity [Pl+0x468] x 0x7FFF x 0.125 t (layers report says x 0.1).

## 5. Query text
Table 0x82E0074C (448 entries). Query window SIMUI 0x1006260E; message 0x02DC6D7F (title 0x02DCC25E -> O vt+0x124,
body 0xC2DCC228 -> O vt+0x128; do not call those). Agent classes by property 0x73: 62B9DA80/5A2 SIMGEOM +8 zone;
814A0FBD 614A1014 E14A102C C14A1040 A14A106E 414A1097 214A10AE 614A1057 SIMUTIL +0x30 power plants; 2302193A
waste-to-energy; A2FD2580 02FD2C92 C2FD2C98 SIMUTIL +8 pump/tower/desalination; 62FD2C9F treatment; 210D4D78
40FC7753 22EE7A5B SIMSERV +0x10 police/fire/jail; 612A8F75 C2EC529C 2123CB83 E3319EB4 A3319F62 SIMRCI +0x14
school/college/hospital/library/museum; 0345776C C34ACD28 SIMECO +8 incinerator/recycling; SIMMISC +8 parks etc.

## Open (live)
Vtables of a house and a coal plant; state values for occupied/construction/abandoned; residents formula vs
valve 3000 supply; plant fields vs the Query; W+0x0E/0x10, O+0xC high bits, O+0x18; power/water bits on every
footprint tile; library/museum stats; landfill scale.
