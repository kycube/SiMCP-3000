# EVENTS: advisors, petitioners, ticker, disasters, scenarios, rewards, cheats (static RE by subagent; saved by main)

Addresses `MODULE preferred-VA`. city = *(STRTSIM 0x10032C9C). Helper scripts in this folder (q.py, ixf.py,
cheats.py, scanimm.py, advmap.py, scn_cmds.txt = every scenario command name + handler).

## 1. Advisors and petitioners
Advisor slots (CONFIRMED: ctor vtable store + Init loads Sys\Advisor-*.INI + its "force <Name> to say" cheat):
| City off | Vtable +0 | ctor | Advisor |
|---|---|---|---|
| +0x104 | SIMADV 0x100310B4 | 0x10017C48 | Utilities (Gus) |
| +0x108 | 0x10030310 | 0x10003C83 | Budget (Mortimer) |
| +0x10C | 0x1003056C | 0x10006712 | City Planner (Constance); QI iid 0xC28D0B6E; city->vt[0x1A8]() |
| +0x110 | 0x10030A18 | 0x1000F16F | Environment (Karen) |
| +0x114 | 0x10030884 | 0x1000C94D | Health/Education "Demographics" (Randall) |
| +0x118 | 0x10030CCC | 0x10011C7F | Public Safety (Maria) |
| +0x11C | 0x10030EFC | 0x100153E3 | Transportation (Moe) |
| +0x120 | 0x10031504 (+4 0x100314D4, +8 0x1003148C) | 0x1001E556 | PetitionerManager (PM), PetitionerManager.INI |

Pending petitions (CONFIRMED): Q = *(PM+0x28); L = *(Q+4); head = *L; node = *node until == head; node {+0 next,
+4 prev, +8 entry*}; Q+0x0C lock (vt[1]/vt[2]). Entry 0x1C bytes (ctor 0x100243F4): +0x00 petition id (= string
index in every Sc3StringsPetitioner* table), +0x04 param, +0x08 ticker handle, +0x10/+0x11(arg5)/+0x14(arg3)/
+0x15(arg4) bytes, +0x16 pending flag. Queue: 0x100230B0 IsQueued(id); 0x10022FD2 Enqueue(entry*) (posts ticker
link type 0x724A82D6); 0x100231B6 Remove(id); 0x10024033 (id, choice) records answer. PM vt slots 5/6/7
(0x10021B51, 0x10021B63 (1 arg), 0x10021B7C (2 args)) forward to Q (LIKELY GetCount/GetAt).
Create: SIMADV 0x100208AC thiscall(PM, id, param, b14, b15, b11) ret 0x14 (false if queued); wrapper
0x10020892(id, param, b14, b11). PM message handler 0x10021A27: message 0xA4C68296 (data1 id, data2 b11) queues.
**Answer: SIMADV 0x1002096A = PM slot 9 (+0x24), thiscall(PM, id, choice) ret 8**: records, removes, reaction
headline 0x10021180(id, choice) (0 = none), switch(id-1) (0..0x12E, table 0x10020F71) applies effects via
advisors at PM+0x0C..+0x24, +0x3C. choice LIKELY 1 = Button1 (accept), 2 = Button2 (reject).
Petitioner text tables (index = id 1..250; holidays 0x249B17xx use 300..305; Vinnie 215): Heading 0xC26DD29B,
Name 0x826DD2D0, Message 0xC26DD2AB, Button1 0xA26DD23B, Button2 0xE26DD247, Reaction1 0xE26DD2FA, Reaction2
0x226DD30B, Advice 0xE26DD125, Ticker 0x026DD322, TickerX 0xE27EBF4D, TickerY 0xE27EBF70. No Button text =
informational. Advisor message tables: Heading 0x825ADC5A, Message 0x225ADC6B, Ticker 0xC25B11C3 (1..314; MBE
401..413), used at SIMADV 0x10001440 / 0x10002429; advisor panel SIMUI 0x10005602; SIMUI listens for
0x724A82D1..0x724A82DD. Where each advisor keeps pending advice: OPEN.

