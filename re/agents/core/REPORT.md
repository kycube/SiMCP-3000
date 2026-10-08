# CORE: clock, object root, framework, lifecycle (static analysis by subagent, saved by main session)

Addresses are `MODULE preferred-VA`; "slot N" = vtable index N (byte offset 4N); args = stack args (thiscall).

## 1. Simulation clock (CONFIRMED by code unless marked)
Three threads; the frame loop does not advance the date.
1. Timer thread: SIMCITY global timer service (0x10017518, owns a thread object; timer set at 0x100175C8)
   calls the clock's timer callback SIMCITY 0x1000A854 (cdecl, arg = clock).
2. Clock = city+0x130 (vtable SIMCITY 0x10013988, size 0x78, ctor 0x10009B35). The callback does nothing while
   pause count +0x54 != 0; otherwise accumulates elapsed real ms (+0x58 last, +0x5C acc) and calls AdvanceMinute
   0x1000A915 / AdvanceHour 0x1000A9B1 / **AdvanceDay 0x1000AA4D** (thiscall, no args, takes lock +0x6C).
   AdvanceDay bumps the clock's RWDate (+0x48, JDN at +0x4C) and fires listeners by kind: 3 day, 4 week, 5 month
   (day-of-month 1), 6 year (day-of-year 1), 7 one-shot alarms. A listener posts `{msgType,...}` to a queue
   (q->vt[0xC](msg*)) or calls a C callback.
   Layout: +0x04..+0x1C listener lists kinds 1..7, +0x20 embedded timer (vt 0x10013BA0), +0x40 minute, +0x44 hour,
   +0x48 RWDate, +0x50 rate, +0x54 pause count, +0x60/64/68 ms per day/hour/minute, +0x6C lock, +0x70 refcount,
   +0x74 running.
   Slots: 3 Start(timer 1000), 4 Stop, 5 GetDate(RWDate*), 6 SetDate(RWDate*), 7/8 Get/SetTime, 9 GetRate(&r),
   10 SetRate(r) 0x1000A066, 11 Pause, 12 Resume, 13 GetPauseCount, 15..18 register listener (queue, kind, msgType),
   19..22 unregister.
3. Sim engine thread = city+0x124 (vtable SIMCITY 0x10013140; runnable vt 0x1001313C at +4). Thread proc 0x100014DC:
   blocking get [+0x14]->vt[0x68](&msg); 0x1000155B; 0x100015FB (sleeps 1 s at a time while city slot 138 (total
   pause) != 0); dispatch 0x10001675 on msg[0]: 0 -> 0x1000165F; 1 Start 0x100017E2 (registers clock listeners
   (q,3,5),(q,4,6),(q,5,7),(q,6,8)); 2 Stop 0x10001882 (exit); 3/4 run sim category 0 / 1..0;
   **5 = day: categories 2..0 then city->slot127(2)**; 6 = week: categories 3..0, slot127(3);
   7 = month: slot139, categories 4..0, slot127(4), slot140; 8 = year: categories 5..0, slot127(5).
   Category runner 0x10001914(k): for each simulator in list engine+0x44+4k: ok = sim->vt[0x14](); if !ok
   city->slot141() (lock); sim->vt[0xC](k); if !ok city->slot142() (unlock).
   Engine layout: +0x08 thread, +0x0C event, +0x11/12/13 init/started/stop flags, +0x14 msg queue (vt[0xC] post,
   vt[0x10] urgent, vt[0x68] get), +0x18 message server, +0x20 lock, +0x28 city, +0x44..+0x58 sim lists cat 0..5.

**Day step = city slot 127 SIMCITY 0x100054E7 OnDateEvent(kind)**: kind 2 = day (under lock city+0x1F4,
++city+0x138 at 0x1000566C, msg 0x43152585(year, dayOfYear)); kind 3 week (0x237CFEE8); kind 4 month (0xC2A3FD82);
kind 5 year (0x437CFFDE + anniversaries when year - founding year (+0x13C) in 10/25/50/100/250/500/1000/2000).

