// sc3kplug.dll - minimal GZCOM plugin for SimCity 3000 Unlimited (GOG build 2.0.949)
//
// SC3U.exe scans <Apps>\PlugIn\*.dll at startup (SC3U.exe 0x40B00F / 0x470157) and registers each
// file as a GZCOM library: LoadLibraryA, GetProcAddress("GZDllGetGZCOMDirector"), then
// director->InitializeCOM(pCOM, path) and director->EnumClassObjects(cb, ctx) (SC3U.exe 0x48A575,
// 0x48AB54). This stub is such a director. It registers no classes. It records every call the
// framework makes into the exported g_plug block (read by Python with ReadProcessMemory) and into
// %TEMP%\sc3k-mcp\plugin.log, and keeps the cIGZCOM / framework pointers for the bridge.
//
// The director layout (18 slots + an 11-slot cIGZFrameWorkHooks at +4) and the IIDs were read from
// the cRZCOMDllDirector in SIMECO.DLL (vtables 0x1001C508 / 0x1001C4DC); see notes/GZCOM.md.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stddef.h>

#define PLUG_MAGIC   0x50334353  // 'SC3P'
#define PLUG_VERSION 1
#define DIRECTOR_ID  0x5C3B41D6

#define GZIID_cIGZUnknown          0x00000001
#define GZIID_cIGZCOMDirector      0xA21EE941
#define GZIID_cIGZFrameWorkHooks   0x03FA40BF

// slot numbers recorded in the call log
enum {
	S_QI = 0, S_ADDREF, S_RELEASE, S_INITCOM, S_ONSTART, S_ENUMCLASSES, S_GETCLASS, S_CANUNLOAD, S_ONUNLOAD,
	S_REFCOUNT, S_REMOVEREF, S_FRAMEWORK, S_GZCOM, S_DIRECTORID, S_LIBPATH, S_DTOR, S_SLOT16, S_ADDDIRECTOR,
	S_HOOK0 = 20,  // + hook index 0..7
	S_ATTACH = 0xF0, S_GETDIRECTOR = 0xF1, S_DETACH = 0xF2,
};

#pragma pack(push, 4)
struct PlugBlock {
	DWORD magic;
	DWORD version;
	DWORD pCOM;          // cIGZCOM* from InitializeCOM
	DWORD pFrameWork;    // pCOM->vtable[4]() (what SIMECO stores as its framework)
	DWORD director;      // our director object
	DWORD calls[32];     // call count per slot (hooks at 20..27)
	DWORD logSeq;        // entries ever written; slot = (seq - 1) % 64
	struct Entry { DWORD seq, tick, tid, slot, a0, a1, a2; } log[64];
};
#pragma pack(pop)

extern "C" __declspec(dllexport) PlugBlock g_plug = { PLUG_MAGIC, PLUG_VERSION };

static HMODULE g_hModule;
static HANDLE g_logFile = INVALID_HANDLE_VALUE;

static void Log(DWORD slot, DWORD a0 = 0, DWORD a1 = 0, DWORD a2 = 0) {
	if (slot < 32)
		g_plug.calls[slot]++;
	DWORD seq = ++g_plug.logSeq;
	PlugBlock::Entry *e = &g_plug.log[(seq - 1) % 64];
	e->tick = GetTickCount();
	e->tid = GetCurrentThreadId();
	e->slot = slot;
	e->a0 = a0;
	e->a1 = a1;
	e->a2 = a2;
	e->seq = seq;
	if (g_logFile != INVALID_HANDLE_VALUE) {
		char line[160];
		int n = wsprintfA(line, "%lu tid=%lu slot=%lu a=%08lX %08lX %08lX\r\n", e->tick, e->tid, slot, a0, a1, a2);
		DWORD w;
		WriteFile(g_logFile, line, n, &w, NULL);
	}
}

// ---------------------------------------------------------------------------
// Interfaces (MSVC thiscall vtables match the VC6-built game)

struct cIGZUnknown {
	virtual bool QueryInterface(DWORD iid, void **ppv) = 0;
	virtual DWORD AddRef() = 0;
	virtual DWORD Release() = 0;
};

struct cIGZCOMDirector : cIGZUnknown {
	virtual bool InitializeCOM(void *pCOM, const void *libraryPath) = 0;  // slot 3
	virtual bool OnStart(void *pCOM) = 0;                                 // slot 4
	virtual void EnumClassObjects(void *callback, void *context) = 0;     // slot 5
	virtual bool GetClassObject(DWORD clsid, DWORD iid, void **ppv) = 0;  // slot 6
	virtual bool CanUnloadNow() = 0;                                      // slot 7
	virtual bool OnUnload() = 0;                                          // slot 8
	virtual DWORD RefCount() = 0;                                         // slot 9
	virtual DWORD RemoveRef() = 0;                                        // slot 10
	virtual void *FrameWork() = 0;                                        // slot 11
	virtual void *GZCOM() = 0;                                            // slot 12
	virtual DWORD GetDirectorID() = 0;                                    // slot 13
	virtual bool GetLibraryPath(void *outPath) = 0;                       // slot 14
	virtual void *ScalarDtor(DWORD flags) = 0;                            // slot 15 (virtual destructor)
	virtual bool Slot16(void *arg) = 0;                                   // slot 16 (propagated from OnStart)
	virtual void AddDirector(void *director) = 0;                         // slot 17
};