## 2. News ticker
Post (CONFIRMED, SIMCITY 0x10007635): message server MessageSend (vt+0x0C) with {0x82684130, &item, 0, 0}; item:
+0 0, +4 table id, +8 string index, +0x0C cIGZString* override or 0, +0x10..+0x1C link (+0x10 type). 0x82684131
LIKELY remove. Owner: SC3U.exe ticker window, clsid 0x82F5E9E4, factory 0x420330, size 0x180; vtables +0x00
0x4D0F4C, +0x04 0x4D0D64 (handler 0x4213DB), +0x120 0x4D0D40 (ticker iface; vt[0x10] AddItem 0x421C2D). Find by
dword pair (0x4D0F4C, 0x4D0D64). One std::list per category: head ptr obj+0x13C+4*cat, nodes {next, prev, entry*},
max 0x40 each; category from style map obj+0x124 via 0x422BCC(table, idx, &style), default 5. Entry 0x4C bytes
(vt 0x4D3E08, ctor 0x443D0D): +0x04 seq, +0x0C cIGZString* text, +0x24/+0x28 colours, +0x34..+0x40 link.
Lock obj+0x15C. IXF text files (Res\Text\<LANG>\*.IXF): magic D7 81 C3 80, 20-byte records (table, index, type
0x2026960B, offset, size); data = u32 len + Latin-1; tokens %YOURCITY% %YEAR% %YOURNAME% substituted at post time.
Live headlines: table 0x42C1ED2D idx 100 "%YOURCITY% Founded In %YEAR%", 102/107/112 "The Simulator Is Paused";
random headlines table 0xC2498F0E.

## 3. Disasters (SIMDSTR)
DM = *(city+0xD0) = city->vt[0x168]() (vt SIMDSTR 0x100325A0, ctor 0x10007AB5). DM->vt[0x34](id) (0x10008417)
looks up global map SIMDSTR 0x1003A7B8; QI(iid), call start slot, Release (vt[8]) (CONFIRMED from scenario
cmdStart*):
| Disaster | id | iid | start | scenario handler |
|---|---|---|---|---|
| Earthquake | 0x42963812 | 0xE3024E82 | vt[0x14](float 0..1, bool) | 0x1000AA2F |
| Fire | 0x621CDA33 | 0x634FD3BC | vt[0x10](x, z) | 0x1000AAF3 |
| Locusts | 0x13873255 | 0xC5326356 | vt[0x10](n) | 0x1000AB97 |
| Riot | 0x4296380E | 0x0303B198 | vt[0x0C](a,b,c) | 0x1000AC11 |
| Space junk | 0x13873256 | 0x24889F6F | vt[0x14](a,b) | 0x1000AD3E |
| Tornado | 0x02963821 | 0x83EF8E33 | vt[0x0C](...) | 0x1000AE04 |
| Toxic cloud | 0x22963800 | 0xE475EAD4 | vt[0x0C](a,b,c) | 0x1000AFEC |
| UFO | 0xE2963828 | 0x43024DED | vt[0x10](n) | 0x1000B0BB |
| Whirlpool | 0x13873254 | 0xE3135E82 | vt[0x14](a,b) | 0x1000B135 |
Menu disasters/dispatch: SC3U.exe 0x411523 tool factory (vtable slot at 0x4D0300, 3 args) turns a command id into
a map-placement tool: Fire 0xC26CE54D ctor 0x411E5C; Tornado 0x626CE901 0x411F0D; Riot 0x02FE87A7 0x41206F;
Locusts 0x447F1E42 0x412333; Space debris 0x447F1E43 0x4123E4; Earthquake (LIKELY) 0x22FE8786 0x411FBE (all size
0xAC); dispatch police 0x029A52DD 0x412787; fire 0x229A528C 0x4125F7; plane 0xA5354652 0x412917 (size 0x110).
Unpaired ctors 0x412120, 0x4121D1, 0x412282, 0x412495, 0x412AA7 (UFO/Toxic/Whirlpool/Early Warning).
Disasters enabled (CONFIRMED via cmdEnableDisableDisasters 0x10006D29): set city->vt[0x9C](bool) (SIMCITY
0x10007D10) writes byte city+0x1F2; read city->vt[0x98](). +0x1F1 set by vt[0x94] (LIKELY auto-goto disasters).
DM->vt[0x20](bool) (0x100082DA) LIKELY emergency mode; DM getters +0x31 (byte), +0x24, +0xDC (byte) unconfirmed.

## 4. Scenarios (SCENARIO.DLL)
Global *(SCENARIO 0x1001EB44) (= city+0x100), vt 0x1001A64C; slot 4 returns byte +0x09 (LIKELY running); slot 5
0x10009FFB (1 arg) LIKELY load/start; slot 6 on +0x938; +0x8E4 sub-object. `.snr` scripts run by an interpreter.
Goals: cmdAddGoal 0x100058D0, cmdMarkGoalStatus 0x10008662 (goal map +0x984), cmdGoalStatusIs 0x1000799F,
cmdAllGoalsMet 0x10005A1A, cmdGetMonthsElapsed 0x100073DE, cmdEndScenario 0x10006DB8 (city->vt[0x21C] + sends
0xBA44EB51). Win/lose/time limit decided by the script. Goal command 0x844587AE at SCENARIO 0x100069AA / SIMUI
0x10012186.

