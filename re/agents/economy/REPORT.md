# ECONOMY: budget, taxes, departments, bonds, ordinances, deals (static RE by subagent; saved by main)
Addresses `MODULE preferred-VA`; vt[+X] = vtable byte offset; args = stack args (thiscall).
Supporting files here: ordinances.txt (45 ordinances: id, advisor, year, name), strings_window.txt,
strings_all.txt (decoded Res\Text\ENGLISH\*.IXF), scripts ixf.py, ords.py, vtd.py, d.py, cls.py, items.py,
fielduse.py, scmd.py, pak.py.

**Funds anti-tamper:** month-end SIMMISC 0x10007D88 resets funds (+0x38) to the shadow copy (+0x40) if they differ.
Always use SetFunds (budget vt[+0x0C]). **SIMECO.DLL is ecology** (pollution, garbage, power), not economy; economy
is SIMMISC (budget, ordinances, neighbor deals) and SIMADV (departments, business deals, deal proposals).

## Reaching the objects (CONFIRMED)
city = *(STRTSIM 0x10032C9C); simulators created via GZCOM CreateInstance (SIMCITY 0x10005E62..0x10006634, helper
0x10006655); trivial getters (no AddRef). Don't GetClassObject (creates a new instance).
| What | City field | Getter | clsid / iid | vtable |
|---|---|---|---|---|
| Budget | +0xC4 | vt[+0x15C] 0x10002B79 | C11BCC75 / E11BCC69 | SIMMISC 0x1003C550 |
| Ordinances | +0xC0 | vt[+0x158] | 41193C4B / 41193C3A | SIMMISC 0x10040F3C |
| Neighbor deals | +0xF4 | vt[+0x18C] | 02910E84 / C2910E7D | SIMMISC 0x10040BF4 |
| Finance advisor (business deals) | +0x108 | vt[+0x1B0] | 828D0C49 / 628D0C45 | SIMADV 0x10030310 |
| Utilities advisor (deal proposals) | +0x104 | vt[+0x198] | 422E28E8 / 022E288E | SIMADV 0x100310B4 |
| SIMECO | +0xD4 | vt[+0x16C] | C0A81498 / 80A814AC | SIMECO 0x1001B984 |
Budget Init (SIMMISC 0x100067C7) caches: +0x14 city, +0x18 ordinances, +0x1C SimTransit, +0x20/+0x28 SIMRCI, +0x24
neighbor deals, +0x2C SIMINIT, +0x30 RCI tax-base object; 0x10007A59 sets +0x4E0 = Finance advisor.