struct cIGZFrameWorkHooks : cIGZUnknown {
	virtual bool PreFrameWorkInit() = 0;
	virtual bool PreAppInit() = 0;
	virtual bool PostAppInit() = 0;
	virtual bool PreAppShutdown() = 0;
	virtual bool PostAppShutdown() = 0;
	virtual bool PostSystemServiceShutdown() = 0;
	virtual bool AbortiveQuit() = 0;
	virtual bool OnInstall() = 0;
};

class Director : public cIGZCOMDirector, public cIGZFrameWorkHooks {
public:
	DWORD refs;
	void *com;
	void *framework;

	bool QueryInterface(DWORD iid, void **ppv) {
		Log(S_QI, iid);
		if (!ppv)
			return false;
		if (iid == GZIID_cIGZUnknown || iid == GZIID_cIGZCOMDirector)
			*ppv = static_cast<cIGZCOMDirector *>(this);
		else if (iid == GZIID_cIGZFrameWorkHooks)
			*ppv = static_cast<cIGZFrameWorkHooks *>(this);
		else
			return false;
		AddRef();
		return true;
	}
	DWORD AddRef() { return ++refs; }
	DWORD Release() { return refs ? --refs : 0; }  // static object: never deleted

	bool InitializeCOM(void *pCOM, const void *libraryPath) {
		Log(S_INITCOM, (DWORD)pCOM, (DWORD)libraryPath);
		if (!pCOM)
			return false;
		com = pCOM;
		g_plug.pCOM = (DWORD)pCOM;
		__try {
			typedef void *(__fastcall *GetFn)(void *, void *);
			framework = ((GetFn)(*(void ***)pCOM)[4])(pCOM, NULL);
			g_plug.pFrameWork = (DWORD)framework;
		}
		__except (EXCEPTION_EXECUTE_HANDLER) {
			framework = NULL;
		}
		return true;
	}
	bool OnStart(void *pCOM) { Log(S_ONSTART, (DWORD)pCOM); return true; }
	void EnumClassObjects(void *callback, void *context) { Log(S_ENUMCLASSES, (DWORD)callback, (DWORD)context); }
	bool GetClassObject(DWORD clsid, DWORD iid, void **ppv) { Log(S_GETCLASS, clsid, iid); return false; }
	bool CanUnloadNow() { Log(S_CANUNLOAD); return false; }
	bool OnUnload() { Log(S_ONUNLOAD); return true; }
	DWORD RefCount() { return refs; }
	DWORD RemoveRef() { return refs ? --refs : 0; }
	void *FrameWork() { return framework; }
	void *GZCOM() { return com; }
	DWORD GetDirectorID() { return DIRECTOR_ID; }
	bool GetLibraryPath(void *outPath) { Log(S_LIBPATH, (DWORD)outPath); return false; }
	void *ScalarDtor(DWORD flags) { Log(S_DTOR, flags); return this; }
	bool Slot16(void *arg) { Log(S_SLOT16, (DWORD)arg); return true; }
	void AddDirector(void *director) { Log(S_ADDDIRECTOR, (DWORD)director); }

	bool PreFrameWorkInit() { Log(S_HOOK0 + 0); return true; }
	bool PreAppInit() { Log(S_HOOK0 + 1); return true; }
	bool PostAppInit() { Log(S_HOOK0 + 2); return true; }
	bool PreAppShutdown() { Log(S_HOOK0 + 3); return true; }
	bool PostAppShutdown() { Log(S_HOOK0 + 4); return true; }
	bool PostSystemServiceShutdown() { Log(S_HOOK0 + 5); return true; }
	bool AbortiveQuit() { Log(S_HOOK0 + 6); return true; }
	bool OnInstall() { Log(S_HOOK0 + 7); return true; }
};

static Director g_director;

extern "C" __declspec(dllexport) cIGZCOMDirector *GZDllGetGZCOMDirector(void) {
	Log(S_GETDIRECTOR, (DWORD)&g_director);
	g_plug.director = (DWORD)&g_director;
	return &g_director;
}

static void OpenLog(void) {
	char path[MAX_PATH];
	DWORD n = GetTempPathA(MAX_PATH - 32, path);
	if (!n || n > MAX_PATH - 32)
		return;
	lstrcatA(path, "sc3k-mcp");
	CreateDirectoryA(path, NULL);
	lstrcatA(path, "\\plugin.log");
	g_logFile = CreateFileA(path, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_ALWAYS,
		FILE_ATTRIBUTE_NORMAL, NULL);
}

BOOL WINAPI DllMain(HINSTANCE hinst, DWORD reason, LPVOID) {
	if (reason == DLL_PROCESS_ATTACH) {
		g_hModule = hinst;
		DisableThreadLibraryCalls(hinst);
		OpenLog();
		Log(S_ATTACH, (DWORD)hinst, GetCurrentProcessId());
	}
	else if (reason == DLL_PROCESS_DETACH) {
		Log(S_DETACH);
		if (g_logFile != INVALID_HANDLE_VALUE)
			CloseHandle(g_logFile);
	}
	return TRUE;
}
