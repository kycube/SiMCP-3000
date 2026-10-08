# Scenarios: reading and writing .SNR files (2026-10-08)

The game's Scenario Creator (Apps\ScenarioCreator: "SimCity Scenario Creator 97.mde" and "... 2000.mde", Microsoft
Access databases) does not run on a current system: the test machine has 64-bit Microsoft 365 Access, and the
Creator is a compiled 32-bit Access 97 / 2000 application (Access offered only to reopen it after a failed start).
So scenarios are read and written directly; the format turned out to be simple.

## The file

An .SNR is an IXF file (sc3k_mcp/ixf.py): every record of the scenario's city (as in a saved .sc3) plus

| record (type, group, instance) | content |
|---|---|
| 0x26E732E0, 0x19A6CEA1, 0 | header {u32 text table id, i32, i32} (shipped: 7/5, 3/3 ...; new files use 3, 3) |
| 0x62B9DA24, 0x19A6CEA1, 1 | 24-bit BMP, 163 x 152, shown in the scenario picker |
| 0x2026960B, 0x19A6CEA1, 2 | 5 bytes 05 00 00 00 4D |
| 0x04845CBE, 0xC3DE4D66, 0 | "SNR" chunk, text lines: "SNR ", the base city's path (the Creator's temp copy), "<script type 601861727> <script group 601861772> <entry script instance>", "<text table id> 1", "<guide advisor id> 1", "<text table id>" |
| 0x23DFAE5F, 0x23DFAE8C, n | scripts, plain text: "; Script Code", the instruction count, then per instruction "<flag> <opcode> <argument count> ; comment" and one "<is variable> <value>" line per argument (values may be floats, e.g. 187.33) |
| 0x2026960B, <table id>, index | texts: u32 character count + Latin-1, as in the game's Res\Text tables. Index 0 = description, 1 = name. |

The shipped scenarios keep most texts in Apps\Res\Text\ENGLISH\<Scenario>.IXF (same table id) and embed only a few
(truncated: the old Creator wrote counts longer than the bytes stored). The game reads texts embedded in the .SNR
itself (live/t16: a copy of Rags To Riches with all 75 texts embedded under a new table id, its header, SNR chunk
and script references moved to that id, loaded and showed "MCP Rags To Riches" and its briefings).

Opcode names: Apps\Sys\SYS.PAK SC3ScenarioLayer.ini (0 Add ... 74 IsNeighborDealPresent; sc3k_mcp/scenarios.py
OPS). scenario_file lists any scenario's scripts readably, e.g. Rags To Riches' monthly crime check:

```
GetCrimeValue(1)
If()
AndCondition()
  GreaterThan(15, $1)
  Equal($15, 0)
EndAnd()
BeginBlock()
  MarkGoalStatus(1, 1)
  PopUpMsg(text#102 'The citizens of %CITYNAME% are overjoyed by Mayo', 0, 0x628d0c45, 1, 1)
  SetVariable(15, 1)
EndBlock()
```

Patterns used by the shipped scripts: the entry script adds goals (AddGoal(id, table, text)), rank titles
(AddRankInfo(rank, table, text)), the briefing (MakeDialogText(table, text, 1)) and registers periodic scripts
(RepeatRegular(period, 0x23DFAE8C, script)); a value goes into a variable (Get...(variable[, kind])); If() takes
one condition or an AndCondition / OrCondition group closed by EndAnd / EndOr, then one statement or a BeginBlock
... EndBlock; the end is SetResultsDlgText(table, text, mood) then EndScenario(rank); %SCNVN n% in a text shows
variable n.

## Writing (create_scenario)

sc3k_mcp/scenarios.py create(): the base .sc3's records + header + picture + SNR chunk + texts embedded under a
table id derived from the name + two scripts: 149 (entry: goals, rank titles 1 "win" / 2 "lose", briefing,
RepeatRegular(2, ..., 150)) and 150 (each goal measured into variable k and marked met / not met; AllGoalsMet ->
SetResultsDlgText + EndScenario(1); GetMonthsElapsed past the limit -> EndScenario(2)).

Verified in the game (live/t17): "MCP Test Win" (Madison, population >= 1) loaded, the goal was marked met after
the first month and the scenario ended with rank 1, result "All goals met.", results window with the planner
(Constance Lee); "MCP Test Lose" (population >= 100,000,000, 2 months) ended at month 2 with rank 2 and its text.
scenario_status reads texts the scenario carries in its own file.
