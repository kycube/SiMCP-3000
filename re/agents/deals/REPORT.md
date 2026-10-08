# DEALS: neighbor deals and business deals (static RE by subagent; saved by main, 2026-10-07)

Addresses `MODULE preferred-VA`; thiscall unless noted. C = confirmed from code, L = likely, O = open.
Helper files here: h.py, deal_tables.txt (petition id -> deal type -> queue param, connection types),
petitions.txt, n_code.txt, util_code.txt, budget_adv.txt, pm_fmt.txt, ui_nb.txt.

## Corrections to earlier notes (C)
- Record bytes +0x34..+0x48 (N+0x84..+0x98) are per-neighbor CONNECTION COUNTS, not deal quantities.
- N vt[+0x60](ct, nb) is HasConnection (count > 0).
- Deal terms live in Deal objects in two lists on N: N+0x24 active, N+0x28 pending proposals.
- Petition 181 is a SELL-power request (grouped with 179/180, deal type 1) despite its "Offers" heading.

## 0. Enums, objects, N vtable
Deal type dt: 0 BuyPower, 1 SellPower, 2 BuyWater, 3 SellWater, 4 ExportGarbage (we pay them),
5 ImportGarbage (they pay us). Rate globals POWER_BUY 0x10049EA8, +4 POWER_SELL, WATER_BUY, WATER_SELL,
GARBAGE_EXPORT 0x10049EB8, GARBAGE_IMPORT 0x10049EBC.

Connection type ct (SIMNTWRK 0x10008F24 picks the occupant and $ cost, prompt 0x251 "connect for $X"):
| ct | network | neighbor occupant | record count | point set |
|---|---|---|---|---|
| 1 | road | 16017 | +0x34 | N+0x1BC |
| 2 | rail | 17006 | +0x38 | N+0x1B0 |
| 3 | power line | 12102 | +0x40 | N+0x1D4 |
| 4 | highway (2 tiles) | 17207 | +0x44 | N+0x1E0 |
| 5 | water pipe | 17310 | +0x3C | N+0x1C8 |
| 6 | subway | 17410 | +0x48 | N+0x1EC |
The $2,000 is the connection occupant's build cost (budget vt+0x54). Point key = (x<<16)|y (O: exact axes).

N = *(city+0xF4) (SIMMISC vtable 0x10040BF4): +0x0C city; +0x10 occupant counter (vt[0x60](12330) Seaport
count, L); +0x14 terrain (vt[0x50](x,y) edge tile is water, L); +0x18 power sim; +0x1C water sim; +0x20 our
population source; +0x24 active-deal list, +0x28 pending list (std::list head=*(N+0x24); node {next, prev,
Deal*}); +0x2C lock (vt[1] lock, vt[2] unlock); +0x50+i*0x54 neighbor records; +0x1A0/+0x1A4 map W/H;
+0x1A8 penalties accrued not yet charged; +0x1B0..+0x1F4 six std::sets of connection points (0xC each);
+0x1F8 day, +0x1FC month, +0x200 year.

N vtable: +0x4C 0x10016678 InitNeighbors; +0x50 AddConnection(ct,x,y); +0x54 RemoveConnection; +0x58
HasConnectionAt(ct,x,y); +0x5C EdgeOf(x,y) -> nb or 4; +0x60 HasConnection(ct,nb); +0x64 0x100170E6
ProposeRenegotiation(dt); +0x68 0x1001761C ProposeNewDeal(nb,dt,cap); +0x6C GetPendingInfo(dt,&info) -> bool;
+0x70 GetPending(dt,&Deal*) (AddRef); +0x74 RejectPending(dt); +0x78 0x10017D45 AcceptPending(dt); +0x7C
RemoveActive(dt) no penalty; +0x80 0x10017F89 CancelActive(dt); +0x84 HasActive(dt); +0x88 HasPending(dt);
+0x8C GetActiveInfo(dt,&info) -> bool; +0x90 GetActive(dt,&Deal*); +0x94 PopBrokenDeal(&Deal*); +0x98
FindNeighborForDeal(dt); +0x9C 0x10017B64 CanDealWith(nb,dt); +0xA0 ReportDelivery(dt,amount); +0xA4
State(nb); +0xA8 CountNeighbors; +0xAC Pop(nb); +0xB0 GetName(nb,IGZString*); +0xB4 SetName; +0xB8 GetMayor;
+0xBC..+0xF0 per-ct counts/sums; +0xF4 0x10018F95 MonthlyIncome; +0xF8 0x10019000 MonthlyExpense; +0xFC
TakePenalties (reads AND CLEARS +0x1A8 - never call).

