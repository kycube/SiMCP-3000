# ADVISORS, SCENARIOS, AUTO OPTIONS (static RE by subagent; saved by main, 2026-10-07)

Addresses `MODULE VA`. city = *(STRTSIM 0x10032C9C). Helper scripts here: q.py (dis/around/xref/dref/vt/str),
lin.py (linear disassembly), txt.py (text tables), advids.py, snr.py / snrdis.py (.SNR container and script
disassembler), snrcat.py (catalog of every scenario: name, description, goals, ranks, month tests).

## A. Advisors
Every advisor has its cSC3Advisor base at advisor+4 (A; base ctor SIMADV 0x1001CF14; base vtable 0x1003127C;
QI iid 0x013DEE82 -> A). (CONFIRMED)
| A+ | advisor+ | meaning |
|---|---|---|
| 0x80 | 0x84 | advice list (0x24-byte message list, type 0): the current advice |
| 0x84 | 0x88 | briefings list (type 1): static topics (e.g. 3000 "Simoleons") |
| 0x88 | 0x8C | ordinances list (type 2): ordinance topics 1..73 |
| 0x8C | 0x90 | "my news is out of date" message index (0x129..0x12F) |
| 0x90 | 0x94 | std::list of forced ids (cheat), re-added every update |
| 0x98 | 0x9C | PetitionerManager pointer |
| 0x9C | 0xA0 | byte "needs update" (set by callback SIMADV 0x1000F058 -> 0x100094DD, L monthly) |
Update = A vtable slot 18 (Utilities 0x10019AE6): gather, generate, sweep 0x1000273C, clear fresh 0x1000270B,
re-add forced 0x1001DF05, send 0x82C04C75 {advisorId} (SIMUI panel refresh).

Message list (0x24, vt 0x1003019C, ctor 0x10001334(owner, type)): +0x04 std::list head pointer (nodes {next,
prev, entry*}, no size); +0x08 owner; +0x0C type byte; text tables type 0: +0x18 Heading 0x825ADC5A, +0x14
Message 0x225ADC6B, +0x1C Ticker 0xC25B11C3, +0x10 0; types 1/2: +0x10 = +0x18 = 0x82B85965, +0x14 =
0xE26EC3B8; +0x20 lock object (vt[1] lock, vt[2] unlock).

Advice entry (0x1C, ctor 0x10002CF2): +0x00 byte kind (0 normal, 1, 3 permanent briefing); +0x04 message id
(advisor tables 1..314 / 401..413); +0x08 ticker handle; +0x0C key/param; +0x11 byte period; +0x12 byte
counter; +0x13 hidden/read byte (only == 0 shown); +0x14/+0x15 flags; +0x16 fresh byte; +0x18 head of
std::list<token record> (records inline at node+8, 0x30-byte nodes).
AddAdvice SIMADV 0x1001DB07(id, key, b11, b14, b15, kind) thiscall on A, ret 0x18; wrappers 0x1001DA5A..
0x1001DAEA; 0x1001DB9F(id, record) attaches a token record. Adding posts a ticker headline (0x1000287E) with
link type 0x724A82D2 and data {advisorId, msgId}.

Advisor ids (A vtable slot 19): +0x104 Utilities 0x022E288E; +0x108 Budget 0x628D0C45; +0x10C City Planner
0xC28D0B6E; +0x110 Environment 0x828D04EB; +0x114 Health/Education 0xC28D0F40; +0x118 Public Safety
0x828D0A2F; +0x11C Transportation 0x028D0FC5.

A's interface (SIMUI panel model 0x1000606B): vt[0x50] GetMood (average AdvisorMoods.INI mood of visible
entries, default 3); vt[0x58] entry count; vt[0x5C](uint* inout, obj** out) GetHeadings; vt[0x60](id,
cIGZString*) message text; vt[0x64](id, obj**) 0x44-byte advice object; vt[0x68]/[0x6C] briefings;
vt[0x78]/[0x7C] ordinances. SIDE EFFECT: vt[0x60]/[0x64] mark the entry read (+0x13 = 1, hides it, removes the
ticker item). Read memory instead.

Tokens: globals %MAYOR% %YOURNAME% %CITYNAME% %YOURCITY% %POPULATION% %YEAR% %PARADENAME% %ANYNEIGHBOR%
(SIMADV 0x100385D0..). Per-entry token records (ctor 0x1002A019(type, token, value)): +4 type; +8 token string
object (+0xC begin, +0x10 end); +0x1C/+0x20/+0x24 values. Formatter 0x1002A8C8: 1 text(table +0x20, index
+0x1C); 2/3 int +0x24 locale-formatted (money vs number OPEN; Budget uses 3 for %X%); 4 neighbor (+0x1C);
5 "%d" of +0x24. Advisor messages with %X%/%Y% (disaster damage, 140-286, 401-411) and %NEIGHBOR% (249).

