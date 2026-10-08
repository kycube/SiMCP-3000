// sc3kbridge.dll - in-process command bridge for SimCity 3000 Unlimited (GOG build 2.0.949)
//
// Injected into SC3U.exe by the sc3k-mcp server (LoadLibraryA from a remote thread). Commands are
// written by the server into the exported g_bridge block and executed on the game's UI thread by
// sending WM_SC3KBRIDGE to a message-only window this DLL creates on that thread. Unlike the SC2K
// bridge it does not subclass the game window (DDrawCompat may subclass it too, which would make
// unloading unsafe): a temporary WH_GETMESSAGE hook on the UI thread creates the window, then is
// removed. Every command runs under __try/__except, so a crash in a game call comes back as
// status -100 and the game keeps running.
//
// Addresses are for the stock GOG SC3U.exe (TimeDateStamp 0x63732172); the DLL refuses to run
// (ready = 0xBAD) on any other build. Game DLL addresses are module-relative (they are relocated).

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <stddef.h>
#include <tlhelp32.h>
#include <intrin.h>

#define BRIDGE_MAGIC   0x42334353  // 'SC3B'
#define BRIDGE_VERSION 1
#define WM_SC3KBRIDGE  (WM_APP + 0x3C3)

#define SC3U_TIMESTAMP 0x63732172
#define SC3U_BASE      0x400000

// ---------------------------------------------------------------------------
// Shared command block

enum {
	OP_PING = 1,
	OP_UNLOAD = 5,
	OP_CALL = 7,       // args: addr, conv(0 cdecl/stdcall, 1 thiscall), nargs, this, a0..a7, flags
	OP_INSTALL = 8,    // internal: install hooks on the UI thread
	OP_CALL_SEQ = 12,  // args: count, flags; str: CallDesc[count] run back-to-back in one UI-thread turn
	OP_MOUSE = 20,     // args: action (MOUSE_*), x, y (client px), holdMs (fake cursor stays there afterwards), x2, y2
	OP_KEY = 21,       // args: vk, action (KEY_*), modifiers (1 shift, 2 ctrl, 4 alt), char (for WM_CHAR, 0 = none)
	OP_TRACE = 22,     // args: action (1 object, 2 class, 3 remove all), addr (object | vtable), nslots, tag
	OP_WATCH = 23,     // args: action (1 set, 2 clear all), addr, len (1/2/4), rw (1 write, 3 read/write), slot 0..3
	OP_REPEAT = 24,    // args: fn, this (0 = cdecl/stdcall), count, nargs (0..4), a0..a3 -> calls fn count times
	OP_COMMAND = 25,   // args: command id, nparams (0..3), p1, p2, p3, defer -> run a game command (menu/tool id)
	OP_DEFER = 26,     // args as OP_CALL: run the call later from the message loop (for calls that open modal windows)
	OP_TOOL_POINTS = 27, // args: tool, camera, npoints (1..16), mode (0 drag through points, 1 click each), keys, defer;
	                     // str: int world[npoints][3] -> the tool's own mouse handlers see those world points
	OP_OCC_SCAN = 28,  // args: occupant manager, out buffer (game memory), max records, x0, y0, x1, y1
	                   // -> unique occupants {ptr, category, x0, y0, x1, y1, occupant id, state} (8 dwords each); ret[0] = count
	OP_RNG = 29,       // args: action (1 seed and enable, 0 disable, 2 status), seed -> ret {seeds drawn, rands drawn,
	                   // seeders patched, enabled}: reproducible randomness for research (see "Deterministic randomness")
};

#define WM_SC3KBRIDGE_DEFERRED (WM_SC3KBRIDGE + 1)

// SC3U.exe helpers for game commands (re/agents/tools/REPORT.md section 6)
#define FN_MAKE_COMMAND 0x474908  // thiscall(void **holder, DWORD id): command server -> new command object
#define FN_OPERATOR_NEW 0x4B4890  // cdecl operator new(size)
#define FN_VARIANT_U32  0x46F260  // thiscall(variant, value, type 3 = uint32)

enum { MOUSE_MOVE = 0, MOUSE_LCLICK = 1, MOUSE_RCLICK = 2, MOUSE_LDOWN = 3, MOUSE_LUP = 4, MOUSE_LDRAG = 5,
	MOUSE_WHEEL = 6, MOUSE_RELEASE = 7 };
enum { KEY_PRESS = 0, KEY_DOWN = 1, KEY_UP = 2 };

// One call of an OP_CALL_SEQ batch (packed into BridgeBlock::str)
struct CallDesc {
	DWORD fn;
	DWORD thisPtr;  // 0 for cdecl/stdcall
	int nargs;      // 0..6
	int args[6];
};

#define EVENT_SLOTS 64

#pragma pack(push, 4)
struct BridgeBlock {
	DWORD magic;
	DWORD version;
	DWORD ready;          // 1 once the command window exists and hooks are installed; >= 0xBAD: init failed
	DWORD hwndBridge;     // message-only window that executes commands (owned by the UI thread)
	DWORD hwndMain;       // the game's main window (class "Gonzo")
	DWORD threadId;       // the game's UI thread
	DWORD hooksInstalled;
	DWORD layout[8];      // [0] offsetof(events) [1] offsetof(state) [2] sizeof(BridgeBlock) [3] offsetof(seq)
	// request
	DWORD seq;
	DWORD op;
	int args[16];
	char str[520];
	// response
	DWORD doneSeq;
	int status;           // 0 ok, <0 error
	int ret[16];
	DWORD msgLen;
	char msg[2048];
	// persistent state (readable/writable by the client at any time)
	struct State {
		DWORD eventSeq;       // total events ever logged; slot = (seq - 1) % EVENT_SLOTS
		DWORD autoMode;       // 1: outside bridge commands too, auto-answer prompts (unattended play)
		DWORD autoAnswerYes;
		DWORD stopAtDay;      // reserved for the real-time stop-at-day hook
		DWORD deferPosted;    // deferred calls posted
		DWORD deferDone;      // deferred calls finished (== deferPosted when idle)
		int deferStatus;      // status of the last finished deferred call (-100 crash)
		int deferRet;         // EAX of the last finished deferred call
		DWORD reserved[8];
	} state;
	// event log: prompts/dialogs the game raised and how they were answered
	struct Event {
		DWORD seq;
		DWORD day;
		DWORD kind;
		int result;
		DWORD id;
		DWORD how;
		char text[232];
	} events[EVENT_SLOTS];
};
#pragma pack(pop)

extern "C" __declspec(dllexport) BridgeBlock g_bridge = { BRIDGE_MAGIC, BRIDGE_VERSION };

// ---------------------------------------------------------------------------
// State

static HMODULE g_hModule;
static HWND g_hwndMain;
static HWND g_hwndBridge;
static HHOOK g_getMsgHook;
static char g_className[64];
static volatile LONG g_inCall;
static int g_cmdFlags;

static void Msg(const char *fmt, ...) {
	if (g_bridge.msgLen >= sizeof(g_bridge.msg) - 2)
		return;
	va_list va;
	va_start(va, fmt);
	int n = _vsnprintf_s(g_bridge.msg + g_bridge.msgLen, sizeof(g_bridge.msg) - g_bridge.msgLen, _TRUNCATE, fmt, va);
	va_end(va);
	if (n < 0)
		g_bridge.msgLen = sizeof(g_bridge.msg) - 1;
	else
		g_bridge.msgLen += n;
	if (g_bridge.msgLen < sizeof(g_bridge.msg) - 1) {
		g_bridge.msg[g_bridge.msgLen++] = '\n';
		g_bridge.msg[g_bridge.msgLen] = 0;
	}
}

static void LogEvent(DWORD kind, int result, DWORD id, DWORD how, const char *text) {
	DWORD seq = ++g_bridge.state.eventSeq;
	BridgeBlock::Event *e = &g_bridge.events[(seq - 1) % EVENT_SLOTS];
	e->day = 0;  // TODO: city day once its address is known
	e->kind = kind;
	e->result = result;
	e->id = id;
	e->how = how;
	strncpy_s(e->text, sizeof(e->text), text ? text : "", _TRUNCATE);
	e->seq = seq;  // written last: readers treat a slot as valid once seq matches
}

// ---------------------------------------------------------------------------
// IAT hooks (installed/removed on the UI thread). Each game module's import slot for a USER32
// function is pointed at our hook; the hooks pass through unless a bridge input command is active.

typedef BOOL (WINAPI *GetCursorPosFn)(LPPOINT);
typedef SHORT (WINAPI *KeyStateFn)(int);
static GetCursorPosFn g_realGetCursorPos;
static KeyStateFn g_realGetAsyncKeyState, g_realGetKeyState;

