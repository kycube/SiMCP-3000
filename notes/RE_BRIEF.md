# RE brief for static-analysis subagents (SC3U MCP project)

You are reverse engineering **SimCity 3000 Unlimited** (stock GOG build) so an MCP server can drive the game
by calling its own code. Your job is **STATIC ANALYSIS ONLY** of one subsystem, ending in a short report.

## Hard rules

1. **STATIC ONLY.** Never run anything in `live\` and never import `sc3k_mcp` (those talk to the LIVE
   game process). Never attach to, read, or write the running `SC3U.exe`. Never use the Cheat Engine tools.
   Never launch the game.
2. The game files in `C:\Program Files\GOG Galaxy\Games\SimCity 3000 Unlimited\` are **read-only** for you.
3. Write files **only** in your own folder `re\agents\<your-topic>\` of this repository.
   Do not edit shared files (`re\pe.py`, `notes\*`, anything else). Copy and extend helpers in your folder.
4. Python 3 with pefile and capstone installed (don't use `-I`). Set
   `PYTHONIOENCODING=utf-8`. Don't name a script `dis.py` (shadows the stdlib). No Ghidra/IDA is installed.
5. Don't install anything. No web access is needed.

## Tools and references

- `re\pe.py`: `Image(name)` loads a module from the game's Apps dir (e.g. `Image("SIMMISC.DLL")`). Methods:
  `dis(va, n, stop_at_ret)`, `around(va, before, after)` (synced to the function start), `func_start(va)`,
  `xrefs(va)` (code whose imm/disp32 == va), `data_refs(va)` (dwords in data == va, e.g. vtable slots),
  `calls_to(fn)` (E8/E9 callers), `find_str(s)`, `strings()`, `vtable(va)` -> [(slot, fn, nargs)],
  `vtable_starts()` -> {vtable: [ctor sites]}, `stack_args(fn)` (thiscall arg count from `ret N`),
  `follow_jmp`, `cstr`, `u32`, `imports` {iat_va: "dll!name"}, `exports`. Run from `re\` or add it to sys.path.
- `re\out\strings\<MODULE>.txt`: every string with the code addresses referencing it (`va [nrefs] refs | text`).
- `re\out\com_classes_live.txt`: the live GZCOM class registry: `clsid ? library* ? DLL` (315 classes).
- `notes\GZCOM.md` (framework/director interface, IIDs), `notes\ADDRESSES.md`, `notes\LIVE_FACTS.md`
  (facts measured in the running game; **the most important input you have**).
- Data files: `Apps\Res\*` (UI layouts, text, `SSimData`, `Hotkeys`, sprites), `Apps\Sys\SYS.PAK`
  (contains `SimTune.INI` tunables). Text strings may live in `Res\Text\*.IXF`.

## Binary facts

- MSVC 6 C++, **no RTTI**, `thiscall` (this in ecx, callee pops stack args), bool returned in AL.
  VC6 vtables are contiguous in `.rdata` with no separator. Many classes use multiple inheritance (several
  vtables at object +0, +4, +8...). SEH frames via `_EH_prolog` (`mov eax, imm; call _EH_prolog`), so
  `func_start()` (which looks for `push ebp; mov ebp, esp`) can miss those: also look for `b8 xx xx xx xx e8`
  followed by a call to the module's `_EH_prolog` thunk.
- Every game DLL prefers base **0x10000000** (`SIMBABLD` 0x12000000) and is relocated at runtime.
  **Always report addresses as `MODULE preferred-VA`** (e.g. `SIMMISC.DLL 0x100051C6`).
- Architecture: GZCOM components (SC4-style). Components find each other through `cIGZCOM`
  (`GZCOM()->GetClassObject(clsid, iid, void**)`, vtable slot 6 on directors) and through the framework's
  system services. Interface IDs are 32-bit constants pushed before such calls; `QueryInterface(iid, void**)`
  implementations compare `[ebp+8]` against IID constants, which tells you which interfaces a class has.
- Every DLL caches framework service pointers in its `.data` (seen live): e.g. a gzserviced object, a
  resource manager. A pointer stored in a module's `.data` and set in an init function is how globals look.

## How the MCP will use your findings

A bridge DLL inside the game can, on the game's UI thread: call any function (`cdecl`/`stdcall`/`thiscall`,
up to 8 args, and batches of calls), read/write memory, send synthetic mouse/keyboard input. The Python side
reads memory directly. So the best recipe looks like:
"object X is reached by: global `MODULE VA` -> +0x14 -> ...; or `GZCOM()->GetClassObject(clsid, iid)`.
To do Y, call `MODULE VA` (thiscall, this = X, args (a, b)); it returns ...; it charges funds / shows a
dialog / needs Z first."

## Deliverable

`re\agents\<topic>\REPORT.md`, **at most 150 lines**:
1. Answers to your numbered questions, each with exact addresses and how you know (string xref, call
   pattern, arithmetic, data table), and confidence (CONFIRMED by code / LIKELY / GUESS).
2. Object layouts you established (offset, type, meaning).
3. Concrete recipes for the bridge (function, convention, this, args, return, side effects).
4. Open questions that need a live test, phrased as a test (e.g. "read X before/after building a road").
Your final message must summarize the report (key addresses + recipes) — it is what the main session reads.
Be economical: budget about 80-120 tool calls.