## Budget object (size 0x598, factory 0x1002A6A5, ctor 0x10005129) CONFIRMED
QI 0x10007D2B: IID 1/0xE11BCC69 -> this; 0x58D/0x206C6E7C/0x81C0CB7C -> this+4 (sim iface vt 0x1003C508). +8 base vt
0x1003C5C0 (5 slots). Main vtable 0x1003C550:
| vt | addr | args | meaning |
|---|---|---|---|
| +0x0C | 0x100051ED | 2 | SetFunds(int64) (writes +0x38 and +0x40) |
| +0x10 | 0x10005204 | 0 | GetFunds() edx:eax |
| +0x14 | 0x10008946 | 1 | Spend(u32) -> bool (fails if funds < amount; msg 0x229A8A90) |
| +0x18 | 0x100089A8 | 1 | AddFunds(u32) |
| +0x1C | 0x100089ED | 1 | add to ledger row +0x338 current month (if byte +0x10) |
| +0x20 / +0x24 | 0x10008A3E / 0x10008AE1 | 0 | income YTD / estimated full year |
| +0x28 / +0x2C | 0x10008CED / 0x10008D92 | 0 | expense YTD / estimated full year |
| +0x30 / +0x34 | 0x10008630 / 0x100086A1 | 1 | Register/UnregisterItem |
| +0x38 | 0x100086DC | 2 | FindItem(id, item**) -> bool |
| +0x3C | 0x100092B9 | 1 | recompute item cost |
| +0x40 | 0x1000933D | 1 | RefreshItem(item): cost = % x full / 100 |
| +0x44 / +0x48 | 0x10008734 / 0x10008710 | 1 | item amount (int64) by id / by ptr |
| +0x4C | 0x1000520B | 1 | GetTaxRate(0 R, 1 C, 2 I) -> AL |
| +0x50 | 0x1000892F | 1 | tax demand effect float[B+0x208 + rate*4] (ST0) |
| +0x54 | 0x10008FBE | 1 | building placement cost(building id) |
| +0x58 | 0x10008FA0 | 1 | zone/terrain cost |
| +0x5C | 0x10009150 | 1 | IssueBond(amount) -> bool |
| +0x60 | 0x1000521F | 0 | outstanding bond principal (+0x590) |
| +0x64 | 0x100092AA | 0 | max total bonds |
| +0x68 / +0x6C | 0x1000522C / 0x10005236 | 1/0 | set/get "free building" cheat flag (byte +0x11) |
Month end SIMMISC 0x10007D88 (anti-tamper, + taxes, ordinances, deals, tolls; - departments, ordinances, deals,
bond payments; byte +0x12 set -> funds clamped at -99,999). Tax income per zone 0x100090A7.

## Budget layout (the 0x24-byte "named entries" in LIVE_FACTS were a misreading)
0x1003C434 is the cRZString vtable (0x14 bytes: +4 begin, +8 end, +0xC cap). +0x4C cRZString "Funds" = label of
funds graph object at +0x48. +0x60 department std::map header, +0x64 item count (6 live). **+0x70/+0xF8/+0x180
three 0x88-byte tax rows R/C/I**: +0x00 name, +0x14 dword 3000/5000/8000 (valve param), +0x18 RCI demand valve*,
**+0x1C byte tax rate (default 7)**, +0x1D byte max (22), +0x20 int64[12] monthly tax income, +0x80 int64 YTD.
Ledger rows int64[12] by month (index month-1) then YTD int64 at +0x60: income +0x2D0 ordinances, +0x338 other,
+0x3A0 tolls/fares, +0x470 neighbor deals, +0x4E8 business deals; expense +0x268 ordinances, +0x408 neighbor deals,
+0x588 bond payments YTD. +0x208 float[23] tax->demand table. Department map node (0x98): +0x10 id; value at +0x18:
+4 item*, +8 funding % (byte), +0x10 int64 monthly cost, +0x18 int64[12] spend, +0x78 int64 YTD.
Bonds: +0x550 -> array of 0x1C-byte records, +0x554 count.

## Departments (budget items created by SIMADV; QI IID 0x223E2B67; item ptr = object+8)
Police 0xA2963983, Fire 0x62963928, Public Health 0x42922A6C, Education 0x02922A5D, Roads 0x8290F605, Mass Transit
0xC290F609 (names text group 0x029541F4). Item vtable SIMADV 0x10030B30: +0x0C GetID, +0x14 full cost (int64), +0x1C
name (cRZString*), **+0x20 SetFundingPct(byte) (0x10011A94)**, **+0x24 GetFundingPct -> AL**, +0x28 advisor IID.

