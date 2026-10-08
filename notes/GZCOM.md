# GZCOM in SC3U (GOG build) — what's verified

SC3U's component framework is the direct ancestor of SimCity 4's GZCOM (documented by the SC4 modding
community: nsgomez/gzcom-dll wiki). **The interface IDs and the director vtable order match SC4.**

## Plugin loading (verified live 2026-10-07)

- `SC3U.exe 0x40B00F` (app init): optionally reads a `Components` list from a config file; otherwise
  enumerates `<AppDir>\*.dll` and skips `CLCD16.DLL`, `CLCD32.DLL`, `DPLAYERX.DLL`, `DRVMGT.DLL` (leftover CD
  protection). Each DLL is passed to `cIGZCOM` vtable `+0x14` (registers a library).
- Then it **always** enumerates `0x470157()` = `dirs->vtable[0x20]()` + `"PlugIn\"` -> `*.dll`, same call.
- Directory manager object: `*(0x4FAC9C)` (getter `0x470463`). All its cached directories resolve to
  `C:\Program Files\GOG Galaxy\Games\SimCity 3000 Unlimited\Apps\`, so the plugin folder is
  **`Apps\PlugIn\`**. (`%PluginDirectory%` expansion at `0x46412E` uses the same getter.)
- Library object (per DLL): `+0x00` loaded flag (byte), `+0x04` director, `+0x08` path (cRZString),
  `+0x0C` path char*, `+0x1C` HMODULE. Load = `0x48A575` (LoadLibraryA, GetProcAddress
  `GZDllGetGZCOMDirector`, call it, `director->InitializeCOM(GZCOM(), path)`); unload = `0x48A675`.
  `0x48AB54` = load + `director->EnumClassObjects(0x48AA3A, com)`. `0x48AB1D` = GetClassObject path.
- `0x4708C4()` returns the global `cIGZCOM*` (cdecl, no args).

Observed call order for `Apps\PlugIn\sc3kplug.dll`, all on the **UI thread** (the `Gonzo` window's thread):
`DllMain(ATTACH)` -> `GZDllGetGZCOMDirector()` -> `InitializeCOM(pCOM, path)` -> `EnumClassObjects(0x48AA3A, pCOM)`
-> `OnStart(pCOM)`. Nobody calls `QueryInterface(cIGZFrameWorkHooks)`: to get the 8 framework hooks the director
must register itself (SC4: `FrameWork()->AddHook(hooks)`; SC3U slot not yet identified).
Live values that session: `pCOM = 0xD45764` (vtable `0x4D6D18`), `pCOM->vtable[4]()` = framework
`0xD456D0` (vtable `0x4D6BF4`). Heap addresses vary per run; vtables are fixed (exe has no ASLR).

## IIDs (from SIMECO's QueryInterface, `SIMECO.DLL 0x1001244A`)

| IID | Interface |
|---|---|
| `0x00000001` | cIGZUnknown |
| `0xA21EE941` | cIGZCOMDirector |
| `0x03FA40BF` | cIGZFrameWorkHooks |

## cIGZCOMDirector vtable (SC3U), from cRZCOMDllDirector in SIMECO.DLL (vtable `0x1001C508`)

Args = stack args (thiscall, callee pops), from each method's `ret N`.

| Slot | Off | Method | Args | Notes |
|---|---|---|---|---|
| 0 | 0x00 | QueryInterface(iid, void**) | 2 | |
| 1 | 0x04 | AddRef | 0 | |
| 2 | 0x08 | Release | 0 | |
| 3 | 0x0C | InitializeCOM(cIGZCOM*, const cIGZString& path) | 2 | stores COM at +0x28, `COM->vtable[4]()` (framework) at +0x40, path at +0x2C; propagates to child directors |
| 4 | 0x10 | OnStart(cIGZCOM*) | 1 | base: gets an object via COM GetClassObject(0x25076B9E, 0xA237613C) and calls slot 16 with it |
| 5 | 0x14 | EnumClassObjects(callback, context) | 2 | |
| 6 | 0x18 | GetClassObject(clsid, iid, void**) | 3 | |
| 7 | 0x1C | CanUnloadNow | 0 | |
| 8 | 0x20 | OnUnload | 0 | |
| 9 | 0x24 | RefCount | 0 | |
| 10 | 0x28 | RemoveRef | 0 | |
| 11 | 0x2C | FrameWork | 0 | returns +0x40 |
| 12 | 0x30 | GZCOM | 0 | returns +0x28 |
| 13 | 0x34 | GetDirectorID | 0 | pure in base; SIMECO returns 0x63CAE7AC |
| 14 | 0x38 | GetLibraryPath(cIGZString&) | 1 | |
| 15 | 0x3C | scalar deleting destructor(flags) | 1 | |
| 16 | 0x40 | bool ?(obj) | 1 | propagated to children; SIMECO overrides with `return true` |
| 17 | 0x44 | AddDirector(cIGZCOMDirector*) | 1 | |

Second interface at object `+4`: cIGZFrameWorkHooks, 11 slots = QI/AddRef/Release (adjustor thunks) +
8 hooks with 0 args returning bool (SC4 order: PreFrameWorkInit, PreAppInit, PostAppInit, PreAppShutdown,
PostAppShutdown, PostSystemServiceShutdown, AbortiveQuit, OnInstall; SC3U order unverified).

SIMECO's derived director registers classes in its constructor via `AddCls(clsid, factory, 0)`
(`SIMECO.DLL 0x100126D3`): `0xC0A81498`, `0x0345776C`, `0xC34ACD28`, ... -> the economy components.

## Every GZCOM library in Apps (export `GZDllGetGZCOMDirector`)

AUDIO, GIMEX, GZGraphicD, GZResourceD, GZSOUNDD, GZServiceD, GZTOOLSD, GZWIND, GZWWWD, MaxisAddOn, SCENARIO,
SIMADV, SIMBABLD, SIMCITY, SIMDIRT, SIMDSTR, SIMECO, SIMGEOM, SIMINIT, SIMMISC, SIMNTWRK, SIMRCI, SIMSERV,
SIMSPR, SIMUI, SIMUTIL, STRTSIM, SimTransit, simvariables (and SC3U.exe itself).