// Synthetic input state: while GetTickCount() < g_fake.until the cursor and the listed keys report
// what the last OP_MOUSE/OP_KEY asked for, so the game's UI sees a consistent "real" mouse.
static struct {
	DWORD until;
	POINT screen;
	BYTE down[256];
} g_fake;

static BOOL FakeActive(void) {
	return g_fake.until && (int)(g_fake.until - GetTickCount()) > 0;
}

static BOOL WINAPI Hook_GetCursorPos(LPPOINT p) {
	if (FakeActive() && p) {
		*p = g_fake.screen;
		return TRUE;
	}
	return g_realGetCursorPos(p);
}

static SHORT WINAPI Hook_GetAsyncKeyState(int vk) {
	if (FakeActive())
		return g_fake.down[vk & 0xFF] ? (SHORT)0x8000 : 0;
	return g_realGetAsyncKeyState(vk);
}

static SHORT WINAPI Hook_GetKeyState(int vk) {
	if (FakeActive())
		return g_fake.down[vk & 0xFF] ? (SHORT)0xFF80 : 0;
	return g_realGetKeyState(vk);
}

// ---------------------------------------------------------------------------
// Deterministic randomness (research mode, off by default). The simulators' random generators are small LCG
// objects {state, seed} whose Seed(-1) takes timeGetTime() when they are created (city load); the simulators
// also call MSVCRT rand(). With a seed set, Seed(-1) draws from a seeded sequence instead of the clock and
// rand() off the UI thread (the UI thread animates in real time) comes from a seeded LCG, so the same save +
// the same actions + the same seed give the same city.

typedef int (__cdecl *RandFn)(void);
typedef DWORD (WINAPI *TimeFn)(void);
static RandFn g_realRand;
static TimeFn g_realTimeGetTime;
static struct {
	volatile LONG on;
	DWORD seedState, randState;
	DWORD seeds, rands;
	DWORD uiTid;
	DWORD uiState, uiRands, uiSeed;   // UI-thread rand() while a city loads (the city global is 0 then)
	DWORD *cityGlobal;
	BOOL loading;
} g_rng;

#define RAND_TRACE 65536
#define RAND_FRAMES 6
static struct { DWORD n; DWORD rec[RAND_TRACE][RAND_FRAMES + 1]; } g_randTrace;   // thread + call stack

static int __cdecl Hook_rand(void) {
	if (g_rng.on && GetCurrentThreadId() == g_rng.uiTid && g_rng.cityGlobal) {
		// on the UI thread rand() animates in real time, except while a city is being built (city global 0):
		// those calls (e.g. SimTransit assigning its traffic agents) get a sequence reset at each load
		if (*g_rng.cityGlobal == 0) {
			if (!g_rng.loading) {
				g_rng.loading = TRUE;
				g_rng.uiState = g_rng.uiSeed;
			}
			g_rng.uiState = g_rng.uiState * 214013u + 2531011u;
			g_rng.uiRands++;
			return (int)((g_rng.uiState >> 16) & 0x7FFF);
		}
		g_rng.loading = FALSE;
	}
	if (g_rng.on && GetCurrentThreadId() != g_rng.uiTid) {
		g_rng.randState = g_rng.randState * 214013u + 2531011u;
		if (g_rng.rands < RAND_TRACE) {
			DWORD *rec = g_randTrace.rec[g_rng.rands];
			void *frames[RAND_FRAMES];
			USHORT got = RtlCaptureStackBackTrace(1, RAND_FRAMES, frames, NULL);
			rec[0] = GetCurrentThreadId();
			for (int i = 0; i < RAND_FRAMES; i++)
				rec[1 + i] = i < got ? (DWORD)frames[i] : 0;
			if (!got)
				rec[1] = (DWORD)_ReturnAddress();
			g_randTrace.n = g_rng.rands + 1;
		}
		g_rng.rands++;
		return (int)((g_rng.randState >> 16) & 0x7FFF);
	}
	return g_realRand ? g_realRand() : 0;
}

static DWORD WINAPI SeedSource(void) {
	if (g_rng.on) {
		g_rng.seedState = g_rng.seedState * 1103515245u + 12345u;
		g_rng.seeds++;
		return g_rng.seedState;
	}
	return g_realTimeGetTime ? g_realTimeGetTime() : GetTickCount();
}

static DWORD g_seedSourcePtr = (DWORD)SeedSource;   // what a patched 'call dword ptr [imm32]' reads
static struct { BYTE *imm; DWORD orig; } g_seedPatches[64];
static int g_nSeedPatches;

// Seed(-1) in every module: 8B 44 24 04 56 83 F8 FF 8B F1 75 06 FF 15 <imm32 -> timeGetTime IAT> 89 06 89 46 04
static int PatchSeeders(void) {
	static const BYTE pat[] = { 0x8B, 0x44, 0x24, 0x04, 0x56, 0x83, 0xF8, 0xFF, 0x8B, 0xF1, 0x75, 0x06, 0xFF, 0x15 };
	static const BYTE tail[] = { 0x89, 0x06, 0x89, 0x46, 0x04 };
	if (g_nSeedPatches)
		return g_nSeedPatches;
	g_realTimeGetTime = (TimeFn)GetProcAddress(LoadLibraryA("WINMM.dll"), "timeGetTime");
	HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, GetCurrentProcessId());
	if (snap == INVALID_HANDLE_VALUE)
		return 0;
	MODULEENTRY32 me;
	me.dwSize = sizeof(me);
	for (BOOL ok = Module32First(snap, &me); ok; ok = Module32Next(snap, &me)) {
		if (me.hModule == g_hModule)
			continue;
		BYTE *base = me.modBaseAddr;
		__try {
			IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(base + ((IMAGE_DOS_HEADER *)base)->e_lfanew);
			IMAGE_SECTION_HEADER *sec = IMAGE_FIRST_SECTION(nt);
			for (int i = 0; i < nt->FileHeader.NumberOfSections; i++, sec++) {
				if (!(sec->Characteristics & IMAGE_SCN_MEM_EXECUTE))
					continue;
				BYTE *a = base + sec->VirtualAddress, *b = a + sec->Misc.VirtualSize - 32;
				for (BYTE *q = a; q < b && g_nSeedPatches < 64; q++) {
					if (q[0] != 0x8B || memcmp(q, pat, sizeof(pat)) != 0 || memcmp(q + 18, tail, sizeof(tail)) != 0)
						continue;
					DWORD *imm = (DWORD *)(q + 14);
					DWORD old;
					if (VirtualProtect(imm, 4, PAGE_EXECUTE_READWRITE, &old)) {
						g_seedPatches[g_nSeedPatches].imm = (BYTE *)imm;
						g_seedPatches[g_nSeedPatches].orig = *imm;
						*imm = (DWORD)&g_seedSourcePtr;
						VirtualProtect(imm, 4, old, &old);
						FlushInstructionCache(GetCurrentProcess(), imm, 4);
						g_nSeedPatches++;
					}
				}
			}
		}
		__except (EXCEPTION_EXECUTE_HANDLER) {
		}
	}
	CloseHandle(snap);
	return g_nSeedPatches;
}

// Draw tracing (research): every generator Next() call of every module is logged with its caller chain, so two
// runs can be compared draw by draw. Next() starts with 55 8B EC 51 51 in almost every module: those 5 bytes are
// replaced by a jump to a stub that logs and then runs them.
#define NEXT_TRACE 131072
#define NEXT_FRAMES 4
static struct { DWORD n; DWORD rec[NEXT_TRACE][4 + NEXT_FRAMES]; } g_nextTrace;   // module, tid, this, state, frames
static struct { BYTE *fn; BYTE orig[5]; } g_nextHooks[40];
static int g_nNextHooks;
static BYTE *g_nextStubs;

static void __cdecl LogNext(int idx, DWORD *self, DWORD ret, DWORD esi, DWORD ebp) {
	DWORD i = g_nextTrace.n;
	if (i >= NEXT_TRACE)
		return;
	g_nextTrace.n = i + 1;
	DWORD *r = g_nextTrace.rec[i];
	r[0] = idx;
	r[1] = GetCurrentThreadId();
	r[2] = (DWORD)self;
	__try {
		r[3] = *self;
	}
	__except (EXCEPTION_EXECUTE_HANDLER) {
		r[3] = 0;
	}
	r[4] = ret;                                  // the caller of Next()
	r[5] = esi;                                  // the caller's ESI (often its object)
	__try {
		r[6] = *(DWORD *)(ebp - 8);                  // the caller's first saved register (its caller's ESI)
	}
	__except (EXCEPTION_EXECUTE_HANDLER) {
		r[6] = 0;
	}
	void *frames[1];
	r[7] = RtlCaptureStackBackTrace(2, 1, frames, NULL) ? (DWORD)frames[0] : 0;
}

