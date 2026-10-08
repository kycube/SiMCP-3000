# FEATURES: loans, disasters, preferences, advisor mood, ordinance costs, transit, population window
(static RE by subagent; saved by main)

All static. Addresses = MODULE preferred-VA. C = city = *(STRTSIM 0x10032C9C). thiscall throughout.
B = *(C+0xC4) budget, O = *(C+0xC0) ordinances, DM = *(C+0xD0) disaster manager, T = *(C+0xAC) SimTransit,
R = *(C+0xE4) residential. Helpers in `re/agents/features/`: `q.py` (dis/around/xref/vt), `g.py` (instruction grep
with a linear-disassembly cache in %TEMP%), `ordswitch.py` (emulates the ordinance cost switch -> `ordswitch.txt`),
disassembly dumps `prefs_*.txt`, `ps_listener.txt`, `ps_end.txt`.

## 1. Bonds ("Loans"): NO early repayment exists (CONFIRMED)
The Loans panel (SIMMISC; Budget window COMM 0x025DDC4A handled at 0x1000C31C, command object vtable 0x1003D534)
click handler SIMMISC 0x10025DEE handles only: 0x20 close, **0x3A "Issue Loan"** -> `B vt[0x5C](panel+0x24)`,
**0x3C "Consult Financial Advisor"** -> post {0x724A82DE, 0x628D0C45, 0xBBE}. Amount slider 0x39 (handler
0x10025E8E stores panel+0x24; built at 0x10025986: min 5000, max *(0x10049494) = MaxBondAmt*1000 = 25,000, step
5000, default 5000). Table refresh 0x10025ED6 shows per bond: "Maturity Date Mo/Yr" (rec+0 byte month, +4 year),
"Total" (+0xC), "Amount Owed" (+0x10), "Amount Paid" (+0x14). No repay / pay-off text in the window strings
(0x1B3..0x1B9, 0x23B..0x23D); only SIMMISC touches B+0x550/+0x554/+0x590 and the count +0x554 changes only in
ctor/load, IssueBond (inc 0x10009298) and month end (dec 0x10008148).
Rules (INI [Bonds] MaxBonds 10, MonthlyPaymentPer1K 10, MaxBondAmt 25, BondLifespan 10): IssueBond 0x10009150
(B vt[0x5C](amount)): round down to a multiple of 5000; count < MaxBonds; amount <= 25,000; outstanding
(+0x590 int64) + amount <= vt[0x64] (= 25,000*10 = 250,000). New record (0x1C): +0 byte month, +4 maturity year =
year + lifespan, +8 principal, +0x18 monthly payment = principal*Per1K/1000, +0xC total due = payment*12*lifespan
(1.2x principal), +0x10 remaining = total, +0x14 amount paid = 0; then AddFunds (vt[0x18]).
Month end 0x1000808C: per bond YTD int64 B+0x588 += payment; remaining -= payment, paid += payment; removed (and
outstanding -= principal) when remaining == 0 or month == rec+0 and year == rec+4. B+0x558 + 4*month = dword
monthly bond total. (Funds themselves settle at year end per LIVE_FACTS.)

## 2. Disasters
DM layout (SIMDSTR, vtables +0 0x100325A0, +4 0x10032558, +8 0x10032544, +0xC 0x1003252C):