Deal object (0x54, ctor 0x100190EA, vtable SIMMISC 0x10040E08): +0x04 neighbor-name cRZString; +0x18 second
string (text group 0x209E6378); +0x2C quantity (%X%; 0 for buy types until a delivery is reported); +0x30
monthly $; +0x34 byte nb; +0x35 byte dt; +0x38 months elapsed (-1 broken/cancelled); +0x3C minimum monthly
charge (%W%); +0x40 penalty (%Z%); +0x44 rate per 1000 units (%Y%); +0x48 date object; +0x4C agreement JDN
(%YEAROFDEAL% = its year); +0x50 refcount. vt[0x68](&info) exports 0x28 bytes: +0 name*, +4 second string*,
+8 qty, +0xC monthly, +0x10 byte nb, +0x11 byte dt, +0x14 months, +0x18 min, +0x1C penalty, +0x20 rate,
+0x24 year.

## 1. Where proposals are created (C)
Generator: Utilities advisor (city+0x104) 0x1001A85F, called from advisor update 0x10019AE6 (vtable
0x1003101C slot +0x48 on util+4) when byte util+0xA0 is set; stats refresh 0x10019B78 first (L monthly).
Queued via 0x1001DD03(id,key,1) -> PM 0x1002087A -> create 0x100208AC(id, param=key, 0, 0, b11=1).
param is a constant per deal type (below), not a neighbor index. Tokens attached by 0x1001BD76.
Util fields: +0x134 power capacity, +0x138 consumption, +0x130 demand (L), +0x13C shortage metric (L), +0x144
surplus, +0x150 i64 water capacity, +0x148 i64 water use, +0x158 i64 surplus, +0x164 water shortage (L),
+0x1B8 garbage capacity (L), +0x1D8 i64 garbage produced (L), +0x1E0 i64 spare (L), +0x180 population, +0xE0
MINIMUM_DEAL_POPULATION 5000, +0xD8 LOW_TREASURY_LEVEL 10000, +0x1E9+dt "new deals enabled" byte (default 1;
util vt[0x20](dt|-1) disables, vt[0x24] enables).

New offers per dt (no active deal of that dt, enabled, nb = N.vt98(dt) != 4; vt98 starts at a random
neighbor and returns the first with no deal of the same commodity and CanDealWith); id = one of three (rand):
| dt | condition | ids | key | cap |
|---|---|---|---|---|
| 1 sell power | consumption < 40% capacity, surplus > 1000, pop > 5000 | 179/180/181 | 0x63248EA7 | surplus |
| 0 buy power | demand >= 80% capacity or +0x13C > 30 | 172/173/202 | 0x83248FD7 | - |
| 3 sell water | use < 40% capacity, surplus > 1000, pop > 5000 | 185/186/187 | 0xC3249313 | water surplus |
| 2 buy water | use >= 80% capacity or +0x164 > 30 | 165/166/167 | 0x232493D6 | - |
| 5 import garbage | produced < 60% capacity, spare > 500, pop > 5000 | 191/192/193 | 0x232494CF | - |
| 4 export garbage | produced >= 90% capacity | 196/197/247 | 0x63249696 | - |
Each: N.vt68(nb,dt,cap), vt6C(dt,&info), queue. Treasury is not a condition. Queued but CanDealWith now
fails -> N.vt74(dt) + withdraw (queue 0x100232B7). Conditions fail -> vt74(dt). Sell-power pending and
treasury < 10000 -> Budget advisor message 37 "Deal To Sell Power".
"Cancel it" petitions when an active deal's months > 24: 177 (dt0), 170 (dt2), 195 (dt4) (b14 = 1).
Renegotiation at months >= 60 (nothing pending, vt64 ok): 175 (dt0), 248 (dt1), 168 (dt2), 189 (dt3),
199 (dt4), 194 (dt5); vt64 fails -> renews (months = 0); months > 66 -> pending new terms auto-accepted.
Broken deals (vt94 loop 0x1001BC6C): connection gone 230 power / 227 water / 249 garbage; still connected
(cancelled / supply failed) 239 power / 240 water; informational. 200 never created by deal code (O).

