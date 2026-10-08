# Reverse-engineering notes

How the game and the Building Architect were understood well enough to drive them through their own code.

- `agents/<topic>/REPORT.md`: static-analysis reports, one per subsystem (core, economy, map, tools, sim,
  events, deals, advisors, buildings, fields, layers, features, styles, replace, rng, uistate, viewsnap; and for
  the Building Architect: bld, batrender, baapp, batlib). Each was written from the stock GOG binaries following
  `notes/RE_BRIEF.md`, with addresses given as `MODULE preferred-VA` and a confidence (CONFIRMED / LIKELY / GUESS).
  Their findings were then tested against the running game; `notes/LIVE_FACTS.md` and `notes/BAT_PHASE0.md` record
  what was verified and how. Where a report and LIVE_FACTS disagree, LIVE_FACTS wins.
- The one-off analysis scripts and dumps that the reports mention (string tables, vtable dumps, per-topic helper
  scripts) are not included: they were run against a local install and are reproducible with the helpers below.
- `pe.py`: a small PE/x86 helper (load a game module at its preferred base, disassemble with capstone, find
  cross-references, strings, vtables). `inventory.py`: every module's strings with the code that references
  them and the class IDs each component registers. `syspak.py`: extracts `Apps\Sys\SYS.PAK` (menu ids, tunables).
  `vtlen.py`: vtable lengths. Output goes to `re/out/` (not tracked).

Nothing here contains game code or data; you need your own copy of SimCity 3000 Unlimited to reproduce it.