| field | meaning | conf |
|---|---|---|
| +0x14 set, +0x18 size | disaster instances in state 0 (warning/premonition phase) | CONFIRMED |
| +0x20 set, +0x24 size | **active instances** (DM vt[0x28] returns +0x24) | CONFIRMED |
| +0x31 byte | disasters enabled/registered (mirrors C+0x1F2 via msg 0x0373D8CE; DM vt[0x24] reads, vt[0x20](bool) sets) | CONFIRMED |
| +0x34 city, +0x38/+0x3C map max x / z | | L |
| +0x70 / +0x74 police / fire dispatch helpers (vt[0x44](x,z)) | | L |
| +0x78 budget | | L |
| +0xA0 std::list of state listeners {fn, ctx}; vt[0x2C](fn,ctx) add, vt[0x30] remove | | CONFIRMED |
| +0xA4 byte Emergency Warning active (Emergency menu "Early Warning" COMM 0x02B5AECF -> msg 0x8373D754 -> 0x100076A2) | | CONFIRMED |
| +0x58 byte warning issued while a disaster was pending/active ("with EW") | | CONFIRMED |
| +0xA8 false-alarm count; +0xB8 warning age (ended after MaxEmergencyDuration 8) | | L |
| +0xB4 summed damage $ of finished instances; damage relief 0x1000792E: if > 500 the city gets +0xB4 * (35% with EW, 25% without) / 100 via budget vt[0x1C], then +0xB4 = 0 | | CONFIRMED |
| +0xDC byte sim-ready flag gating the messages | | L |

Set nodes: head = *(set+0); node {+4 parent, +8 left, +0xC right, +0x10 key = instance interface ptr}; head+4 root,
head+8 leftmost; null children (iterator 0x10007E3D). State changes arrive via DM vt[0x0C](inst, state)
0x10007F3D: 0 -> insert into +0x14; 1 -> move to +0x20 (first active posts 0xE31E2463: C vt[0x44](1) disaster mode =
C+0x38 bit 0, special speed; SIMUI disables speed buttons); 4 -> remove, +0xB4 += inst vt[0x34](), the last one
posts 0x231E2493 (end). Every state is forwarded to the listeners.

Disaster instance interface (QI 0x22223BA4; one object per burning building / riot / swarm...), same slots in every
class: vt[0x20]() disaster id (0x621CDA33 fire, 0x42963812 quake, 0x4296380E riot, 0x02963821 tornado, 0x22963800
toxic cloud, 0xE2963828 UFO, 0x13873254 whirlpool, 0x13873255 locusts, 0x13873256 space junk, 0xC4C90997 parade =
an "event" also passing through DM); vt[0x10](int* x, int* z) ret 8 tile location; vt[0x30]() buildings
destroyed/abandoned (%X%); vt[0x34]() damage $ (%Y%) (proved by the Public Safety report builder SIMADV 0x10013A9C,
text "...%X% buildings were destroyed, at a cost of %Y%" CONFIRMED); vt[0x2C]() still running (L); vt[0x18]() owning
disaster's iface; vt[0x24](i)/vt[0x28]() phase table / count.

Per-class memory-only fields (instance vtable: location / count vt[0x30] / damage vt[0x34] / phase):
Fire 0x10032498: +0x10/+0x14 / byte +0x38 != 0 / +0x3C / +4 active byte, +0xC occupant.
Quake 0x100322C8: +0x60>>8, +0x68>>8 / +0x289C / +0x28A0 / +0x28B0 (>=5 done).
Riot 0x10032C98: +0x34/+0x38 / +0x54 / +0x50 / +0x14 != 0 running.
Tornado 0x1003314C: +0x18/+0x1C / +0x80 / +0x7C / +0x50 (5).
Toxic 0x100332C8: +0x14>>8, +0x1C>>8 / +0x58 / +0x54 / +0x30 (4).
SpaceJunk 0x10032FAC: +0x30/+0x34 / +0x70 / +0x74 / +0x78 (>=5).
UFO 0x100334BC: computed (call vt[0x10]) / sum +0x64..+0x70 / +0x7C / +0x74 (>=4).
Locusts 0x1003290C: computed / +0x74 / +0x78 / +0x58 (>=3).
Whirlpool 0x10033638: *(+0x64)->vt[0x20] or +0x48>>8/+0x50>>8 / +0x70 / +0x74 / +0x80 (>=5).
Parade 0x100337B4: +0x34/+0x38.
Static registry map SIMDSTR 0x1003A7B8 (node +0x10 id, +0x14 class id, +0x18 the disaster class's generic iface
(QI 0x021E9CBF = object+0xC)); DM vt[0x34](id) returns it. Fire class keeps a per-building map at Fire+0x6C
(occupant -> instance).