Date storage: city+0x134 RogueWave RWDate (vt 0x10013978), +0x138 JDN. **+0x13C = founding year** (slot 125 get,
126 set). RWDate helpers (thiscall on RWDate): ctor(m,d,y) 0x1000932B, year() 0x10009708, dayOfYear()
0x100095AF, dayOfMonth() 0x100095CE, month() 0x1000968E, mdy(&m,&d,&y) 0x100095EA; jday(m,d,y) cdecl 0x10009511.
City slots: 121 0x100052FD GetDate(&m,&d,&y); 122 0x10005252 (&doy,&y); 123 0x10005398 SetDate(m,d,y).

Pause (counted): slot 131 0x100056BB PauseSim (clock Pause, ++city+0x140, msg 0xC2A35D7F on 0->1);
slot 132 0x10005773 ResumeSim (clock Resume, --+0x140, msg 0xC2A35D81 at 0); 133 IsPaused; 134 count (+0x140);
135/136/137 second counter +0x144 (system/modal pause); 138 = +0x140 + +0x144. City message handler slot 3
0x10002FA6: 0xC2A35D7E -> PauseSim, 0xC2A35D80 -> ResumeSim, 0xC2684065 -> SetSpeed(msg[1]).

Speed: slot 129 0x10005ADA SetSpeed(0..4) -> clock SetRate(r), r = sim-ms per real-ms: 0:120 (~720 s/day),
1:10080 (8.6 s/day), 2:43200 (2 s), 3:129600 (0.67 s), 4:525600 (0.16 s). Stores +0x14C effective, +0x150
requested (effective 0 while slot 12 (+0x30) true); sends 0xC2684066(speed). Slot 130 0x10005A77 GetSpeed.

## 2. Object graph root
- Live: *(STRTSIM 0x10032C9C) = city. Static alternative (CONFIRMED): *(SIMCITY 0x100174AC) -> holder (vt SIMINIT
  0x1002F458), holder+0x14 = city. Holder Init SIMINIT 0x10003C19: GZCOM()->vt[3](0xA1A166CC, IID 0xFA1,
  &this+0x14) then city->slot155(this). Holder +0x0C = SIMINIT 0x1002F350 obj (clsid C306B854, IID 41772393; type
  hierarchy, LIKELY); +0x10 = SIMINIT 0x1002FB44 obj (clsid 4306B914, IID 6179B578). SC3U.exe 0x407B5E also creates
  a city into app+0x18. Do NOT GetClassObject(0xA1A166CC) yourself (creates a new city).
- Simulators created by city 0x10005E3E via helper 0x10006655(clsid,&unk,iid,&field), also kept in vector
  +0x94/+0x98 (slot 112 count, 113 get). Accessors (mov eax,[ecx+X]; ret):
  71-74 +0x84..+0x90 (set elsewhere); 78 +0xA0 A0AB8C20 SIMGEOM; 79 +0xA4 4173F29E SIMDIRT; 80 +0xA8 2171C021
  SIMNTWRK; 81 +0xAC 029CA806 SimTransit; 82 +0xB0 00AB8C8B SIMGEOM; 83 +0xB4 409FF3BA SIMRCI; 84 +0xB8 20AFDF44
  SIMUTIL; 85 +0xBC 82BF0042 SIMUTIL; 86 +0xC0 41193C4B SIMMISC; 87 +0xC4 C11BCC75 SIMMISC (budget); 88 +0xC8
  E11BDDF6 SIMMISC; 89 +0xCC 22498F2C STRTSIM; 90 +0xD0 61F6ABF5 SIMDSTR; 91 +0xD4 C0A81498 SIMECO; 92 +0xD8
  20A7AE7F SIMSERV; 93 +0xDC 00ABF2EC SIMSERV; 94 +0xE0 A0F42214 SIMSERV; 95 +0xE4 A106C520 SIMRCI; 96 +0xE8
  20EC9849 SIMRCI; 97 +0xEC A106CF3D SIMRCI; 98 +0xF0 60A2966E SIMRCI; 99 +0xF4 02910E84 SIMMISC; 100 +0xF8
  E2ED2A04 SIMMISC; 101 +0xFC 631C8E77 SIMGEOM; 157 +0x100 03DE4CE4 SCENARIO; 102 +0x104 422E28E8 SIMADV; 108
  +0x108 828D0C49; 106 +0x10C E28D0B76; 105 +0x110 828D04FB; 103 +0x114 028D0F43; 104 +0x118 C28D0A3A; 107 +0x11C
  A28D0FC9; 109 (LIKELY) +0x120 02619041 (all SIMADV); 118 +0x124 sim engine; 128 +0x130 clock.
  Vector-only simulators: 60A42F32 SIMRCI, C259C02D SIMMISC, 61448030 SIMSERV, E1FD7AA3 SIMGEOM.
