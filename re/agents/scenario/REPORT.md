# SCENARIO: the scenario script language (static RE by subagent; saved by main; checked live where noted)

Addresses are SCENARIO.DLL preferred VAs. Live checks: notes/SCENARIOS.md (live/t16, live/t17).

## Corrections and file rules
- Text records are 8-bit: u32 character count + cp1252 bytes (record size 4 + n), as in every Res\Text\ENGLISH
  scenario IXF (CONFIRMED; also live).
- Line endings: the line readers (0x1000F6F1, 0x100077AE) end a line at `\r` and drop `\n`: CRLF works, LF-only
  fails.
- Script text: line 1 free, line 2 the instruction count; per instruction a line `time op nargs`, nargs lines
  `isVar value`, then one blank line that is always consumed (parser 0x1000F74C). Numbers parsed with %d ("2.5"
  reads as 2).
- The extension must be `.snr` (compared lower-case); the SNR chunk {0x04845CBE, 0xC3DE4D66, 0} must exist (the
  "is a scenario" test) and parse; the entry script must exist. Scripts are type 0x23DFAE5F (group normally
  0x23DFAE8C, instances free). Optional records: newsticker styles 0xA4846144/0xA48461A3, custom presenters
  0x44EB6BC8/0x44EB6BC9, saved state 0x206C6E7C/0xC3DE4D66 (present = the scenario resumes; leave it out to start
  fresh).

## 1. Dispatch
INI command names are mapped to handlers at 0x1000B2B0..0x1000C5D2 (registration 0x1000C6FE into the table at
*0x1001EB10, 8 bytes per opcode). ExecInstr 0x10008D1A (this = s, instr, exec): opcode = (short)[instr+4];
handler(instr, s->running ? exec : 0). Instruction in memory: 12 bytes {i32 time, i16 op, u8 nargs, arg*}; arg 8
bytes {u8 isVar, i32 value at +4}. With exec = 0 every handler returns 1 and does nothing, but If / IfElse / And /
Or / Block still consume their operands. Variables: 512 int32 at s+0x70; "d" = destination index (< 512,
0x10007206); value arguments are constants or variables (isVar = 1 reads vars[value]); Get-style handlers write
vars[d] and return the value.

Conditions: If = condition (the next instruction) + body (the next one, run or skipped); IfElse = condition, then,
else (one instruction each); AndCondition ... EndAnd = true if every enclosed result is non-zero (short-circuit;
empty = 1); OrCondition ... EndOr = true if any is (empty = 0); BeginBlock ... EndBlock groups statements. Wrap
bodies in a block: a skipped Assign (3) does not consume its operand.

| op | name | arguments -> effect |
|---|---|---|
| 0 1 18 10 | Add Subtract Multiply Divide | d, a, b -> d = a op b (divide by 0 = -1) |
| 8 | ComputePercentage | d, a, b -> d = a * 100 / b (b = 0 -> -1) |
| 9 17 | Decrement Increment | d |
| 55 | SetVariable | d, v (returns 1) |
| 3 | Assign | d = the result of the next instruction |
| 4 5 7 26 27 28 29 48 51 52 57 | GetCrimeValue GetLandValue GetPopulation CountUnpoweredBuildings CountUnwateredBuildings GetTrafficDensity GetFundsAvailable GetAura GetSurplusPower GetSurplusWater GetTotalDebt | d -> d = the city's value |
| 6 | GetPollutionValue | d, kind 0 / 1 / 2 (the three pollution measures, LIKELY air / water / garbage) |
| 30 | GetMonthsElapsed | d |
| 54 | GetCurrentDate | dYear, dMonth, dDay (order LIKELY) |
| 72 | GetRCItaxes | dR, dC, dI |
| 13 14 34 32 | Equal GreaterThan LessThan NotEqual | a, b -> 1 / 0 (signed) |
| 11 12 44 | EndAnd EndOr EndBlock | markers |
| 33 | CountStructures | d, structure id |
| 56 | CountStructuresNearLocation | d, id, x, z, radius (1-based cells, square) |
| 59 | CountStructuresWithAppearanceInCity | d, key type, key group, key instance |
| 58 | CountStructuresWithAppearanceNearLocation | d, key type, group, instance, x, z, radius |
| 45 | GenerateRandomNum | d, lo, hi (inclusive) |
| 22 | StartFire | x, z (1-based) |
| 23 64 | StartRiot StartToxicCloud | x, z, premonition |
| 24 | StartTornado | 8 args, LIKELY x1, z1, x2, z2, intensity, speed, ?, premonition |
| 46 65 66 | StartEarthquake StartWhirlpool StartSpaceJunk | magnitude, premonition |
| 47 67 | StartUFOAttack StartLocusts | premonition |
| 60 | MoveCamera | x, z, zoom (0-4; >= 5 -> 2) |
| 62 | PlaySound | sound id |
| 63 | SetScenarioSpeed | speed, lock (LIKELY) |
| 61 | EnableDisableDisasters | on |
| 49 50 | DisableNewNeighborDeals EnableNewNeighborDeals | type (-1 = all) |
| 53 | OfferRewardBuilding | building id |
| 68 | IsOrdinanceEnacted | ordinance id, want (1 enacted / 0 not) |
| 69 70 71 | OfferBusinessDeal IsBusinessDealActive EnableDisableBusinessDeal | deal [, want / on] |
| 73 74 | IsNeighborConnection IsNeighborDealPresent | type, direction / ?, want (LIKELY) |