Auto Go To Disasters is NOT C+0x1F3 (CONFIRMED): it is the preference byte PR+0x84 (section 3). SIMADV 0x10013588
(inside the Public Safety disaster-start handler 0x100132CE, DM listener 0x100132A6) reads app vt[0x60]()->vt[0x30]()
and moves the camera only if nonzero (parades always): posts 0x435EE5C0, 0x635EE3C3, 0xE35EE21F, 0xA35EE145(x, z),
then 0x10013CE4. Menu "Goto" (PMSG 0xC30177CA) goes to the same advisor at 0x10013C50, cycling a disaster map at
PS+0x140 (count +0x144, current key +0x14C, lock +0x150), PS = *(C+0x118). City save (SIMCITY 0x1000467F) also
stores PR+0x84 == 1.
C+0x1F3 (LIKELY) = NOT(C+0x38 bit 1); only writers ctor (=1), setter vt[0x50], and 0x10007383 (bit-1 handler of C
vt[0x58]/vt[0x5C] set/clear mode-flag mask) which disables City Properties (0x1000900A) and enables Scenario Goals
(0x10008003) => bit 1 = scenario mode. Public Safety triggers the parade event (DM vt[0x34](0xC4C90997) -> QI
0xA4C68296 -> vt[0x1C]) only when C vt[0x40]() == 1.
Recipe (UI thread, under the city lock, slots 141/142): walk tree *(DM+0x20); per key inst: id = inst->vt[0x20](),
inst->vt[0x10](&x,&z), vt[0x30], vt[0x34]. Pending = tree *(DM+0x14). Emergency Warning = DM+0xA4. Relief pending =
DM+0xB4. Fire count = active instances with vtable 0x10032498.

## 3. Preferences window (SIMUI class vtable 0x100AA5FC, handler 0x10055E07)
Values live in PR = *(app+0xF8), app = *(SC3U 0x4FA86C) (PR vtable SC3U 0x4CFDAC, ctor 0x408A23; saved to
`Apps\SC3.cfg`). SIMUI reaches it as app iface (QI 0xFA2 = app+0x30) vt[0x60] (helper 0x1008E998); audio manager
vt[0x34] (helper 0x1008E95F). PR getters: vt[0x2C] -> PR+0x6C (sound block), vt[0x30] -> PR+0x84, vt[0x34] ->
PR+0x94 (graphics), vt[0x38] -> PR+0xA0 (tips). Apply (OK) 0x100593AC; OK then posts {0x231BBF91, PR, 0, 0} (SIMSPR
listens).

| option (label) | store | control id | live setter / notes |
|---|---|---|---|
| Traffic Visible (0x200) | PR+0x94 dword 3/2/1/0 | radio 0x2F95AEB: AEC=3, AED=2, AEE=1, AEF=Off 0 | C vt[0x164]() (= C+0xCC STRTSIM) ->vt[0x50](v) |
| Sims Visible (0x207) | PR+0x98 2/1/0 | radio 0x2F95AF0: AF1=2, AF2=1, AF3=0 | ...->vt[0x4C](v) |
| Other Animations (0x204) | PR+0x9C 1/0 | radio 0x2F95AF4: AF5 On, AF6 Off | via 0x231BBF91 |
| Show tips at startup (0x293) | PR+0xA0 byte (+0xA4 tip index) | check 0x2F95AF7 | |
| **Auto Go To Disasters (0x21F)** | **PR+0x84 byte (default 1)** | check 0x2F95AF8 | read live at each disaster start |
| 3D sounds (0x291) | PR+0x6C byte (0) | check 0x2F95AFC | |
| Music on (0x153) / volume | PR+0x6D (1) / PR+0x70 (0x400) | check 0x2F95AF9 / slider 0x2F95AFE | audio vt[0x14](0x3EA, vol-or-0, 0,0,0) then (0x3FA) |
| Sound Effects on (0x14F) / vol | PR+0x74 / PR+0x78 | 0x2F95AFB / slider 0x2F95B00 | audio 0x3EB, then 0x3FC |
| Ambient on (0x219) / vol | PR+0x7C / PR+0x80 | 0x2F95AFA / slider 0x2F95AFF | audio 0x3EC, then 0x3FB |
| Screen resolution (0x20B) | list rows 0x2F95B01..B07, scroll 0x2F95B0F | | leave alone |
| Music Choices (0x21A), Preview Score (0x294) | groups 0x2F95AE4 / AE5 | | OPEN |
| new-city defaults | PR+0x85 auto budget, +0x86 disasters, +0x88/+0x8C/+0x90 style ids | written by City Options SIMUI 0x1005EE78 | |