- Other city slots: 15-17 map size (+0x3C/+0x40/+0x44); 141/142 lock/unlock city+0x1A8 (sim-data lock, used by
  the engine and 18x by SIMUI); 143 &lock; 144/145/146 same for +0x1CC.

## 3. Framework (vtable SC3U.exe 0x4D6BF4, 45 slots). Global *(SC3U.exe 0x4FAB74); getter 0x45D5AE (cdecl)
3 0x45DA30 (1) AddSystemService(svc) [svc vt 0x14 ID, 0x0C priority]; 4 0x45DB58 (3) GetSystemService(srvid,
iid, void**) [map +0x18]; 5 0x45DB8D (3) EnumSystemServices; 6/7 0x45DF07/0x45DFBE (1) AddHook/RemoveHook
(+0x08); 8/9 0x45DC10/0x45DD1C (1) add/remove list +0x28: svc vt[0x2C](count) every main-loop pass; 10/11
0x45DDB6/0x45DE6D (1) list +0x24: svc vt[0x28](n) every [fw+0x2C] passes; 12/13 set/get interval (+0x2C, min 1);
14 0x45D9AE runs list +0x28; 15 0x45D9CE per-pass driver (++0x4FAB7C, slot 14, list +0x24 every N); 16
0x4613D8 (1) Quit(code); 17 0x4613FE AbortiveQuit; 18 CommandLine() = fw+0x34; 19 IsInstall; 20 GetCOMObject()
= fw+0x94; 31 returns +0x04 (application object); 43 0x46135A main loop (PeekMessageA up to 500 msgs, then slot
15 if byte +0x30).
Per-frame UI-thread callback: fw->vt[0x20](svc) (slot 8); svc = cIGZSystemService-shaped (slots 0..0x30:
QI/AddRef/Release, 0x0C priority, 0x14 ID, 0x28/0x2C bool f(uint32) ret 4). Stub every slot safely.