## B. Scenarios
Files Cities\Scenarios\*.SNR (13 shipped); StarterTowns *.ST3, Terrains *.SCT (SIMINIT 0x10012E5B,
0x100148DE). Main menu "Play Scenario" (id 0x712BF5C5) runs command 0x610438A4 [uint32 0xA42C7725, bool true].
In city: MenuItem 0x10009304 = COMM 0x610438A4 0xA42C7725 (Options -> Load submenu 0xD1009300). Load Execute
SIMINIT 0x10009A91; parser 0x10009C98: p1 uint32 load type, p2 bool prompt-to-save, p3 char-array path
(variant type 0x800C) skips the file dialog (SCENARIO Replay 0x10008A85 uses [0xA42C7725, false, path]).
After a pick, SIMINIT 0x100097DD(path) loads, SCENARIO 0x1000ACD1 starts it.
.SNR = IXF/DBPF container (D7 81 C3 80): header group 0x19A6CEA1 (inst 0 text table id, inst 1 BMP);
"SNR" text chunk group 0xC3DE4D66; scripts group 0x23DFAE8C type 0x23DFAE5F; the embedded city. Script ops
(SC3ScenarioLayer.ini): AddGoal 35, MarkGoalStatus 37, GoalStatusIs 39, EndScenario 31, AddRankInfo 41,
SetResultsDlgText 42, GetMonthsElapsed 30, RepeatRegular 20, SetScenarioSpeed 63.

State s = *(SCENARIO 0x1001EB44) = *(city+0x100) (always exists). vtable 0x1001A64C: slot 4 IsRunning (+9),
5 Save, 6 GetPath(out) (+0x938).
| s+ | meaning |
|---|---|
| 0x08 | initialized byte |
| 0x09 | running byte (set at start, cleared by EndScenario/shutdown) |
| 0x58 | scenario clock (sim minutes) |
| 0x5C/0x60 | start month / start year |
| 0x64/0x68/0x6C | current day / month / year (refreshed while running) |
| 0x70 | 512 script variables (int32) |
| 0x870..0x8A0 | repeat lists daily/weekly/monthly/yearly |
| 0x8B0/0x8B8 | guide advisor id / flag |
| 0x8B4 | results mood (L) |
| 0x8BC | scenario text table id |
| 0x8C0 | goals map header (+0x8C4 count); lock +0x984 |
| 0x8CC | rank map (node key rank, +0x14 table, +0x18 index) |
| 0x8D8 | final rank (EndScenario), -1 = not ended |
| 0x8DC / 0x8E0 | results text object / intro text object |
| 0x8E4 | scenario UI sub-object (goals window, command 0x844587AE) (L) |
| 0x8F0 | results dialog object while shown |
| 0x8F4 | scenario name text object |
| 0x938 | cRZString path (L) |
| 0x9A9 | speed/pause changes allowed (L) |
Text object (0x14, vt 0x1001AC84): +4 loaded string, +8 type, +0xC table, +0x10 index. Name = index 1,
description = index 0 of the s+0x8BC table (Res\Text\<LANG>\<Scenario>.IXF).
Goals map: header +4 root, +8 leftmost, +0xC rightmost, children NULL-terminated; node (0x24): +4 parent, +8
left, +0xC right, +0x10 goal id, +0x14 cached text obj, +0x18 status byte (1 met), +0x1C text table, +0x20
text index. AddGoal 0x100058D0; MarkGoalStatus 0x10008662; GoalStatusIs 0x1000799F; AllGoalsMet 0x10005A1A.
Time limit: decided by each script; months elapsed = (y - y0)*12 - m0 + m (0x10008807). snrcat.py extracts
the month tests (Locusts 60, Criminalville 60, Betterfeld 48, Rags 36; tutorials none).
Outcome: EndScenario 0x10006DB8(rank): s+0x8D8 = rank, running = 0, results dialog (0x1000412D -> +0x8F0) +
city vt[0x21C] (modal pause), listen for 0xBA44EB51 = results dialog CLOSED (SC3U command 0xC425A194, Execute
0x412C65); handler 0x10006B4F closes, unpauses (vt[0x220]), sends 0x54E23EE9 {1}, choice 0 replay, 1 load
scenario picker, 2 0x1000A906 (OPEN). Rank 1 = best; worst rank = loss (titles via AddRankInfo).

## C. Auto options
Auto Budget = city+0x1F1 (default 1; get vt[0x90], set vt[0x94](bool) sends 0x6569DE54; budget caches at
budget+0x13). Year end (SIMMISC 0x100083B3): if funds > -100,000 and (flag == 0 or funds < 0) the Budget
window (MenuItem 0x10008001) opens. Disasters = city+0x1F2 (vt[0x98]/vt[0x9C]). city+0x1F0 show startup
tip (L). city+0x1F3 (get vt[0x40], set vt[0x50], default 1): purpose OPEN (candidate Auto Go To Disasters).
Advisors and petitioners never act on their own.

## Recipes
1. Advice (memory only): for off in 0x104..0x11C: adv = *(city+off); L = *(adv+0x84); head = *(L+4); walk
   nodes; e = *(n+8); if byte e+0x13 == 0: id = *(e+4); heading text(*(L+0x18), id), message
   text(*(L+0x14), id), ticker text(0xC25B11C3, id); tokens h = *(e+0x18), records at node+8: type +4, token
   chars [*(r+0xC), *(r+0x10)), value +0x24. Briefings *(adv+0x88), ordinances *(adv+0x8C).
3. Scenario status: s = *(city+0x100); running byte s+9; name text(*(t+0xC), *(t+0x10)) with t = *(s+0x8F4);
   description text(*(s+0x8BC), 0); months = (*(s+0x6C) - *(s+0x60))*12 - *(s+0x5C) + *(s+0x68); goals from
   the tree at *(s+0x8C0); ended = !running and *(s+0x8D8) != -1; rank title from the tree at *(s+0x8CC);
   results text r = *(s+0x8DC); results dialog open = *(s+0x8F0) != 0.
4. Start a scenario: deferred command 0x610438A4 [0xA42C7725] (verified live it needs [kind, 0, 0]), answer
   the save prompt, pick in the file dialog.