Buttons: OK 0x2F95AD8 (Enter), Cancel 0x2F95AD6 (Esc; restores audio from PR); tabs 0x2F95AD9..ADD. No scroll-speed
or edge-scroll option in the window (INI keys SC3U.ini [Navigation] ScrollMarginFactor, Max/MinPixelsToScrollPerFrame,
ScrollRateInPixelsPerMinute read at SC3U 0x429026..0x429163, L).
Recipe: write the PR field, call the live setter from the table, then MessageSend {0x231BBF91, PR}.

## 4. Advisor mood (CONFIRMED)
A vt[0x50] = 0x1001DCB2: ecx = *(A+0x80) (advice list) -> jmp 0x100018A5, which loops the list nodes; for entries
with byte e+0x13 == 0 (unread / visible) it calls lookup 0x100018F9(id = *(e+4), &mood), sums moods (unlisted ids
give 0 but still count); result = sum / count (unsigned, truncating), 3 when there are no visible entries. SIMUI
stores it at panel model +0x44 (0x100060EF). The lookup re-reads `\Sys\SYS.PAK` each call: section [AdvisorMoods],
key sprintf("0x%08X", id), value atoi; tries AdvisorMoods.INI first, then GoldAdvisorMoods.INI. INI format
`[Admin] Enabled=ON`, then `[AdvisorMoods]` lines `0x000000NN=m`, m in 1..5 (AdvisorMoods ids 1..0x13A; Gold
0x191..0x19D). 1 = good news (e.g. id 1 "Microwave Power Available" = 1), 5 = crisis (id 11 "Power Plant Explodes" =
5). Memory-only recipe: parse both INIs from re/out/syspak_txt; for each adv = *(C+0x104..0x11C) walk *(adv+0x84)
(as in the advisors report); mood = sum(table.get(id, 0)) // n over entries with +0x13 == 0, else 3.

## 5. Ordinance monthly amounts
O vt[0x30](id) = 0x1001ABDD is pure and **ignores enacted status** (CONFIRMED). P = (O+0xC)->vt[0x78]() (O+0xC =
Residential layer, C vt[0x1B8](0xC106C4F5), QI 0x4106C508; P LIKELY population). R = (O+0x10)->vt[0x10]() (layer
0xA0AB89F0 / QI 0x20631788; what R measures is OPEN). div = record+0x24 (100 if 0), LIKELY the 4th field of
Ordinances.ini `id=advisor;year;text;div`. Results (+ income, - expense), from ordswitch.txt:
- most: -(1 + P/div)
- income P/div: Legalized Gambling 0xA0D07129, Parking Fines 0x015B4D1E, Industrial Pollutant Impact Fee 0x02F6E7E2,
  Industrial Waste Disposal 0xA2F917CF