## 4. Lifecycle (partial; LIKELY/GUESS unless marked)
- City slot 7 SIMCITY 0x10003B8B (+0x1C, 1 arg) = InitNewCity(params*) (shape CONFIRMED): params vt[0x54]/[0x5C]/
  [0x58] -> map size; vt[0x6C] -> +0x08; vt[0x68] -> object (AddRef'd); vt[0x60] -> start year (date = 1/1/year),
  then 0x10003EA6. Params class/creator not found.
- City slot 8 0x1000429D (1 arg): big re-init of simulators/date, LIKELY load-from-stream; also city message
  0x111FDAE5(msg[1]). Slot 9 0x10004E30: releases simulators (LIKELY shutdown/clear).
- SIMINIT holder: slot 3 Init (creates city), slot 4 Shutdown (city->slot156); slot 8 0x10003D77 GetFileType(path)
  via slots 9..15 probes (slot 9 checks FORM/SCDH = .SC3; slot 12 .snr). Save chunk tags (MISC, ALTM, XTER ... CNAM,
  SCDH, FORM) referenced at SIMINIT 0x10001B57..0x1000211E.
- Exit game: framework Quit(0). New/load/save/quit-to-menu UI entry points not found statically.

## 5. Debug facilities
- "Gonzo Debug Window" = class cGZDebugStreamW95 (RegisterClassA 0x45FA23, CreateWindowExA 0x45FA5C, HWND at
  obj+0x8C, show 0x45FBCB): framework debug output window, no input. No command console (/topic, /save belong to
  the IRC chat client).
- Cheats registered per module as (string, id): SIMMISC 0x100067F8 "I am weak" id 0x62E8630B via
  X = 0x100320B1()->vt[0x2C](); X->vt[0x0C](id, name) (GUESS); SIMMISC 0x10019A06 "I love red tape"; SIMADV
  0x1001CDFF "power to the masses", 0x1001CEBF "call cousin Vinnie"; SIMRCI 0x10030C36 "nerdz rool"; SIMDIRT
  0x1000ED59 "Salt on" (+ "Terrain one up/down", "Load terrain"). Matching code not found; SC3U.exe reads a `cheats`
  command-line switch at 0x4079DE.

## Recipes
- Date: read city+0x138 (JDN) or slot 121 GetDate(&m,&d,&y). Set: slot 123 SetDate(m,d,y).
- Pause/resume: slot 131/132 (balance them). Speed: slot 129 SetSpeed(1..3).
- Advance exactly N days (UI thread; sim paused; city+0x144 == 0): clk = *(city+0x130); clk->vt[0x2C]() (extra
  clock pause); city->slot132() (engine unblocks, clock stays paused); call SIMCITY 0x1000AA4D (this = clk) N times
  (queues day/week/month/year messages exactly like the timer); poll city+0x138 to start+N; city->slot131();
  clk->vt[0x30](). Fallback: SetSpeed(3), resume, poll JDN, pause (may overshoot ~1 day).
- UI-thread edits to sim data: wrap in city->slot141()/slot142() (city+0x1A8 lock).

## Open questions / live tests
1. Clock +0x4C vs city+0x138 while running; N-day recipe with N=40 from 1 Jan (+40 exactly, month message once).
2. Click turtle/llama/cheetah, read +0x14C/+0x150 (expect 1/2/3); meaning of slot 12 (+0x30).
3. Register a stub service with fw->vt[0x20], count vt[0x2C] calls/s; confirm fw+0x30 = 1 in game.
4. Breakpoint city slot 7 on New City OK and slot 8 when loading a .sc3 (callers, params vtable). Save: SIMINIT
   chunk writer 0x100020D1.
5. After loading a second city, *(SIMCITY 0x100174AC)+0x14 == *(STRTSIM 0x10032C9C)?
6. "I am weak" with a breakpoint on SIMMISC's handler for 0x62E8630B.

## Addendum (core agent's second report)
- Menu command ids are GZCOM class ids of command/dialog classes. Recipe (LIKELY, from SC3U.exe 0x43EC51 "New" and
  0x4112B5 "Save"): p = 0; GZCOM()->vt[3](clsid, IID 0x006856F7, &p) (wrapper ctor 0x474908); p->vt[0x2C]() runs the
  dialog; p->vt[0x20](&res); res->vt[0xBC]() -> byte (1 = accepted?). New 0xE3270FE9, Save 0x410438DD, Load
  0x610438A4: factory in SIMINIT ~0x1000C26E (also 0x010438E3, 0x310E8C85). Quit 0xA10438E9: SC3U.exe factory
  0x411523 (also 0x447F1E43/44, 0x626CE901, 0xC124039A, 0xC26CE54D, 0xE504604A). Load subtypes 0x83172AD7 /
  0x63172B74 / 0x23172AF2 / 0xA42C7725 and SaveAs 0xC3172AEA in SIMINIT file code. vt[0x2C] is probably modal
  (nested message loop): a bridge call may not return until the dialog closes.
- Clock SetRate 0x1000A066 sets +0x50 = r, +0x60 = 86400000/r ms/day, +0x64 ms/hour, +0x68 ms/minute; clock Start
  = timer->vt[0x14](1000, 0); clock slots 15-18 register (3 args), 19-22 unregister (2 args).
- Engine Start subscribes clock->vt[0x3C](q,3,5), (q,4,6), (q,5,7), (q,6,8).
