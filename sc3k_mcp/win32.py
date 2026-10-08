"""Minimal ctypes wrappers for talking to the 32-bit SC3U.exe from 64-bit Python (copied from sc2k-mcp)."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import struct

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
u32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)

PROCESS_ALL_ACCESS = 0x1F0FFF
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_RELEASE = 0x8000
PAGE_READWRITE = 0x04
LIST_MODULES_32BIT = 0x01
SMTO_ABORTIFHUNG = 0x0002
WM_COMMAND = 0x0111

k32.OpenProcess.restype = wt.HANDLE
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.CloseHandle.argtypes = [wt.HANDLE]
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.WriteProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.VirtualAllocEx.restype = ctypes.c_void_p
k32.VirtualAllocEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wt.DWORD, wt.DWORD]
k32.VirtualFreeEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wt.DWORD]
k32.CreateRemoteThread.restype = wt.HANDLE
k32.CreateRemoteThread.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD)]
k32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
k32.GetExitCodeThread.argtypes = [wt.HANDLE, ctypes.POINTER(wt.DWORD)]
k32.GetExitCodeProcess.argtypes = [wt.HANDLE, ctypes.POINTER(wt.DWORD)]
k32.GetCurrentProcess.restype = wt.HANDLE
k32.IsProcessInJob.argtypes = [wt.HANDLE, wt.HANDLE, ctypes.POINTER(ctypes.c_int)]
psapi.EnumProcessModulesEx.argtypes = [wt.HANDLE, ctypes.POINTER(wt.HMODULE), wt.DWORD, ctypes.POINTER(wt.DWORD), wt.DWORD]
psapi.GetModuleBaseNameW.argtypes = [wt.HANDLE, wt.HMODULE, wt.LPWSTR, wt.DWORD]
psapi.EnumProcesses.argtypes = [ctypes.POINTER(wt.DWORD), wt.DWORD, ctypes.POINTER(wt.DWORD)]
u32.SendMessageTimeoutW.restype = ctypes.c_ssize_t
u32.SendMessageTimeoutW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM, wt.UINT, wt.UINT, ctypes.POINTER(ctypes.c_size_t)]
u32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
u32.IsWindow.argtypes = [wt.HWND]
u32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
u32.GetClientRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
u32.GetWindowDC.restype = wt.HDC
u32.GetWindowDC.argtypes = [wt.HWND]
u32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
u32.PrintWindow.argtypes = [wt.HWND, wt.HDC, wt.UINT]
u32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
u32.ClientToScreen.argtypes = [wt.HWND, ctypes.POINTER(wt.POINT)]
u32.IsWindowVisible.argtypes = [wt.HWND]
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.CreateCompatibleBitmap.restype = wt.HBITMAP
gdi32.CreateCompatibleBitmap.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int]
gdi32.SelectObject.restype = wt.HGDIOBJ
gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wt.HDC]
gdi32.GetDIBits.argtypes = [wt.HDC, wt.HBITMAP, wt.UINT, wt.UINT, ctypes.c_void_p, ctypes.c_void_p, wt.UINT]

try:
    u32.SetProcessDPIAware()
except Exception:
    pass


class WinError(RuntimeError):
    pass


def _check(ok, what):
    if not ok:
        raise WinError(f"{what} failed (error {ctypes.get_last_error()})")
    return ok


def find_pids(exe_name: str) -> list[int]:
    arr = (wt.DWORD * 4096)()
    needed = wt.DWORD()
    _check(psapi.EnumProcesses(arr, ctypes.sizeof(arr), ctypes.byref(needed)), "EnumProcesses")
    pids = []
    for pid in arr[: needed.value // 4]:
        h = k32.OpenProcess(0x0410, False, pid)  # QUERY_INFORMATION | VM_READ
        if not h:
            continue
        try:
            buf = ctypes.create_unicode_buffer(260)
            if psapi.GetModuleBaseNameW(h, None, buf, 260) and buf.value.lower() == exe_name.lower():
                pids.append(pid)
        finally:
            k32.CloseHandle(h)
    return pids


class Process:
    """A handle on a running 32-bit process with memory read/write helpers."""

    def __init__(self, pid: int):
        self.pid = pid
        self.handle = k32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        _check(self.handle, f"OpenProcess({pid})")

    def close(self):
        if self.handle:
            k32.CloseHandle(self.handle)
            self.handle = None

    def alive(self) -> bool:
        code = wt.DWORD()
        return bool(self.handle) and k32.GetExitCodeProcess(self.handle, ctypes.byref(code)) and code.value == 259

    def read(self, addr: int, size: int) -> bytes:
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t()
        _check(k32.ReadProcessMemory(self.handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(got)),
               f"ReadProcessMemory({addr:#x},{size})")
        return buf.raw[: got.value]

    def write(self, addr: int, data: bytes) -> None:
        got = ctypes.c_size_t()
        _check(k32.WriteProcessMemory(self.handle, ctypes.c_void_p(addr), data, len(data), ctypes.byref(got)),
               f"WriteProcessMemory({addr:#x},{len(data)})")

    def u8(self, a): return self.read(a, 1)[0]
    def i16(self, a): return struct.unpack("<h", self.read(a, 2))[0]
    def u16(self, a): return struct.unpack("<H", self.read(a, 2))[0]
    def i32(self, a): return struct.unpack("<i", self.read(a, 4))[0]
    def u32(self, a): return struct.unpack("<I", self.read(a, 4))[0]

    def modules32(self) -> dict[str, int]:
        arr = (wt.HMODULE * 1024)()
        needed = wt.DWORD()
        _check(psapi.EnumProcessModulesEx(self.handle, arr, ctypes.sizeof(arr), ctypes.byref(needed), LIST_MODULES_32BIT),
               "EnumProcessModulesEx")
        out = {}
        for hm in arr[: needed.value // ctypes.sizeof(wt.HMODULE)]:
            buf = ctypes.create_unicode_buffer(260)
            psapi.GetModuleBaseNameW(self.handle, hm, buf, 260)
            out[buf.value.lower()] = hm or 0
        return out

    def remote_call(self, func_addr: int, param: int, timeout_ms: int = 10000) -> int:
        tid = wt.DWORD()
        th = k32.CreateRemoteThread(self.handle, None, 0, ctypes.c_void_p(func_addr), ctypes.c_void_p(param), 0, ctypes.byref(tid))
        _check(th, "CreateRemoteThread")
        try:
            if k32.WaitForSingleObject(th, timeout_ms) != 0:
                raise WinError("remote thread timed out")
            code = wt.DWORD()
            k32.GetExitCodeThread(th, ctypes.byref(code))
            return code.value
        finally:
            k32.CloseHandle(th)

    def alloc(self, size: int) -> int:
        p = k32.VirtualAllocEx(self.handle, None, size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
        _check(p, "VirtualAllocEx")
        return p

    def free(self, addr: int) -> None:
        k32.VirtualFreeEx(self.handle, ctypes.c_void_p(addr), 0, MEM_RELEASE)


def pe_exports(path: str) -> dict[str, int]:
    """Return {name: rva} for a PE file's export table (tiny parser, no deps)."""
    data = open(path, "rb").read()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    opt = pe + 24
    magic = struct.unpack_from("<H", data, opt)[0]
    dd = opt + (96 if magic == 0x10B else 112)
    exp_rva, exp_size = struct.unpack_from("<II", data, dd)
    sec = opt + struct.unpack_from("<H", data, pe + 20)[0]
    sections = [struct.unpack_from("<8sIIII", data, sec + i * 40) for i in range(nsec)]

    def off(rva):
        for _, vsize, va, rawsize, rawptr in sections:
            if va <= rva < va + max(vsize, rawsize):
                return rva - va + rawptr
        raise ValueError(f"rva {rva:#x} not in any section")

    if not exp_rva:
        return {}
    e = off(exp_rva)
    nfuncs, nnames, afuncs, anames, aords = struct.unpack_from("<IIIII", data, e + 20)
    out = {}
    for i in range(nnames):
        name_rva = struct.unpack_from("<I", data, off(anames) + 4 * i)[0]
        o = off(name_rva)
        name = data[o: data.index(b"\0", o)].decode()
        ordinal = struct.unpack_from("<H", data, off(aords) + 2 * i)[0]
        out[name] = struct.unpack_from("<I", data, off(afuncs) + 4 * ordinal)[0]
    return out