- -(1 + R/div): Earthquake Retrofit 0xC2BF1DD1, Smoke Detectors 0x62BF1DAA, Power Conservation 0x82B9999B
- extra term: Youth Curfew + O+0x50, Pro-Reading + O+0x5C, Trash Presort + O+0x60 (zeroed in ctor; writers OPEN)
- 0 (free): Leaf Burning Ban, Subsidized Mass Transit, Farmer's Market
Record +0x20 (CONFIRMED): SetEnacted 0x1001AA77 on enact sets +0x20 = vt[0x30](id) and adjusts totals O+0x68
(income) / O+0x6C (expense); on repeal adjusts back and sets +0x20 = 0. Monthly refresh 0x10019FC7 (from O vt[0x88])
recomputes +0x20 and the totals for all records with available && enacted. So +0x20 is current for enacted ones (as
of the last month) and 0 otherwise. The Ordinances window (SIMUI 0x100021D4..0x1000221E) calls vt[0x30](id) for every
row, so its "estimated" costs = vt[0x30]. Recipe: O vt[0x30](id) (UI thread), or +0x20 for enacted ones.

## 6. Transit (SimTransit T = *(C+0xAC), global *(SimTransit 0x1001FDB8))
Fares (CONFIRMED): the trip code (0x100073C2..) adds per-tile fares into float T+0x100 at rates T+0xCC rail,
T+0xD0 subway, T+0xD4 bus (STTraffic.ini PerTileTransitIncome Rail 10 / Subway 10 / Bus 5; Subsidized Mass Transit
lowers fares by 35%). Month end (0x1000927E): T+0x104 = T+0x100, T+0x100 = 0. T vt[0xA4]() = int64(T+0x104) -> budget
ledger B+0x3A0 + 8*m ("Transit Fares"), YTD B+0x400. T+0x100 = this month's running total.
Funding / costs: T+0xDC roads monthly cost (roads*2 + highways*30); T+0xE0 mass transit monthly cost (sum of
station vt[0x10]() + rail*1 + subway*20); T+0xE4 / +0xE5 road / transit funding % (vt[0x9C] / vt[0xA0]); float
effects +0xFC / +0xF8. T+0x108 strike state (1 = strike; vt[0xB4]); vt[0xBC] = strike risk from underfunding.
Stations: T+0xD8 std::list of station interfaces (QI 0xA2EAB10D) with only vt[0x10] monthly cost and
vt[0x14](funding%); **no ridership/capacity fields** (CONFIRMED); passengers/day is the query value T+0x60 density
x 4.3 (layers report).
Airport/seaport: nothing stored; query text computed on the fly (L): airport (SIMMISC 0x1000F49C) "Air Traffic"
level from the RCI valve layer's commercial demand (valve 5000) vs the airport category 12310 (0x3016) count,
"On Time Flights %" from the aura layer; seaport 0x1000FC5D: industrial valve 8000 vs category 12330 (0x302A).

## 7. Population window (SIMUI 0x10020C35..0x10023E00)
Three graph pages, each a curve over Resident Age 0..89; nothing new beyond what we have: Education 0x100212D4
(R vt[0x88](0,89) population EQ, vt[0x84] = vt[0x88](20,65) workforce EQ); Life Expectancy 0x10022A13
(vt[0x90](0,89), vt[0x8C] = vt[0x90](20,65)); Population 0x1002358B (vt[0x78] total pop, vt[0x7C] =
vt[0x80](20,65) workforce fraction * 100 + 0.5). No commute-time data; no health/education breakdown by age beyond
the per-age EQ/LE arrays. Aside: an "Approval Rating" graph exists at owner+0x88 (owner = SIMMISC object with iface
vtable 0x1003C1E4, LIKELY the aura simulator); value OPEN.

## Open questions (live)
1. Set PR+0x84 = 0, light a fire: camera stays? C+0x1F3 == 0 inside a scenario?
2. During a fire: DM+0x24 == number of burning buildings; inst vt[0x10] matches the burning tile; vt[0x34] grows?
3. Early Warning with no disaster pending -> DM+0xA8 increments?
4. Ordinances: identify R layer 0xA0AB89F0; who writes O+0x50/+0x5C/+0x60.
5. Preferences: music-choices list field meaning and PR+0xA8/+0x8A8/+0x938...; SC3.cfg written at exit or on OK?