static int HookNexts(void) {
	static const BYTE seedPat[] = { 0x8B, 0x44, 0x24, 0x04, 0x56, 0x83, 0xF8, 0xFF, 0x8B, 0xF1, 0x75, 0x06, 0xFF, 0x15 };
	static const BYTE tail[] = { 0x89, 0x06, 0x89, 0x46, 0x04, 0x5E, 0xC2, 0x04, 0x00 };
	static const BYTE prologue[] = { 0x55, 0x8B, 0xEC, 0x51, 0x51 };
	if (g_nNextHooks)
		return g_nNextHooks;
	if (!g_nextStubs)
		g_nextStubs = (BYTE *)VirtualAlloc(NULL, 4096, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
	if (!g_nextStubs)
		return 0;
	HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, GetCurrentProcessId());
	if (snap == INVALID_HANDLE_VALUE)
		return 0;
	MODULEENTRY32 me;
	me.dwSize = sizeof(me);
	for (BOOL ok = Module32First(snap, &me); ok && g_nNextHooks < 40; ok = Module32Next(snap, &me)) {
		if (me.hModule == g_hModule)
			continue;
		BYTE *base = me.modBaseAddr;
		__try {
			IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(base + ((IMAGE_DOS_HEADER *)base)->e_lfanew);
			IMAGE_SECTION_HEADER *sec = IMAGE_FIRST_SECTION(nt);
			for (int i = 0; i < nt->FileHeader.NumberOfSections; i++, sec++) {
				if (!(sec->Characteristics & IMAGE_SCN_MEM_EXECUTE))
					continue;
				BYTE *a = base + sec->VirtualAddress, *b = a + sec->Misc.VirtualSize - 64;
				for (BYTE *q = a; q < b; q++) {
					if (q[0] != 0x8B || memcmp(q, seedPat, sizeof(seedPat)) != 0 || memcmp(q + 18, tail, sizeof(tail)) != 0)
						continue;
					BYTE *fn = q + 27;                 // Next() follows Seed()
					if (memcmp(fn, prologue, 5) != 0)
						break;
					int idx = g_nNextHooks;
					BYTE *st = g_nextStubs + idx * 64;
					BYTE *w = st;
					*w++ = 0x60;                              // pushad
					*w++ = 0x9C;                              // pushfd
					*w++ = 0x55;                              // push ebp
					*w++ = 0x56;                              // push esi
					*w++ = 0xFF; *w++ = 0x74; *w++ = 0x24; *w++ = 0x2C;   // push [esp+0x2C] (return address)
					*w++ = 0x51;                              // push ecx (this)
					*w++ = 0x6A; *w++ = (BYTE)idx;            // push idx
					*w++ = 0xE8; *(DWORD *)w = (DWORD)LogNext - (DWORD)(w + 4); w += 4;   // call LogNext
					*w++ = 0x83; *w++ = 0xC4; *w++ = 0x14;    // add esp, 20
					*w++ = 0x9D;                              // popfd
					*w++ = 0x61;                              // popad
					memcpy(w, prologue, 5); w += 5;           // the replaced prologue
					*w++ = 0xE9; *(DWORD *)w = (DWORD)(fn + 5) - (DWORD)(w + 4); w += 4;  // jmp Next+5
					DWORD old;
					if (!VirtualProtect(fn, 5, PAGE_EXECUTE_READWRITE, &old))
						break;
					g_nextHooks[idx].fn = fn;
					memcpy(g_nextHooks[idx].orig, fn, 5);
					BYTE jmp[5];
					jmp[0] = 0xE9;
					*(DWORD *)(jmp + 1) = (DWORD)st - (DWORD)(fn + 5);
					memcpy(fn, jmp, 5);
					VirtualProtect(fn, 5, old, &old);
					FlushInstructionCache(GetCurrentProcess(), fn, 5);
					g_nNextHooks++;
					break;
				}
			}
		}
		__except (EXCEPTION_EXECUTE_HANDLER) {
		}
	}
	CloseHandle(snap);
	return g_nNextHooks;
}

static void UnhookNexts(void) {
	for (int i = 0; i < g_nNextHooks; i++) {
		DWORD old;
		if (VirtualProtect(g_nextHooks[i].fn, 5, PAGE_EXECUTE_READWRITE, &old)) {
			memcpy(g_nextHooks[i].fn, g_nextHooks[i].orig, 5);
			VirtualProtect(g_nextHooks[i].fn, 5, old, &old);
			FlushInstructionCache(GetCurrentProcess(), g_nextHooks[i].fn, 5);
		}
	}
	g_nNextHooks = 0;
}

static void UnpatchSeeders(void) {
	for (int i = 0; i < g_nSeedPatches; i++) {
		DWORD old;
		if (VirtualProtect(g_seedPatches[i].imm, 4, PAGE_EXECUTE_READWRITE, &old)) {
			*(DWORD *)g_seedPatches[i].imm = g_seedPatches[i].orig;
			VirtualProtect(g_seedPatches[i].imm, 4, old, &old);
		}
	}
	g_nSeedPatches = 0;
	g_rng.on = 0;
}

struct IatHook {
	const char *module;   // NULL = the exe
	const char *dll;
	const char *func;
	void *hook;
	void **slot;          // patched IAT slot (NULL if not found / not installed)
	void *orig;
};

static IatHook g_iatHooks[] = {
	{ NULL, "USER32.dll", "GetCursorPos", (void *)Hook_GetCursorPos },
	{ NULL, "USER32.dll", "GetAsyncKeyState", (void *)Hook_GetAsyncKeyState },
	{ NULL, "USER32.dll", "GetKeyState", (void *)Hook_GetKeyState },
	{ "GZWIND.DLL", "USER32.dll", "GetCursorPos", (void *)Hook_GetCursorPos },
	{ "GZWIND.DLL", "USER32.dll", "GetAsyncKeyState", (void *)Hook_GetAsyncKeyState },
	{ "GZWIND.DLL", "USER32.dll", "GetKeyState", (void *)Hook_GetKeyState },
	{ "GZGraphicD.dll", "USER32.dll", "GetKeyState", (void *)Hook_GetKeyState },
	{ "SIMRCI.DLL", "MSVCRT.dll", "rand", (void *)Hook_rand },
	{ "SIMSERV.DLL", "MSVCRT.dll", "rand", (void *)Hook_rand },
	{ "SIMECO.DLL", "MSVCRT.dll", "rand", (void *)Hook_rand },
	{ "SIMDSTR.DLL", "MSVCRT.dll", "rand", (void *)Hook_rand },
	{ "SimTransit.dll", "MSVCRT.dll", "rand", (void *)Hook_rand },
};

// Find the IAT slot through which `mod` calls dll!func: by import name (so a slot another bridge instance
// already hooked is found too), else by the slot's current value.
static void **FindIATSlot(HMODULE mod, const char *dll, const char *func) {
	BYTE *base = (BYTE *)mod;
	HMODULE target = GetModuleHandleA(dll);
	void *real = target ? (void *)GetProcAddress(target, func) : NULL;
	if (!base || !real)
		return NULL;
	IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(base + ((IMAGE_DOS_HEADER *)base)->e_lfanew);
	IMAGE_DATA_DIRECTORY dd = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
	if (!dd.VirtualAddress)
		return NULL;
	for (IMAGE_IMPORT_DESCRIPTOR *d = (IMAGE_IMPORT_DESCRIPTOR *)(base + dd.VirtualAddress); d->Name; d++) {
		if (_stricmp((const char *)(base + d->Name), dll) != 0)
			continue;
		void **iat = (void **)(base + d->FirstThunk);
		if (d->OriginalFirstThunk) {
			IMAGE_THUNK_DATA32 *names = (IMAGE_THUNK_DATA32 *)(base + d->OriginalFirstThunk);
			for (int i = 0; names[i].u1.AddressOfData; i++) {
				if (IMAGE_SNAP_BY_ORDINAL32(names[i].u1.Ordinal))
					continue;
				IMAGE_IMPORT_BY_NAME *ibn = (IMAGE_IMPORT_BY_NAME *)(base + names[i].u1.AddressOfData);
				if (strcmp((const char *)ibn->Name, func) == 0)
					return &iat[i];
			}
		}
		for (void **slot = iat; *slot; slot++)
			if (*slot == real)
				return slot;
	}
	return NULL;
}

static BOOL PatchPtr(void **slot, void *value) {
	DWORD old;
	if (!VirtualProtect(slot, sizeof(void *), PAGE_READWRITE, &old))
		return FALSE;
	*slot = value;
	VirtualProtect(slot, sizeof(void *), old, &old);
	return TRUE;
}

