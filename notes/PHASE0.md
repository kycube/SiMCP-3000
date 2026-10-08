# Phase 0 findings (2026-10-07)

## Decisions (with the user)

- **Binaries: stock GOG install, unpatched.** Re-hash on 2026-10-07 matched the handoff survey exactly
  (`SC3U.exe` SHA-1 `b12a397c075eba12dd60b5ea5b99acdb513ca2be`, TimeDateStamp `0x63732172`; game DLLs dated
  2000-04-19). User was fine either way; stock chosen because the 4GB patch only flips a PE header bit (code
  addresses unchanged), so it can be added later, and stock keeps the build reproducible.
- **Bridge loading: GZCOM plugin in `Apps\PlugIn\`** (user approved creating that folder). Verified live; see
  GZCOM.md. The stable stub `sc3kplug.dll` lives there; the hot-reloadable bridge is injected separately.
- **RE tools:** user said "you decide". Cheat Engine reads/scans freely, breakpoints sparingly and only on
  saved throwaway cities. Ghidra/JDK not installed; ask (with download details) if capstone proves too slow.
- **Project:** this repository (then called sc3k-mcp), SC2K MCP code copied and adapted (SC2K project
  untouched). SC2K's temp RE helpers (`sdis.py`, `xref.py`, `mcpclient.py`, `RE_BRIEF.md`) were already
  deleted with their temp folder; `re/pe.py` replaces sdis/xref.

## Launching

| Method | Result |
|---|---|
| GOG's `Launch SimCity 3000 Unlimited.lnk` via `explorer.exe` (no args) | Works. Borderless fullscreen 1920x1080 (DDrawCompat), game renders 800x600. Intro movie ~30 s, then main menu. |
| `live/SC3U-windowed.lnk` via `explorer.exe`, args `-w -r1024x768 -intro:off` | Works. Captioned window, 1024x768 client; intro skipped; menu within ~4 s (menu art stays 800x600, centered). |
| `live/launch_direct.py` (CreateProcess from our Python, `CREATE_BREAKAWAY_FROM_JOB`, `__COMPAT_LAYER` replaced with GOG's flags) | Works. Breakaway allowed; game outlives the launcher; comes up foreground. |

- GOG Galaxy writes the compat flags to `HKCU`/`HKLM ...\AppCompatFlags\Layers` for `SC3U.exe`, so Explorer
  launches get them without env vars. Our processes inherit `__COMPAT_LAYER=DetectorsAppHealth`, which would
  override that, so the direct launcher sets `__COMPAT_LAYER` to GOG's string (Windows normalizes it to
  `16BitColor 8And16BitAggregateBlts HighDpiAware`).
- Registry: game reads `HKLM\SOFTWARE\WOW6432Node\Electronic Arts\Maxis\SimCity 3000 Unlimited`
  (`InstalledPath`, `Language`=1033). Nothing in HKCU yet.
- **This session's processes are not MSIX-packaged** (`GetCurrentPackageFullName` -> `APPMODEL_ERROR_NO_PACKAGE`;
  chain python <- bash <- claude.exe <- sihost.exe). They run in a job with LimitFlags 0 (no kill-on-close),
  and breakaway succeeded anyway. The SC2K HKCU-virtualization problem may not apply; not re-tested.
- The game process always reports `IsProcessInJob = TRUE`, even from Explorer (probably the PCA compat job).
- Command-line switches parsed by the exe's cmdline object (`0x469023`): `intro`, `sound`, `music` with value
  `off` (`-intro:off`), plus updater switches. `-w`/`-r` handled elsewhere (work as documented).
- **WM_CLOSE is ignored** at the main menu. Test instances were ended with TerminateProcess.

## Windows

- Main window: class **`Gonzo`**, title `SimCity 3000`, created on the UI thread.
- DDrawCompat adds `DDrawCompatPresentationWindow` (title `[DDrawCompat] SimCity 3000`) covering the game
  window, plus ~20 hidden 1x1 presentation windows, two hidden `SocketWindowClass` windows (Winsock), IME windows.
- **Capture:** `PrintWindow` on the DDrawCompat presentation window works (includes a caption in windowed
  mode). On the `Gonzo` window it returns black (fullscreen) or white (windowed).

## Bridge skeleton (verified live, `live/t1_bridge.py`, all checks pass)

- Two DLLs. `Apps\PlugIn\sc3kplug.dll` = stable GZCOM stub (loaded by the game). `sc3kbridge-<sha1>.dll` =
  hot-reloadable bridge, injected from `%TEMP%\sc3k-mcp\` with LoadLibraryA via CreateRemoteThread.
- The bridge does **not** subclass the `Gonzo` window. Its init thread installs a thread-local `WH_GETMESSAGE`
  hook on the UI thread, posts `WM_NULL` to the game window, the hook creates a message-only window
  (`HWND_MESSAGE`, class `SC3KBridge_<base>`) on the UI thread, and the hook is removed. Commands are
  `SendMessageTimeout(hwndBridge, WM_APP+0x3C3, op)`. Unload destroys that window from its own wndproc and
  frees the DLL from a helper thread.
- Results: attach 0.20 s; `OP_PING` reports the UI thread id; `OP_CALL 0x4708C4` (`GZCOM()`) returns the same
  `cIGZCOM*` the plugin got in `InitializeCOM`; `OP_CALL_SEQ` ok; calling address 0x10 returns status -100
  (`0xC0000005`) and the bridge keeps working; hot reload (unload + re-inject) 0.44 s; `detach()` leaves no
  bridge module behind.
- Block layout is published in `layout[]` (events, state, size, request offset) and checked by the client.

## Display sleep (found 2026-10-07 in Phase 1)

- When the monitor goes to sleep, DDrawCompat stops presenting: the game window freezes (or a game launched while
  the display is off shows black). The game itself keeps running (main loop 45 passes/s, sim, bridge, memory all
  fine) - only screenshots are affected. Presentation resumes once the game window is activated (a click on it);
  after that it keeps rendering while unfocused. The user enabled keep-awake for the session.
- WM_ACTIVATEAPP/WM_ACTIVATE sent by us, raising the z-order, or nudging the window did NOT restore it.
- `screenshot` therefore reports a hint when the frame is all black.

## Focus

- At the main menu the game keeps running unfocused in windowed mode (~0.2 cores focused and unfocused; not
  minimized, not hidden). Background SetForegroundWindow from our process worked to move focus *away*, but
  could not give it back (foreground lock).
- Posted mouse messages: WM_MOUSEMOVE highlights menu items, but a posted WM_LBUTTONDOWN/UP on "Start New City"
  did nothing (menu likely reads button state directly, or ignores clicks while inactive).
- Answered later (LIVE_FACTS.md): a running city keeps simulating while the window is unfocused.

## Next: Phase 1 recon (in priority order)

1. Framework vtable `0x4D6BF4`: find AddHook and any tick/idle registration (SC4 has AddToTick/AddToOnIdle).
   A UI-thread per-frame callback would give the stop-at-day hook without patching code.
2. Map class IDs to components: each director's constructor calls `AddCls(clsid, factory, 0)`; dump them for
   every SIM*/GZ* DLL and name components by DLL until better names appear.
3. Cheat Engine value scans: funds -> writer -> budget code; date -> sim tick; one tile edit -> map storage and
   dimensions; population and RCI demand.
4. Main loop (`PeekMessageA` caller in the exe) and the simulation tick vs. frame update split.
5. Start a city through the bridge (find the menu's action), then run the in-city focus test.
6. Follow the "Gonzo Debug Window" reference at `0x45FA51` (possible hidden console).