## 2. Terms (N.vt68 0x1001761C) (C)
Fails if HasActive(dt) or HasPending(dt), not CanDealWith, or an opposite-direction deal for the same
commodity with the same neighbor. rate = RATE[dt] + rand(5): 8..12 power/water, 5..9 garbage; buy types
raised to at least an opposite deal's rate with another neighbor. k = max(1, P*pct/100000): sell types P =
neighbor population, pct 25; buy types P = our population, pct 10. units = k * (500 power / 200 water / 650
garbage); sell power/water units = min(units, cap); round up to a multiple of 1000.
Sell (1,3,5): qty = units, monthly = units*rate/1000, penalty = 25*monthly.
Buy (0,2,4): qty = 0 (filled monthly), est = units*rate/1000, monthly = min = max(est, MIN 30/25/20),
penalty = 25*est. Renegotiation vt64 recomputes from current populations (buy: new rate > old; sell: rate =
max, fails if qty shrinks or nothing changes). BASE_DEAL_PENALTY written, never read.
Tokens: %NEIGHBOR% name of info.nb; %Y% rate for dt 0/2/4, monthly $ for 1/3/5; %W% minimum; %Z% penalty;
%X% qty (garbage: qty * SIMECO vt[0x100]() float, rounded); %YEAROFDEAL% info year.

## 3. Answers (C)
PM answer 0x1002096A routes deal ids to Utilities advisor 0x1001C1A8(id, choice); choice 1 = Button1.
| petitions | 1 | 2 |
|---|---|---|
| new offers and new terms | N.vt78(dt) accept | vt7C(dt) + vt74(dt): remove active WITHOUT penalty, drop pending |
| 233-238 Terms (Cancel/Keep) | vt80(dt) then vt7C(dt) | nothing |
| 170/177/195 (Cancel/Keep) | vt80(dt) | nothing |
vt78: pending -> active, months 0, date today, record byte +0x4C+dt = 1. vt80: months >= 60 removed free,
else months = -1 and N+0x1A8 += penalty. vt7C clears +0x4C+dt for all neighbors. Monthly tick 0x10018CD5:
months++; connection gone -> vt80. Month-end: income N.vtF4 = sum rate*qty/1000 over sell deals -> B+0x470;
expense N.vtFC (penalties) + N.vtF8 = sum max(rate*delivered/1000, min) over buy deals -> B+0x408.

## 4. Neighbor record N+0x50+i*0x54 (C)
+0x00 city name, +0x14 mayor (cRZString 0x14 each); +0x24 ? (0); +0x28 population; +0x2C cap 4,000,000;
+0x30 state (1; 0 if the mid-edge tile was water: sea edge, garbage deals need a Seaport); +0x34..+0x48
connection counts (table above); +0x4C..+0x51 active-deal byte per dt.
Edge from tile (0x10016F13): x == 0 -> nb 0; y == 0 -> 1; x == W-1 -> 2; y == H-1 -> 3. Neighbors Map UI
slot s -> nb (s+1)&3. CanDealWith: dt0 power count > 0; dt1 also a powered point on that edge; dt2 water
count > 0; dt3 also a watered point; dt4/5 state 0 needs a Seaport, state 1 road/rail/highway or Seaport.
Yearly population drift (month 1): 12x pop += rand(3800)-1200; 1.5% halves; floor 1000.
Berlin: Upper Marazan +0x51 = 1 (active ImportGarbage), counts road 5 rail 1 water 2; Greyleaf highway 2;
Bradford Falls road 1. Deal code uses the counts (shipped cities may have stale counts vs point sets).