static void InstallHooks(void) {
	HMODULE u = GetModuleHandleA("USER32.dll");
	g_realGetCursorPos = (GetCursorPosFn)GetProcAddress(u, "GetCursorPos");
	g_realGetAsyncKeyState = (KeyStateFn)GetProcAddress(u, "GetAsyncKeyState");
	g_realGetKeyState = (KeyStateFn)GetProcAddress(u, "GetKeyState");
	g_realRand = (RandFn)GetProcAddress(GetModuleHandleA("MSVCRT.dll"), "rand");
	g_rng.uiTid = GetCurrentThreadId();
	int n = 0;
	for (int i = 0; i < (int)(sizeof(g_iatHooks) / sizeof(g_iatHooks[0])); i++) {
		IatHook *h = &g_iatHooks[i];
		HMODULE m = h->module ? GetModuleHandleA(h->module) : GetModuleHandleA(NULL);
		void **slot = FindIATSlot(m, h->dll, h->func);
		if (slot && PatchPtr(slot, h->hook)) {
			h->slot = slot;
			h->orig = GetProcAddress(GetModuleHandleA(h->dll), h->func);
			n++;
		}
		else
			Msg("IAT hook %s!%s in %s not installed", h->dll, h->func, h->module ? h->module : "exe");
	}
	g_bridge.hooksInstalled = n ? n : 1;
}

static void RemoveHooks(void) {
	for (int i = 0; i < (int)(sizeof(g_iatHooks) / sizeof(g_iatHooks[0])); i++) {
		IatHook *h = &g_iatHooks[i];
		if (h->slot && *h->slot == h->hook)
			PatchPtr(h->slot, h->orig);
		h->slot = NULL;
	}
	g_fake.until = 0;
	g_bridge.hooksInstalled = 0;
}

// ---------------------------------------------------------------------------
// Synthetic input (runs on the UI thread; messages go straight to the game's window procedure)

static void FakeCursor(int x, int y, DWORD holdMs) {
	POINT pt = { x, y };
	ClientToScreen(g_hwndMain, &pt);
	g_fake.screen = pt;
	g_fake.until = GetTickCount() + (holdMs ? holdMs : 1);
}

static void SendMouse(UINT msg, WPARAM keys, int x, int y) {
	SendMessageA(g_hwndMain, msg, keys, MAKELPARAM(x, y));
}

static int DoMouse(int action, int x, int y, int holdMs, int x2, int y2) {
	if (holdMs <= 0)
		holdMs = 600;
	memset(g_fake.down, 0, sizeof(g_fake.down));
	FakeCursor(x, y, holdMs);
	switch (action) {
	case MOUSE_MOVE:
		SendMouse(WM_MOUSEMOVE, 0, x, y);
		break;
	case MOUSE_LCLICK:
		SendMouse(WM_MOUSEMOVE, 0, x, y);
		g_fake.down[VK_LBUTTON] = 1;
		SendMouse(WM_LBUTTONDOWN, MK_LBUTTON, x, y);
		g_fake.down[VK_LBUTTON] = 0;
		SendMouse(WM_LBUTTONUP, 0, x, y);
		break;
	case MOUSE_RCLICK:
		SendMouse(WM_MOUSEMOVE, 0, x, y);
		g_fake.down[VK_RBUTTON] = 1;
		SendMouse(WM_RBUTTONDOWN, MK_RBUTTON, x, y);
		g_fake.down[VK_RBUTTON] = 0;
		SendMouse(WM_RBUTTONUP, 0, x, y);
		break;
	case MOUSE_LDOWN:
		SendMouse(WM_MOUSEMOVE, 0, x, y);
		g_fake.down[VK_LBUTTON] = 1;
		SendMouse(WM_LBUTTONDOWN, MK_LBUTTON, x, y);
		break;
	case MOUSE_LUP:
		SendMouse(WM_LBUTTONUP, 0, x, y);
		break;
	case MOUSE_LDRAG: {
		SendMouse(WM_MOUSEMOVE, 0, x, y);
		g_fake.down[VK_LBUTTON] = 1;
		SendMouse(WM_LBUTTONDOWN, MK_LBUTTON, x, y);
		int steps = 8;
		for (int i = 1; i <= steps; i++) {
			int cx = x + (x2 - x) * i / steps, cy = y + (y2 - y) * i / steps;
			FakeCursor(cx, cy, holdMs);
			SendMouse(WM_MOUSEMOVE, MK_LBUTTON, cx, cy);
		}
		g_fake.down[VK_LBUTTON] = 0;
		SendMouse(WM_LBUTTONUP, 0, x2, y2);
		break;
	}
	case MOUSE_WHEEL:
		SendMessageA(g_hwndMain, WM_MOUSEWHEEL, MAKEWPARAM(0, (short)x2), MAKELPARAM(x, y));
		break;
	case MOUSE_RELEASE:
		g_fake.until = 0;
		break;
	default:
		Msg("unknown mouse action %d", action);
		return -1;
	}
	return 0;
}

static int DoKey(int vk, int action, int mods, int ch) {
	memset(g_fake.down, 0, sizeof(g_fake.down));
	if (!FakeActive()) {
		POINT pt;
		g_realGetCursorPos(&pt);
		g_fake.screen = pt;
	}
	g_fake.until = GetTickCount() + 300;
	if (mods & 1) g_fake.down[VK_SHIFT] = g_fake.down[VK_LSHIFT] = 1;
	if (mods & 2) g_fake.down[VK_CONTROL] = g_fake.down[VK_LCONTROL] = 1;
	if (mods & 4) g_fake.down[VK_MENU] = g_fake.down[VK_LMENU] = 1;
	UINT scan = MapVirtualKeyA(vk, 0);
	UINT down = (mods & 4) ? WM_SYSKEYDOWN : WM_KEYDOWN, up = (mods & 4) ? WM_SYSKEYUP : WM_KEYUP;
	if (action == KEY_PRESS || action == KEY_DOWN) {
		g_fake.down[vk & 0xFF] = 1;
		SendMessageA(g_hwndMain, down, vk, 1 | (scan << 16));
		if (ch)
			SendMessageA(g_hwndMain, (mods & 4) ? WM_SYSCHAR : WM_CHAR, ch, 1 | (scan << 16));
	}
	if (action == KEY_PRESS || action == KEY_UP) {
		g_fake.down[vk & 0xFF] = 0;
		SendMessageA(g_hwndMain, up, vk, 1 | (scan << 16) | 0xC0000000);
	}
	return 0;
}

// ---------------------------------------------------------------------------
// Call tracing (dynamic RE): an object's vtable pointer is swapped for a copy whose slots go through
// logging thunks (object mode), or a class vtable's slots are patched in place (class mode). Each call
// records slot, this, caller and the first 4 stack args in g_trace, then jumps to the original method
// with registers and stack untouched.

#define TRACE_SLOTS 4096
#pragma pack(push, 4)
struct TraceBlock {
	DWORD magic;     // 'SC3T'
	DWORD seq;       // records ever written; slot = (seq - 1) % TRACE_SLOTS
	DWORD enabled;
	DWORD reserved;
	struct Rec { DWORD seq, tick, tagSlot, thisPtr, ret, a[4], tid; } recs[TRACE_SLOTS];
};
#pragma pack(pop)
extern "C" __declspec(dllexport) TraceBlock g_trace = { 0x54334353 };

struct Traced {
	DWORD addr;      // object (mode 1) or vtable (mode 2)
	DWORD origVt;    // mode 1: original vtable pointer
	DWORD *copy;     // mode 1: our vtable copy
	DWORD *slots;    // mode 2: patched vtable
	DWORD orig[256]; // mode 2: original slot values
	int n, mode;
	BYTE *thunks;
};
static Traced g_traced[16];
static int g_nTraced;

static void __cdecl TraceRecord(DWORD *f) {
	// f: pushad frame (edi, esi, ebp, esp, ebx, edx, ecx, eax), then orig, tagSlot, ret, args...
	if (!g_trace.enabled)
		return;
	DWORD seq = InterlockedIncrement((LONG *)&g_trace.seq);
	TraceBlock::Rec *r = &g_trace.recs[(seq - 1) % TRACE_SLOTS];
	r->tick = GetTickCount();
	r->tagSlot = f[9];
	r->thisPtr = f[6];
	r->ret = f[10];
	for (int i = 0; i < 4; i++)
		r->a[i] = f[11 + i];
	r->tid = GetCurrentThreadId();
	r->seq = seq;
}