## 2. The leading number: a start time
Units of 1/1440 sim day. The tick 0x1000C828 runs a pending instruction once time <= s+0x58 (the scenario clock:
+1 per sim-clock tick, jumps to the next multiple of 1440 at a day change). It applies only to top-level
instructions of the entry script (the shipped ones use increasing values there); elsewhere use 0.

## 3. How scripts run
Start 0x1000ACD1 loads the entry script named on SNR line 3 (key at s+0x958); time-0 instructions run on the first
tick. SubRoutine(group, instance) runs {0x23DFAE5F, group, instance} at once (0x10008D58). RepeatRegular(period,
group, instance) (0x10005B76) appends to the list at s+0x870 + 12 * period: 0 daily, 1 weekly (day of month % 7 ==
0, LIKELY), 2 monthly (live: checks ran each month), 3 yearly; the lists run at the date change, before pending
timeline instructions; entries are never removed.

## 4. Goals, ranks, dialogs
AddGoal(goal, table, index) (status starts not met); MarkGoalStatus(goal, s) (met = s != 0); GoalStatusIs(goal, s)
(0 if the goal does not exist); AllGoalsMet; AddRankInfo(rank, table, index); EndScenario(rank): s+0x8D8 = rank
(-1 if that rank was never added), stops the scripts, opens the results window, which lists all ranks in order and
highlights the one reached (0x1000755D); no built-in win / lose (shipped: 1 = best). SetResultsDlgText(table, index,
mood) (s+0x8DC); MakeDialogText(table, index, mood) (s+0x8E0; mood 1 happy .. 5 bad, LIKELY). PopUpMsg(table,
index, status button (1 = show), presenter id, presenter kind, mood); presenter kinds 0 petitioner index, 1 advisor
id, 2 custom presenter. ShowNewsticker(table, index). Text tokens: %CITYNAME%, %MAYOR%, %SCNNAME%, %SCNVN n% /
%SCNVM n% / %SCNVY n% (variable n as number / money / year, LIKELY).

## 5. Header and SNR chunk (parser 0x10009158)
Line 1 ignored; line 2 (the base .sc3 path) ignored; line 3 entry script key; line 4 "table index" = the name text
(index 1); line 5 "id kind" = default presenter of the status and results windows (kind 1: an advisor id, checked,
fallback 0x022E288E); line 6 = the text table for custom presenter names. Header record: only dword 0 (the text
table id) is read (SIMINIT 0x1002A6FA); the other two numbers are only copied.

## 6. Texts inside the .SNR
The load hook 0x10007EC2 registers the .SNR with the resource manager (*0x1001EB8C vt[0x5C]) before any text
lookup; texts are fetched by key {0x2026960B, table, index}. SIMINIT does the same for the picker (vt[0x5C] add,
vt[0x68] remove) and loads the picture {0x62B9DA24, 0x19A6CEA1, 1} and the string {0x2026960B, 0x19A6CEA1, 2}.
Index 0 = description, 1 = name. (CONFIRMED live: live/t16.)