## 5. Discuss Deal (SIMUI) (C)
Button 0x43068566 -> 0x10054CE5: nb = (sel+1)&3, the row's dt; needs PM vt[0x28](dt,&disp) (active deal);
MessageSend {0x724A82E0, -1, dt, 0} -> handler slot +0x34 0x10003E62 opens the modal petition dialog with id
233-238; buttons call PM answer. Nothing is queued.

## 6. Business deals (Budget/Finance advisor F = city+0x108) (C)
INI `Name = building;year;monthly;petition`: 19001 Toxic Waste Plant (16), 19002 Gigamall (206), 19003
Casino (149, pays only with Legalized Gambling 0xA0D07129), 19004 Prison (210).
Record (0x38, vtable SIMADV 0x100303F0) list at F+0xA4: +0x04 petition, +0x08 building, +0x0C year, +0x10
name, +0x24 monthly, +0x28 byte placed/active, +0x30 building object, +0x34 byte enabled.
Offered (L monthly, 0x1000548D): counter F+0xFC ++ while funds (F+0xB8 i64) < TREASURY_LOW 1500 else --;
offer when funds < 1500, population F+0xF8 > 1000, no petition key 0xA2FFF341 queued, counter >= 3; one random
eligible record (year, enabled, not placed/unlocked, casino needs gambling). F vt[0x1C](bld) forces an offer.
Accept (0x10005F27): City Planner (city+0x10C) vt[0x14](building) makes it available in Rewards &
Opportunities; the player places it. After 16, petition 17 (Agree -> re-lock) and 18 (Destroy Plant).
Pay: F vt[0x0C] sums monthly over placed, working records -> ledger B+0x4E8.

## Recipes
1. Pending deal terms: walk N+0x28 (lock N+0x2C vt[1]/vt[2]); or N.vt[0x6C](dt,&info). Current deal:
   N.vt[0x8C](dt,&info). Build the text from text.py with the token rules.
2. Memory: head=*(N+0x28|0x24); node=*head; d=*(node+8): +0x34 nb, +0x35 dt, +0x2C qty, +0x30 monthly,
   +0x38 months, +0x3C min, +0x40 penalty, +0x44 rate, +0x4C JDN.
3. Accept/reject: SIMADV 0x1002096A(pm, id, 1|2).
4. Existing deals: N.vt[0x8C](dt,&info) for dt 0..5; flags N+0x9C+nb*0x54+dt; income N.vtF4(), expense
   N.vtF8() (idempotent); pending penalties dword N+0x1A8 (never call vtFC).
5. Cancel: 0x1002096A(pm, {0:234,1:233,2:236,3:235,4:238,5:237}[dt], 1). Penalty unless months >= 60.
6. Connections: counts record+0x34..; N.vt58(ct,x,y); N.vt5C(x,y) -> nb; N.vt9C(nb,dt) deal possible.
8. Business: F.vt[0x1C](bld) force offer; F.vt[0x20](bld) active; F.vt[0x0C]() monthly income; answer
   0x1002096A(pm, 16|149|206|210, 1), then place the building from the reward picker.
9. util.vt[0x24](dt|-1) enables / vt[0x20] disables new neighbor offers.

## Open
Cadence of the advisor updates (L monthly); whether supply failure is charged; petition 200; record+0x24;
power-sim vt54/vt60 meanings; petition queue token list layout (0x10023046).
