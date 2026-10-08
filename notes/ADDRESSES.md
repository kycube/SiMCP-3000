# Address table

Addresses are `(module, VA at preferred base)`; game DLLs prefer 0x10000000 and get relocated, so store
module + RVA and resolve at attach time. `SC3U.exe` has no ASLR (base 0x400000, TimeDateStamp 0x63732172).

| Module | Address | What | Verified how |
|---|---|---|---|
| SC3U.exe | 0x40B00F | App: register GZCOM libraries (app dir `*.dll` or `Components` list, then `PlugIn\*.dll`) | static + live plugin load |
| SC3U.exe | 0x470157 | `GetPluginDirectory(cRZString*)` = dirs->vt[0x20]() + `"PlugIn\"` | static |
| SC3U.exe | 0x470463 | get directory-manager object (global `0x4FAC9C`) | static + live read |
| SC3U.exe | 0x4FAC9C | `dirs*` (directory manager); cached strings at +0x20, +0x5C, +0x70 = Apps dir | live read |
| SC3U.exe | 0x4708C4 | `GZCOM()` -> global cIGZCOM* (cdecl) | static |
| SC3U.exe | 0x48A575 | library load (LoadLibraryA + GZDllGetGZCOMDirector + InitializeCOM) | static + live |
| SC3U.exe | 0x48A675 | library unload (FreeLibrary) | static |
| SC3U.exe | 0x48AB54 | library load + EnumClassObjects(0x48AA3A, com) | static + live (callback arg) |
| SC3U.exe | 0x48AB1D | GetClassObject via owning library (loads it if needed) | static |
| SC3U.exe | 0x469023 | command-line object ctor (switches `intro`/`sound`/`music` = `off`) | static |
| SC3U.exe | 0x4D6D18 | vtable of the cIGZCOM object | live (plugin `InitializeCOM`) |
| SC3U.exe | 0x4D6BF4 | vtable of the object returned by `cIGZCOM->vt[4]()` (framework) | live |
| SC3U.exe | 0x4D8B4C | vtable of the directory manager | live |
| SC3U.exe | 0x45FA51 | references "Gonzo Debug Window" string | static (not followed yet) |
| SIMECO.DLL | 0x1001C508 | cRZCOMDllDirector vtable (18 slots) | static |
| SIMECO.DLL | 0x1001C14C | SIMECO director vtable (overrides 13, 15, 16) | static |
| SIMECO.DLL | 0x100126D3 | `director->AddCls(clsid, factory, 0)` | static |