static __declspec(naked) void TraceStub(void) {
	__asm {
		pushad
		mov eax, esp
		push eax
		call TraceRecord
		add esp, 4
		popad
		pop eax          // original method (eax is scratch at a call boundary)
		add esp, 4       // tag/slot
		jmp eax
	}
}

static BYTE *MakeThunks(const DWORD *orig, int n, DWORD tag) {
	BYTE *t = (BYTE *)VirtualAlloc(NULL, n * 16, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
	if (!t)
		return NULL;
	for (int i = 0; i < n; i++) {
		BYTE *p = t + i * 16;
		p[0] = 0x68; *(DWORD *)(p + 1) = (tag << 16) | (DWORD)i;   // push tag|slot
		p[5] = 0x68; *(DWORD *)(p + 6) = orig[i];                  // push original
		p[10] = 0xE9; *(LONG *)(p + 11) = (LONG)((BYTE *)TraceStub - (p + 15));
		p[15] = 0xCC;
	}
	return t;
}

static int TraceAdd(int mode, DWORD addr, int n, DWORD tag) {
	if (g_nTraced >= 16 || n <= 0 || n > 256)
		return -1;
	Traced *t = &g_traced[g_nTraced];
	memset(t, 0, sizeof(*t));
	t->addr = addr;
	t->n = n;
	t->mode = mode;
	if (mode == 1) {
		DWORD *vt = *(DWORD **)addr;
		t->origVt = (DWORD)vt;
		t->thunks = MakeThunks(vt, n, tag);
		t->copy = (DWORD *)VirtualAlloc(NULL, n * 4, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
		if (!t->thunks || !t->copy)
			return -2;
		for (int i = 0; i < n; i++)
			t->copy[i] = (DWORD)(t->thunks + i * 16);
		*(DWORD **)addr = t->copy;
	}
	else {
		DWORD *vt = (DWORD *)addr;
		memcpy(t->orig, vt, n * 4);
		t->thunks = MakeThunks(vt, n, tag);
		if (!t->thunks)
			return -2;
		DWORD old;
		if (!VirtualProtect(vt, n * 4, PAGE_READWRITE, &old))
			return -3;
		for (int i = 0; i < n; i++)
			vt[i] = (DWORD)(t->thunks + i * 16);
		VirtualProtect(vt, n * 4, old, &old);
		t->slots = vt;
	}
	g_nTraced++;
	g_trace.enabled = 1;
	return 0;
}

static void TraceRemoveAll(void) {
	for (int k = g_nTraced - 1; k >= 0; k--) {
		Traced *t = &g_traced[k];
		if (t->mode == 1) {
			__try {
				if (*(DWORD **)t->addr == t->copy)
					*(DWORD *)t->addr = t->origVt;
			}
			__except (EXCEPTION_EXECUTE_HANDLER) {
			}
		}
		else if (t->slots) {
			DWORD old;
			VirtualProtect(t->slots, t->n * 4, PAGE_READWRITE, &old);
			memcpy(t->slots, t->orig, t->n * 4);
			VirtualProtect(t->slots, t->n * 4, old, &old);
		}
		// thunks/copies are deliberately leaked: a call already inside a thunk may still return through it
	}
	g_nTraced = 0;
	g_trace.enabled = 0;
}

// ---------------------------------------------------------------------------
// Hardware watchpoints (dynamic RE): DR0..DR3 on every game thread + a vectored exception handler that
// counts the instructions that touched the watched address (EIP is the instruction *after* the access).

#define WATCH_HITS 128
#pragma pack(push, 4)
struct WatchBlock {
	DWORD magic;     // 'SC3W'
	DWORD total;     // hits ever
	DWORD addr[4];
	DWORD nUnique;
	struct Hit { DWORD eip, count, slot, ret, value, tid, f1, f2, f3; } hits[WATCH_HITS];   // f1..f3: callers
};
#pragma pack(pop)
extern "C" __declspec(dllexport) WatchBlock g_watch = { 0x57334353 };

static PVOID g_veh;
static DWORD g_dr7;
static DWORD g_dr[4];

static LONG CALLBACK WatchHandler(EXCEPTION_POINTERS *ep) {
	if (ep->ExceptionRecord->ExceptionCode != EXCEPTION_SINGLE_STEP)
		return EXCEPTION_CONTINUE_SEARCH;
	CONTEXT *c = ep->ContextRecord;
	DWORD dr6 = c->Dr6;
	if (!(dr6 & 0xF))
		return EXCEPTION_CONTINUE_SEARCH;
	int slot = (dr6 & 1) ? 0 : (dr6 & 2) ? 1 : (dr6 & 4) ? 2 : 3;
	g_watch.total++;
	DWORD eip = c->Eip;
	DWORD fr[3] = { 0, 0, 0 };       // return addresses up the EBP chain (functions with frames)
	__try {
		DWORD *bp = (DWORD *)c->Ebp;
		for (int k = 0; k < 3 && bp; k++) {
			fr[k] = bp[1];
			bp = (DWORD *)bp[0];
		}
	}
	__except (EXCEPTION_EXECUTE_HANDLER) {
	}
	int i;
	for (i = 0; i < (int)g_watch.nUnique; i++)
		if (g_watch.hits[i].eip == eip && g_watch.hits[i].slot == (DWORD)slot && g_watch.hits[i].f1 == fr[0]
		    && g_watch.hits[i].f2 == fr[1] && g_watch.hits[i].f3 == fr[2])
			break;
	if (i == (int)g_watch.nUnique && i < WATCH_HITS) {
		g_watch.hits[i].eip = eip;
		g_watch.hits[i].slot = slot;
		g_watch.hits[i].f1 = fr[0];
		g_watch.hits[i].f2 = fr[1];
		g_watch.hits[i].f3 = fr[2];
		g_watch.hits[i].tid = GetCurrentThreadId();
		__try {
			g_watch.hits[i].ret = *(DWORD *)c->Esp;  // often the caller when the access is in a small leaf
		}
		__except (EXCEPTION_EXECUTE_HANDLER) {
		}
		g_watch.nUnique++;
	}
	if (i < WATCH_HITS) {
		g_watch.hits[i].count++;
		__try {
			g_watch.hits[i].value = *(DWORD *)g_dr[slot];
		}
		__except (EXCEPTION_EXECUTE_HANDLER) {
		}
	}
	c->Dr6 = 0;
	return EXCEPTION_CONTINUE_EXECUTION;
}

static void ApplyDebugRegs(HANDLE th, BOOL suspend) {
	if (suspend && SuspendThread(th) == (DWORD)-1)
		return;
	CONTEXT ctx;
	memset(&ctx, 0, sizeof(ctx));
	ctx.ContextFlags = CONTEXT_DEBUG_REGISTERS;
	if (GetThreadContext(th, &ctx)) {
		ctx.Dr0 = g_dr[0]; ctx.Dr1 = g_dr[1]; ctx.Dr2 = g_dr[2]; ctx.Dr3 = g_dr[3];
		ctx.Dr7 = g_dr7;
		ctx.Dr6 = 0;
		SetThreadContext(th, &ctx);
	}
	if (suspend)
		ResumeThread(th);
}

static DWORD WINAPI ApplyAllThreads(LPVOID) {
	// runs on a helper thread so every game thread (including the UI thread) can be suspended
	DWORD me = GetCurrentThreadId(), pid = GetCurrentProcessId();
	HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
	if (snap == INVALID_HANDLE_VALUE)
		return 1;
	THREADENTRY32 te;
	te.dwSize = sizeof(te);
	for (BOOL ok = Thread32First(snap, &te); ok; ok = Thread32Next(snap, &te)) {
		if (te.th32OwnerProcessID != pid || te.th32ThreadID == me)
			continue;
		HANDLE th = OpenThread(THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT | THREAD_SET_CONTEXT, FALSE, te.th32ThreadID);
		if (th) {
			ApplyDebugRegs(th, TRUE);
			CloseHandle(th);
		}
	}
	CloseHandle(snap);
	return 0;
}

static int WatchSet(int action, DWORD addr, int len, int rw, int slot) {
	if (action == 2) {
		g_dr7 = 0;
		memset(g_dr, 0, sizeof(g_dr));
	}
	else {
		if (slot < 0 || slot > 3 || (len != 1 && len != 2 && len != 4) || (addr & (len - 1)))
			return -1;
		DWORD lenBits = len == 1 ? 0 : (len == 2 ? 1 : 3);
		DWORD rwBits = rw == 3 ? 3 : 1;
		g_dr[slot] = addr;
		g_dr7 &= ~((3u << (slot * 2)) | (0xFu << (16 + slot * 4)));
		g_dr7 |= (1u << (slot * 2)) | (((lenBits << 2) | rwBits) << (16 + slot * 4));
		g_watch.addr[slot] = addr;
		if (!g_veh)
			g_veh = AddVectoredExceptionHandler(1, WatchHandler);
		g_watch.nUnique = 0;
		g_watch.total = 0;
	}
	HANDLE t = CreateThread(NULL, 0, ApplyAllThreads, NULL, 0, NULL);
	if (!t)
		return -2;
	WaitForSingleObject(t, 5000);
	CloseHandle(t);
	if (action == 2 && g_veh) {
		RemoveVectoredExceptionHandler(g_veh);
		g_veh = NULL;
	}
	return 0;
}

// ---------------------------------------------------------------------------
// Commands

static int g_lastEdx;  // EDX of the last CallGeneric (high dword of int64 returns)

static int __declspec(noinline) CallGeneric(DWORD fn, DWORD thisPtr, int nargs, const int *a) {
	int result, hi;
	__asm {
		mov esi, a
		mov ecx, nargs
		mov edi, esp
	push_loop:
		test ecx, ecx
		jz do_call
		dec ecx
		push dword ptr [esi + ecx * 4]
		jmp push_loop
	do_call:
		mov ecx, thisPtr
		call fn
		mov esp, edi
		mov result, eax
		mov hi, edx
	}
	g_lastEdx = hi;
	return result;
}


// ---------------------------------------------------------------------------
// Game commands (menu items / tools) and deferred calls

typedef void (__thiscall *MakeCommandFn)(void **holder, DWORD id);
typedef void *(__cdecl *OperatorNewFn)(size_t size);
typedef void (__thiscall *VariantU32Fn)(void *variant, DWORD value, DWORD type);

static DWORD VFn(void *obj, int slot) {
	return (*(DWORD **)obj)[slot];
}

static int RunCommand(DWORD id, int nparams, const int *params, int *ok) {
	void *cmd = NULL;
	((MakeCommandFn)FN_MAKE_COMMAND)(&cmd, id);
	if (!cmd) {
		Msg("no command factory knows id 0x%08X", id);
		return -2;
	}
	void *vars[3] = { 0, 0, 0 };
	if (nparams < 0) nparams = 0;
	if (nparams > 3) nparams = 3;
	for (int i = 0; i < nparams; i++) {
		void *v = ((OperatorNewFn)FN_OPERATOR_NEW)(0x28);
		if (!v)
			return -3;
		((VariantU32Fn)FN_VARIANT_U32)(v, (DWORD)params[i], 3);
		CallGeneric(VFn(v, 1), (DWORD)v, 0, NULL);                       // AddRef
		CallGeneric(VFn(cmd, 3), (DWORD)cmd, 1, (const int *)&v);        // cmd->vt[0x0C](variant)
		vars[i] = v;
	}
	*ok = CallGeneric(VFn(cmd, 11), (DWORD)cmd, 0, NULL) & 0xFF;      // cmd->vt[0x2C]() execute
	for (int i = 0; i < nparams; i++)
		if (vars[i])
			CallGeneric(VFn(vars[i], 2), (DWORD)vars[i], 0, NULL);      // Release
	CallGeneric(VFn(cmd, 2), (DWORD)cmd, 0, NULL);                       // Release
	return 0;
}


// ---------------------------------------------------------------------------
// Tool input in world coordinates: the camera object's vtable is swapped for a copy whose pick slot
// (vt+0x8C: bool Pick(int sx, int sy, int out[3], int flag)) returns our world point for our fake screen
// coordinates, then the current tool's own mouse handlers are called (slot 8 down, 12 move, 10 up), exactly
// what the city view does with real mouse input. Everything else passes through to the real camera.

#define CAM_PICK_SLOT 35
#define CAM_VT_SLOTS 80
#define TOOL_SLOT_DOWN 8
#define TOOL_SLOT_UP 10
#define TOOL_SLOT_MOVE 12
#define FAKE_SX 7    // fake screen point i = (FAKE_SX + i, FAKE_SY)
#define FAKE_SY 7

typedef BOOL (__fastcall *PickFn)(void *cam, void *edx, int sx, int sy, int *out, int flag);
static PickFn g_origPick;
static int g_pickN;
static int g_pickPts[16][3];
static DWORD g_camVtCopy[CAM_VT_SLOTS];

static BOOL __fastcall PickHook(void *cam, void *edx, int sx, int sy, int *out, int flag) {
	int i = sx - FAKE_SX;
	if (sy == FAKE_SY && i >= 0 && i < g_pickN && out) {
		out[0] = g_pickPts[i][0];
		out[1] = g_pickPts[i][1];
		out[2] = g_pickPts[i][2];
		return TRUE;
	}
	return g_origPick(cam, edx, sx, sy, out, flag);
}

static int ToolPoints(void *tool, void *cam, int n, int mode, int keys, const int *pts) {
	if (!tool || !cam || n < 1 || n > 16)
		return -1;
	if (g_pickN) {  // another tool operation is waiting inside a game dialog
		Msg("a tool operation is still running (a game dialog is open)");
		return -5;
	}
	memcpy(g_pickPts, pts, n * 3 * sizeof(int));
	g_pickN = n;
	DWORD *origVt = *(DWORD **)cam;
	memcpy(g_camVtCopy, origVt, sizeof(g_camVtCopy));
	g_origPick = (PickFn)origVt[CAM_PICK_SLOT];
	g_camVtCopy[CAM_PICK_SLOT] = (DWORD)PickHook;
	*(DWORD **)cam = g_camVtCopy;
	int st = 0;
	__try {
		int down[3], move[3], up[3];
		if (mode == 1) {  // click each point
			for (int i = 0; i < n; i++) {
				down[0] = FAKE_SX + i; down[1] = FAKE_SY; down[2] = keys ? keys : 0x10;
				up[0] = FAKE_SX + i; up[1] = FAKE_SY; up[2] = 0;
				CallGeneric(VFn(tool, TOOL_SLOT_MOVE), (DWORD)tool, 3, up);
				CallGeneric(VFn(tool, TOOL_SLOT_DOWN), (DWORD)tool, 3, down);
				CallGeneric(VFn(tool, TOOL_SLOT_UP), (DWORD)tool, 3, up);
			}
		}
		else {  // press at point 0, move through the others, release at the last
			move[0] = FAKE_SX; move[1] = FAKE_SY; move[2] = 0;
			CallGeneric(VFn(tool, TOOL_SLOT_MOVE), (DWORD)tool, 3, move);
			down[0] = FAKE_SX; down[1] = FAKE_SY; down[2] = keys ? keys : 0x10;
			CallGeneric(VFn(tool, TOOL_SLOT_DOWN), (DWORD)tool, 3, down);
			for (int i = 1; i < n; i++) {
				move[0] = FAKE_SX + i; move[2] = keys ? keys : 0x10;
				CallGeneric(VFn(tool, TOOL_SLOT_MOVE), (DWORD)tool, 3, move);
			}
			up[0] = FAKE_SX + n - 1; up[1] = FAKE_SY; up[2] = 0;
			CallGeneric(VFn(tool, TOOL_SLOT_UP), (DWORD)tool, 3, up);
		}
	}
	__except (EXCEPTION_EXECUTE_HANDLER) {
		Msg("exception 0x%08X in tool handler", GetExceptionCode());
		st = -100;
	}
	if (*(DWORD **)cam == g_camVtCopy)
		*(DWORD **)cam = origVt;
	g_pickN = 0;
	return st;
}


// ---------------------------------------------------------------------------
// Occupant scan: walk an occupant manager's tile grid (SIMGEOM vtable 0x10029E24: +0x98 grid<occ*>,
// +0x9C grid<u8 flags>; grid = {vt, dimX, dimY, rows}; elem(x,y) = rows[x][y]) and report each unique
// occupant once with its category (vt+0x88) and tile rect (vt+0xD0).

#define OCC_HASH 131072
static DWORD g_occSeen[OCC_HASH];

static BOOL OccSeen(DWORD p) {
	DWORD h = (p >> 3) * 2654435761u;
	for (DWORD i = 0; i < OCC_HASH; i++) {
		DWORD k = (h + i) & (OCC_HASH - 1);
		if (g_occSeen[k] == p)
			return TRUE;
		if (!g_occSeen[k]) {
			g_occSeen[k] = p;
			return FALSE;
		}
	}
	return TRUE;
}

static int OccScan(BYTE *mgr, DWORD *out, int maxRec, int x0, int y0, int x1, int y1, int *count) {
	BYTE *cellsGrid = *(BYTE **)(mgr + 0x98), *flagsGrid = *(BYTE **)(mgr + 0x9C);
	if (!cellsGrid || !flagsGrid)
		return -2;
	int W = *(int *)(cellsGrid + 4), H = *(int *)(cellsGrid + 8);
	DWORD **cells = *(DWORD ***)(cellsGrid + 0xC);
	BYTE **flags = *(BYTE ***)(flagsGrid + 0xC);
	if (x0 < 0) x0 = 0;
	if (y0 < 0) y0 = 0;
	if (x1 >= W || x1 < 0) x1 = W - 1;
	if (y1 >= H || y1 < 0) y1 = H - 1;
	memset(g_occSeen, 0, sizeof(g_occSeen));
	int n = 0;
	for (int x = x0; x <= x1; x++) {
		for (int y = y0; y <= y1; y++) {
			BYTE f = flags[x][y];
			if (!(f & 1))
				continue;
			DWORD p = cells[x][y];
			if (f & 2)
				p = cells[p & 0xFFFF][p >> 16];
			if (!p || OccSeen(p))
				continue;
			if (n >= maxRec) {
				*count = n;
				return 1;  // truncated
			}
			DWORD *rec = out + n * 8;
			rec[0] = p;
			__try {
				rec[7] = ((DWORD *)p)[5];  // agent state dword (+0x14): 1 working, 2 abandoned, 4 building...
			}
			__except (EXCEPTION_EXECUTE_HANDLER) {
				rec[7] = 0;
			}
			DWORD oid = 0;
			__try {
				// building object: +4 owner clsid 0x207EDC0E, +0xC occupant id; service wrappers point at the
				// building's +0x14 interface from their +4
				DWORD *q = (DWORD *)p;
				if (q[1] == 0x207EDC0E)
					oid = q[3];
				else if (q[1] > 0x10000 && ((DWORD *)(q[1] - 0x14))[1] == 0x207EDC0E)
					oid = ((DWORD *)(q[1] - 0x14))[3];
			}
			__except (EXCEPTION_EXECUTE_HANDLER) {
				oid = 0;
			}
			rec[6] = oid;
			int r[4] = { 0, 0, 0, 0 };
			int cat = 0;
			__try {
				cat = CallGeneric(VFn((void *)p, 0x88 / 4), p, 0, NULL);
				int *pr = r;
				CallGeneric(VFn((void *)p, 0xD0 / 4), p, 1, (const int *)&pr);
			}
			__except (EXCEPTION_EXECUTE_HANDLER) {
				cat = -1;
			}
			rec[1] = cat;
			rec[2] = r[0]; rec[3] = r[1]; rec[4] = r[2]; rec[5] = r[3];
			n++;
		}
	}
	*count = n;
	return 0;
}

// one pending deferred call (fn/this/args, a command, or tool points)
static struct {
	BOOL isCommand, isToolPoints;
	DWORD fn, thisPtr, cmdId;
	int nargs, args[8];
	int pts[16][3];
} g_defer;

static DWORD WINAPI UnloadThread(LPVOID) {
	Sleep(250);
	UnregisterClassA(g_className, g_hModule);
	FreeLibraryAndExitThread(g_hModule, 0);
	return 0;
}

static int Execute(DWORD op) {
	int *a = g_bridge.args;
	int *r = g_bridge.ret;

	switch (op) {
	case OP_PING:
		r[0] = BRIDGE_VERSION;
		r[1] = (int)GetCurrentThreadId();
		r[2] = (int)g_bridge.hooksInstalled;
		r[3] = (int)(UINT_PTR)g_hModule;
		return 0;

	case OP_CALL:
		r[0] = CallGeneric((DWORD)a[0], (DWORD)a[3], a[2] < 0 ? 0 : (a[2] > 8 ? 8 : a[2]), &a[4]);
		r[1] = g_lastEdx;
		return 0;

	case OP_CALL_SEQ: {
		int n = a[0];
		int maxn = (int)(sizeof(g_bridge.str) / sizeof(CallDesc));
		if (n < 0 || n > maxn) {
			Msg("call sequence must have 0..%d entries", maxn);
			return -1;
		}
		// nargs bits: 0..7 count; 8..13 arg j is an address to read the actual dword from at call time;
		// 14 `this` is such an address; 15 `fn` is a vtable slot index of `this`.
		CallDesc *d = (CallDesc *)g_bridge.str;
		for (int i = 0; i < n; i++) {
			int cnt = d[i].nargs & 0xFF;
			if (cnt > 6) cnt = 6;
			int ind = (d[i].nargs >> 8) & 0x3F;
			DWORD th = (d[i].nargs & (1 << 14)) ? *(DWORD *)d[i].thisPtr : d[i].thisPtr;
			DWORD fn = (d[i].nargs & (1 << 15)) ? (*(DWORD **)th)[d[i].fn] : d[i].fn;
			int args[6];
			for (int j = 0; j < 6; j++)
				args[j] = ((ind >> j) & 1) ? *(int *)d[i].args[j] : d[i].args[j];
			int v = CallGeneric(fn, th, cnt, args);
			r[i < 16 ? i : 15] = v;
		}
		return 0;
	}

	case OP_MOUSE:
		return DoMouse(a[0], a[1], a[2], a[3], a[4], a[5]);

	case OP_KEY:
		return DoKey(a[0], a[1], a[2], a[3]);

	case OP_TRACE:
		if (a[0] == 3) {
			TraceRemoveAll();
			return 0;
		}
		return TraceAdd(a[0], (DWORD)a[1], a[2], (DWORD)a[3]);

	case OP_WATCH:
		return WatchSet(a[0], (DWORD)a[1], a[2], a[3], a[4]);

	case OP_COMMAND: {
		if (a[5]) {  // defer: run from the message loop so a modal window it opens doesn't block the bridge
			if (g_bridge.state.deferDone != g_bridge.state.deferPosted) {
				Msg("a deferred call is still running");
				return -5;
			}
			g_defer.isCommand = TRUE;
			g_defer.isToolPoints = FALSE;
			g_defer.cmdId = (DWORD)a[0];
			g_defer.nargs = a[1];
			memcpy(g_defer.args, &a[2], 3 * sizeof(int));
			g_bridge.state.deferPosted++;
			PostMessageA(g_hwndBridge, WM_SC3KBRIDGE_DEFERRED, 0, 0);
			return 0;
		}
		int ok = 0;
		int st = RunCommand((DWORD)a[0], a[1], &a[2], &ok);
		r[0] = ok;
		return st;
	}

	case OP_OCC_SCAN: {
		int cnt = 0;
		int st = OccScan((BYTE *)a[0], (DWORD *)a[1], a[2], a[3], a[4], a[5], a[6], &cnt);
		r[0] = cnt;
		r[1] = st;
		return st < 0 ? st : 0;
	}

	case OP_TOOL_POINTS:
		if (a[5]) {  // defer (a tool may open a modal window, e.g. the neighbor-connection question)
			if (g_bridge.state.deferDone != g_bridge.state.deferPosted) {
				Msg("a deferred call is still running");
				return -5;
			}
			if (a[2] < 1 || a[2] > 16)
				return -1;
			g_defer.isCommand = FALSE;
			g_defer.isToolPoints = TRUE;
			memcpy(g_defer.args, a, 5 * sizeof(int));
			memcpy(g_defer.pts, g_bridge.str, a[2] * 3 * sizeof(int));
			g_bridge.state.deferPosted++;
			PostMessageA(g_hwndBridge, WM_SC3KBRIDGE_DEFERRED, 0, 0);
			return 0;
		}
		return ToolPoints((void *)a[0], (void *)a[1], a[2], a[3], a[4], (const int *)g_bridge.str);

	case OP_DEFER:
		if (g_bridge.state.deferDone != g_bridge.state.deferPosted) {
			Msg("a deferred call is still running");
			return -5;
		}
		g_defer.isCommand = FALSE;
		g_defer.isToolPoints = FALSE;
		g_defer.fn = (DWORD)a[0];
		g_defer.thisPtr = (DWORD)a[3];
		g_defer.nargs = a[2] < 0 ? 0 : (a[2] > 8 ? 8 : a[2]);
		memcpy(g_defer.args, &a[4], 8 * sizeof(int));
		g_bridge.state.deferPosted++;
		PostMessageA(g_hwndBridge, WM_SC3KBRIDGE_DEFERRED, 0, 0);
		return 0;

	case OP_REPEAT: {
		int n = a[2] < 0 ? 0 : a[2];
		int nargs = a[3] < 0 ? 0 : (a[3] > 4 ? 4 : a[3]);
		for (int i = 0; i < n; i++)
			r[0] = CallGeneric((DWORD)a[0], (DWORD)a[1], nargs, &a[4]);
		r[1] = n;
		return 0;
	}

	case OP_INSTALL:
		InstallHooks();
		return g_bridge.hooksInstalled ? 0 : -1;

	case OP_RNG:
		if (a[0] == 1) {
			r[2] = PatchSeeders();
			g_rng.seedState = (DWORD)a[1];
			g_rng.randState = (DWORD)a[1] ^ 0x5DEECE66u;
			g_rng.uiSeed = (DWORD)a[1] * 2654435761u + 7u;
			g_rng.uiRands = 0;
			g_rng.loading = FALSE;
			HMODULE strt = GetModuleHandleA("STRTSIM.DLL");
			g_rng.cityGlobal = strt ? (DWORD *)((BYTE *)strt + 0x32C9C) : NULL;   // city = *(STRTSIM+0x32C9C)
			g_rng.seeds = g_rng.rands = 0;
			g_rng.on = 1;
		}
		else if (a[0] == 0)
			g_rng.on = 0;
		else if (a[0] == 3) {                 // draw tracing on (and reset)
			g_nextTrace.n = 0;
			r[5] = HookNexts();
		}
		else if (a[0] == 4)                   // draw tracing off
			UnhookNexts();
		r[0] = g_rng.seeds;
		r[1] = g_rng.rands;
		r[2] = g_nSeedPatches;
		r[3] = g_rng.on;
		r[4] = (int)(UINT_PTR)&g_randTrace;
		r[5] = g_nNextHooks;
		r[6] = (int)(UINT_PTR)&g_nextTrace;
		r[7] = g_rng.uiRands;
		return 0;

	case OP_UNLOAD:
		UnhookNexts();
		UnpatchSeeders();
		TraceRemoveAll();
		if (g_veh)
			WatchSet(2, 0, 0, 0, 0);
		RemoveHooks();
		g_bridge.ready = 0;
		g_bridge.hwndBridge = 0;
		DestroyWindow(g_hwndBridge);  // our own window, from inside its wndproc on its thread: allowed
		g_hwndBridge = NULL;
		CloseHandle(CreateThread(NULL, 0, UnloadThread, NULL, 0, NULL));
		return 0;
	}
	Msg("unknown op %u", op);
	return -1;
}

static int ExecuteGuarded(DWORD op) {
	__try {
		return Execute(op);
	}
	__except (EXCEPTION_EXECUTE_HANDLER) {
		Msg("exception 0x%08X while executing op %u", GetExceptionCode(), op);
		return -100;
	}
}

static int RunDeferredGuarded(void) {
	__try {
		if (g_defer.isToolPoints) {
			int *a = g_defer.args;
			g_bridge.state.deferRet = 0;
			return ToolPoints((void *)a[0], (void *)a[1], a[2], a[3], a[4], &g_defer.pts[0][0]);
		}
		if (g_defer.isCommand) {
			int ok = 0;
			int st = RunCommand(g_defer.cmdId, g_defer.nargs, g_defer.args, &ok);
			g_bridge.state.deferRet = ok;
			return st;
		}
		g_bridge.state.deferRet = CallGeneric(g_defer.fn, g_defer.thisPtr, g_defer.nargs, g_defer.args);
		return 0;
	}
	__except (EXCEPTION_EXECUTE_HANDLER) {
		return -100;
	}
}

static LRESULT CALLBACK BridgeWndProc(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam) {
	if (msg == WM_SC3KBRIDGE_DEFERRED) {
		// not marked g_inCall: a modal loop inside this call keeps pumping, so bridge commands still work
		g_bridge.state.deferStatus = RunDeferredGuarded();
		g_bridge.state.deferDone = g_bridge.state.deferPosted;
		return 0;
	}
	if (msg == WM_SC3KBRIDGE) {
		if (g_inCall)
			return -99;  // re-entrant call (e.g. a game modal loop pumping messages); refuse
		DWORD op = (DWORD)wParam ? (DWORD)wParam : g_bridge.op;
		g_bridge.msgLen = 0;
		g_bridge.msg[0] = 0;
		memset(g_bridge.ret, 0, sizeof(g_bridge.ret));
		g_cmdFlags = op == OP_CALL ? g_bridge.args[12] : (op == OP_CALL_SEQ ? g_bridge.args[1] : 0);
		InterlockedExchange(&g_inCall, op == OP_INSTALL || op == OP_UNLOAD ? 0 : 1);
		int status = ExecuteGuarded(op);
		InterlockedExchange(&g_inCall, 0);
		g_cmdFlags = 0;
		g_bridge.status = status;
		g_bridge.doneSeq = g_bridge.seq;
		return status;
	}
	return DefWindowProcA(hWnd, msg, wParam, lParam);
}

// ---------------------------------------------------------------------------
// Startup

static HWND FindGameWindow(void) {
	HWND h = NULL;
	DWORD me = GetCurrentProcessId();
	while ((h = FindWindowExA(NULL, h, "Gonzo", NULL)) != NULL) {
		DWORD pid = 0;
		GetWindowThreadProcessId(h, &pid);
		if (pid == me)
			return h;
	}
	return NULL;
}

static void CreateBridgeWindow(void) {
	WNDCLASSA wc;
	memset(&wc, 0, sizeof(wc));
	wc.lpfnWndProc = BridgeWndProc;
	wc.hInstance = g_hModule;
	wsprintfA(g_className, "SC3KBridge_%08X", (DWORD)(UINT_PTR)g_hModule);
	wc.lpszClassName = g_className;
	if (!RegisterClassA(&wc) && GetLastError() != ERROR_CLASS_ALREADY_EXISTS)
		return;
	g_hwndBridge = CreateWindowExA(0, g_className, "sc3kbridge", 0, 0, 0, 0, 0, HWND_MESSAGE, NULL, g_hModule, NULL);
	g_bridge.hwndBridge = (DWORD)(UINT_PTR)g_hwndBridge;
}

// Runs on the UI thread when it retrieves a message; creates the command window there once.
static LRESULT CALLBACK GetMsgHook(int code, WPARAM wParam, LPARAM lParam) {
	if (code >= 0 && !g_hwndBridge && GetCurrentThreadId() == g_bridge.threadId)
		CreateBridgeWindow();
	return CallNextHookEx(g_getMsgHook, code, wParam, lParam);
}

static DWORD WINAPI InitThread(LPVOID) {
	// Refuse to touch anything unless this is the exact executable we know.
	BYTE *base = (BYTE *)GetModuleHandleA(NULL);
	IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(base + ((IMAGE_DOS_HEADER *)base)->e_lfanew);
	if ((DWORD)(UINT_PTR)base != SC3U_BASE || nt->FileHeader.TimeDateStamp != SC3U_TIMESTAMP) {
		g_bridge.ready = 0xBAD;
		return 0;
	}
	g_bridge.layout[0] = offsetof(BridgeBlock, events);
	g_bridge.layout[1] = offsetof(BridgeBlock, state);
	g_bridge.layout[2] = sizeof(BridgeBlock);
	g_bridge.layout[3] = offsetof(BridgeBlock, seq);

	HWND h = NULL;
	for (int i = 0; i < 1200 && !h; i++) {
		h = FindGameWindow();
		if (!h)
			Sleep(50);
	}
	if (!h) {
		g_bridge.ready = 0xBAD + 1;
		return 0;
	}
	g_hwndMain = h;
	g_bridge.hwndMain = (DWORD)(UINT_PTR)h;
	g_bridge.threadId = GetWindowThreadProcessId(h, NULL);

	g_getMsgHook = SetWindowsHookExA(WH_GETMESSAGE, GetMsgHook, g_hModule, g_bridge.threadId);
	if (!g_getMsgHook) {
		g_bridge.ready = 0xBAD + 2;
		return 0;
	}
	for (int i = 0; i < 400 && !g_hwndBridge; i++) {
		PostMessageA(h, WM_NULL, 0, 0);
		Sleep(25);
	}
	UnhookWindowsHookEx(g_getMsgHook);
	g_getMsgHook = NULL;
	if (!g_hwndBridge) {
		g_bridge.ready = 0xBAD + 3;
		return 0;
	}
	SendMessageA(g_hwndBridge, WM_SC3KBRIDGE, OP_INSTALL, 0);
	g_bridge.ready = g_bridge.hooksInstalled ? 1 : 0xBAD + 4;
	return 0;
}

BOOL WINAPI DllMain(HINSTANCE hinst, DWORD reason, LPVOID) {
	if (reason == DLL_PROCESS_ATTACH) {
		g_hModule = hinst;
		DisableThreadLibraryCalls(hinst);
		HANDLE t = CreateThread(NULL, 0, InitThread, NULL, 0, NULL);
		if (t)
			CloseHandle(t);
	}
	return TRUE;
}