## 5. Rewards and landmarks
City Planner (city+0x10C) owns rewards; INI keys REWARD_BUILDINGS, REWARD_BUILDINGS_2, BUSINESS_DEAL_BUILDINGS,
*_NEEDED_FOR_*. Planner vt[0x14](n) 0x1000AD4D OfferRewardBuilding(n); vt[0x18](n) 0x1000ADC3 / vt[0x1C](n)
0x1000AE49 status. Unlocked map inside planner (lock +0x310). Offer arrives as a petition. Message 0xA2D1C5B9
(data+4 building type) -> reward index 1..0x20 (LIKELY placed). Landmark placement code not found.

## 6. Cheats
Cheat manager (SC3U.exe vt 0x4D7900, ctor 0x46A80A), reached via X->vt[0x2C]() with X cached at SIMMISC .data
0x1004A0E8. +0x04 registered codes (node +8 name, +0x1C id), +0x08 listeners, +0x0C used ids, +0x2C enabled byte
(default 1). Methods: 0x0C Register(id, str); 0x14/0x18 add/remove listener; 0x1C IsUsed(id); 0x20 SetUsed;
0x28 Send(text, id) (0x46AC27) delivers {0x230E27AC, id, text*} to listeners; 0x2C Match(text, &id) (0x46AC89)
case-insensitive prefix: 0 none, 1 code+params, 2 exact.
Codes: I am weak 0x62E8630B (SIMMISC 0x100093D3, budget flag, LIKELY free building); so sue me 0x23B4418F; I love
red tape 0xC37A5AAA; Salt on/off 0x831CC164/0xA31CC169; Terrain one up/down 0xA31CF2EF/0xC31CF2F6; nerdz rool
0x23742A09; call cousin Vinnie 0xA3558FD6 (PM: petition 215 via 0x100208AC(215,0,1,0,6)); force petitioners to
say N 0x031DCE55; stop forcing advice 0x831109B4; force Mortimer/Moe/Constance/Gus/Karen to say 0xE3110BF8/
0x43110C27/0x83110C50/0xC310F7D4/0x23110BAD; force Maria/Randall to say 0x83110C8B (shared); let's make a deal
0xA3713D78; pay tribute to your king 0x631DC6BA; zyxwvu 0x234DA4D2; garbage in, garbage out 0xC2FAA2F5; power to
the masses 0xC2FA8E82; water in the desert 0x42FA93FE. Ticker joke cheats at SC3U 0x4206A3..0x420B83.
**DANGER: app cheat id 0x8889284A ("Crash", SC3U 0x408896) writes to address 0. Never send it.**

## Recipes (UI thread)
1. Pending petitions: pm = *(city+0x120); q = *(pm+0x28); h = **(q+4); walk; e = *(node+8) (id, param).
2. Answer: thiscall SIMADV 0x1002096A(pm, id, 1|2). 3. Queue: SIMADV 0x100208AC(pm, id, 0,0,0,0).
4. Ticker: object by vtable pair (0x4D0F4C, 0x4D0D64); lists obj+0x13C+4*cat; text *(entry+0x0C) (string vt[0x1C]).
5. Post headline: MessageSend({0x82684130, &item}) or AddItem 0x421C2D on obj+0x120.
6. Disasters: enable city->vt[0x9C](bool); trigger dm->vt[0x34](id) -> QI(iid) -> start slot -> vt[8]; or menu
   command + map click.
7. Cheat: build GZ string; mgr->vt[0x2C](str,&id) then mgr->vt[0x28](str,id) (mgr by vtable 0x4D7900).
8. Scenario: s = *(SCENARIO 0x1001EB44); byte s+0x09; goals s+0x984.

## Open questions (live tests)
- Petition answer: "call cousin Vinnie", read queue (+0x11 = 6, +0x14 = 1), 0x1002096A(pm, 215, 1): funds rise,
  entry removed, Reaction1 shown.
- Ticker: dump lists on a new city (expect 100, 102 from 0x42C1ED2D), category count.
- Disasters: Fire vt[0x10](x, z) with disasters on; city+0x1F2 vs Options toggle; DM +0x31/+0x24 during a
  disaster; pair UFO/Toxic/Whirlpool/Early Warning ctors.
- Scenario: s+0x09 and +0x984 before/after a goal. Rewards: planner vt[0x18]/[0x1C](1..0x20) before/after
  "pay tribute to your king". Advisor advice storage.