def remote_export(proc: Process, dll: str, name: str) -> int:
    """Address of a SysWOW64 DLL export inside the 32-bit target (e.g. ("user32.dll", "GetWindowLongA"))."""
    base = proc.modules32().get(dll.lower())
    if not base:
        raise WinError(f"{dll} not loaded in target")
    path = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "SysWOW64", dll)
    return base + pe_exports(path)[name]


def inject_dll(proc: Process, dll_path: str) -> int:
    """LoadLibraryA a DLL into a 32-bit (WOW64) target. Returns the module base."""
    dll_path = os.path.abspath(dll_path)
    mods = proc.modules32()
    k32base = mods.get("kernel32.dll")
    if not k32base:
        raise WinError("kernel32.dll not found in target")
    syswow = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "SysWOW64", "kernel32.dll")
    rva = pe_exports(syswow)["LoadLibraryA"]
    path_bytes = dll_path.encode("mbcs") + b"\0"
    mem = proc.alloc(len(path_bytes))
    try:
        proc.write(mem, path_bytes)
        proc.remote_call(k32base + rva, mem)
    finally:
        proc.free(mem)
    base = proc.modules32().get(os.path.basename(dll_path).lower())
    if not base:
        raise WinError("LoadLibraryA in target failed")
    return base


def send_message(hwnd: int, msg: int, wparam: int = 0, lparam: int = 0, timeout_ms: int = 15000) -> int:
    result = ctypes.c_size_t()
    ok = u32.SendMessageTimeoutW(hwnd, msg, wparam, lparam, SMTO_ABORTIFHUNG, timeout_ms, ctypes.byref(result))
    if not ok:
        raise WinError(f"SendMessageTimeout failed/timed out (error {ctypes.get_last_error()})")
    return ctypes.c_int32(result.value & 0xFFFFFFFF).value