## Deals
Neighbor deals (SIMMISC 0x10040BF4): 4 neighbor records of 0x54 bytes at N+0x78 (+0x50/+0x64 names via vt[+0xB0]/
vt[+0xB8], +0x80 state byte, +0x84..+0x98 six deal quantities). vt[+0x60](type 1..6, neighbor 0..3) HasDeal; type
-> field 1 +0x84, 2 +0x88, 5 +0x8C, 3 +0x90, 4 +0x94, 6 +0x98 (commodity mapping LIKELY, untested). Monthly income
vt[+0xF4]; costs vt[+0xF8], vt[+0xFC] (reads and clears +0x1A8). Proposals from the Utilities advisor:
cmdEnableNewNeighborDeals = city->vt[0x198]()->vt[+0x24](arg); vt[+0x20] LIKELY disable.
Business deals (Finance advisor): Toxic factory 19001 (1950, 400), MegaMall 19002 (1970, 300), Casino 19003 (1915,
350; pays only with Legalized Gambling 0xA0D07129), Prison 19004 (1900, 250); list at F+0xA4; vt[+0x0C] monthly
income; vt[+0x10](id) find; **vt[+0x1C](id) OfferDeal** (= cmdOfferBusinessDeal); vt[+0x20](id) IsActive;
vt[+0x24](id, bool) enable/disable. Accept/decline functions for proposals: NOT found (petitioner path, see events).

## Ordinances (SIMMISC 0x10040F3C) CONFIRMED
45, keyed by 32-bit id (ordinances.txt; names text group 0xC29A6083 instance 0x78+). std::map at O+0x28; record +0
category, **+4 enacted byte, +5 available byte**, +0x20 cached monthly amount. O+0x68 total income, O+0x6C total
expense. vt: +0x0C IsEnacted(id) 0x1001A98B; +0x10 IsAvailable(id); +0x18 CountEnacted; **+0x1C SetEnacted(id, bool)
0x1001AA77** (posts 0xC2C09554; no availability check); +0x20 MakeAvailable(id); +0x30 GetMonthlyAmount(id) 0x1001ABDD
(+ income, - expense); +0x34/+0x38 expense/income totals.

## Bonds ("Loans" in UI)
INI MaxBonds 10, MonthlyPaymentPer1K 10, MaxBondAmt 25, BondLifespan 10. IssueBond 0x10009150: rounds down to
multiple of 5000; count < MaxBonds, amount <= global 0x10049494, outstanding + amount <= vt[+0x64]; record +0 month,
+4 maturity year, +8 principal, +0xC total due, +0x10 remaining, +0x18 monthly payment (principal*10/1000);
AddFunds(amount). No payoff entry point found.

## Recipes (UI thread)
1. B = [city+0xC4]; O = [city+0xC0]; N = [city+0xF4]; F = [city+0x108].
2. Funds int64 B+0x38; tax rate zone z byte B+0x8C + z*0x88; month m tax income int64 B+0x90 + z*0x88 + 8*m; totals
   B vt[+0x20/+0x24/+0x28/+0x2C]; departments B vt[+0x38](id, &item) then item vt[+0x24] (%), vt[+0x14] (cost).
3. Set funds B vt[+0x0C](lo, hi); charge B vt[+0x14](amount) -> bool.
4. Tax rate: write byte B+0x8C + z*0x88 (clamp to byte B+0x8D + z*0x88); valve = [B+0x88 + z*0x88];
   valve vt[+0x6C](dword at B+0x208 + 4*min(rate, 22) as raw float bits) (copies slider handler SIMMISC 0x10023F42).
5. Department funding: item vt[+0x20](pct) then B vt[+0x40](item).
6. Ordinance: O vt[+0x1C](id, 1|0); check O vt[+0x10](id) first.
7. Bond: B vt[+0x5C](amount) -> bool. 8. Business deal: F vt[+0x1C](id) offer; F vt[+0x20] active.
9. UI: Budget window COMM 0x025DDC4A; Ordinances PMSG 0x724A82D7.

## Open questions (live)
Sliders vs B+0x8C/+0x114/+0x19C (max 22 or 20?); recipe 4 + one month vs slider change; Police vt[+0x20](50) and
month-end cost scaling; write only B+0x38 then month passes (reverted?); accept a neighbor deal in UI (which of
N+0x84..+0x98 changes); write breakpoint on N+0x80 to find accept/decline; B vt[+0x5C](10000) -> count 1, +10,000,
payment 100.