def post_message(hwnd: int, msg: int, wparam: int = 0, lparam: int = 0) -> None:
    _check(u32.PostMessageW(hwnd, msg, wparam, lparam), "PostMessage")


def window_pid(hwnd: int) -> int:
    pid = wt.DWORD()
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def capture_window(hwnd: int, client_only: bool = False):
    """Capture a window's contents (works when occluded) and return a PIL Image."""
    from PIL import Image

    rect = wt.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    wdc = u32.GetWindowDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(wdc)
    bmp = gdi32.CreateCompatibleBitmap(wdc, w, h)
    old = gdi32.SelectObject(mdc, bmp)
    try:
        u32.PrintWindow(hwnd, mdc, 2)  # PW_RENDERFULLCONTENT

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                        ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                        ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                        ("biClrImportant", wt.DWORD)]

        bih = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bih), 0)
        img = Image.frombuffer("RGB", (w, h), buf.raw, "raw", "BGRX", 0, 1)
    finally:
        gdi32.SelectObject(mdc, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mdc)
        u32.ReleaseDC(hwnd, wdc)
    if client_only:
        cr = wt.RECT()
        u32.GetClientRect(hwnd, ctypes.byref(cr))
        pt = wt.POINT(0, 0)
        u32.ClientToScreen(hwnd, ctypes.byref(pt))
        ox, oy = pt.x - rect.left, pt.y - rect.top
        img = img.crop((ox, oy, ox + cr.right, oy + cr.bottom))
    return img
