# Building Architect MCP (bat_mcp): phase 0 facts (2026-10-08)

Goal (user, 2026-10-08): a fully featured MCP for the SC3U Building Architect so agents can CREATE new buildings;
visuals should be ingested (images of the building) but without screenshots.

## Verified live
- `Apps\Baapp.exe` = "Building Architect Plus"; same GOG build stamp (0x63732172) and base (0x400000) as SC3U.exe, so
  the game's bridge DLL injects unchanged (its exe check passes; missing modules are skipped by the IAT hook
  installer). The Python identity check now accepts sc3u.exe or baapp.exe (`sc3k_mcp/bridge.py KNOWN_EXES`).
- Started without arguments it runs full screen (DDrawCompat borderless 1920x1080); `Baapp.exe -w -r1024x768` runs in
  a 1024x768 window (Gonzo class, title "Building Architect Plus"). Like the game, its window reads black through
  PrintWindow (DDrawCompat), so images must come from the program's own buffers / rendered output anyway.
- Loaded modules: baapp.exe, gzgraphicd, gzresourced, gzwind, gzserviced, simui.dll, simgeom.dll (the game's UI and
  geometry DLLs), ddraw/d3dim/d3dim700 (Direct3D immediate mode). SIMBABLD.DLL is not loaded by Baapp (it is the
  game's in-game copy of the BAT loader/renderer).
- WM_CLOSE to its window did not end it within 10 s (probably a quit confirmation; the window was black).

## Files
- Projects: `<game>\Buildings\*.bld` (17 samples). A .bld is an IXF resource database (magic D7 81 C3 80, 20-byte
  index records) - same container as the game's text tables.
- Libraries: `Apps\Res\BA\PAINTS\{WALLS,ROOFS,GROUND}\*.tga` (textures, 16 px per block face), `PROPS\<category>\
  *.bmp + *.MET`, `DETAILS\{Contemporary,Traditional}\...`, `BATConfig.ini` (lights for construct / texture / preview,
  UI colours), `UI\SHARED`, `HOTKEYS`; user additions in `Apps\BACustom\{Paints,Props,Details}` (see their Readme).
- Text: `Apps\Res\Text\ENGLISH\BATStringsMain.IXF`, `BAMBEStringsMain.IXF`.
- Rendered output for the game: `Apps\BARender\BAT.DAT` (15 buildings; see re/agents/replace/REPORT.md).

## Code
- `bat_mcp/app.py` BatApp(Game): launch windowed, attach bridge, status, quit. `bat_mcp/model.py` Architect: the
  model through the program's functions (blocks, paint, details, props, undo/redo, view buffer, zoom, modes,
  new/open/save). `render.py` (render via M vt[0x18], install into BAT.DAT with backup), `sprites.py` (IXF / RefPack /
  sprite and thumbnail decoders), `bldfile.py` (.bld reader/writer from re/agents/bld). `server.py`: FastMCP
  "buildingarchitect", 36 tools, registered via sc3k_mcp.registry; reference docs/BAT_TOOLS.md, agent guide
  bat_mcp/guide.md.
- Static RE reports: re/agents/bld/ (.bld format, byte-exact round-trip on the 17 samples), re/agents/batrender/
  (BAT.DAT sprites, render pipeline), re/agents/baapp/ (program structure, model, edit functions, palettes, camera).

## Verified live (2026-10-08)
- Window manager global Baapp 0x497124 (wm+0x38 root, +0x30 modal, +0x194 depth); message server getter 0x44F773
  (BatApp._msg_server_getter); the main menu buttons post 0x63CC6994 (New) etc. to the message server; synthetic
  clicks did not reach the start-screen hotspots (the bridge's input hooks are SC3U-oriented) - posting the same
  messages and answering dialogs with the window manager's EndModal works.
- New Building: post 0x63CC6994 -> (if the current building is dirty) "Do you want to save" box: EndModal No
  0x53018149 -> Tile Size dialog: radio group 0xA2FBB0B6 iface (+0xA4) vt[0x34](0x75C408C9 + size - 1), EndModal
  0x05C3F90C (that dialog's OK; 0x05C3F90D cancel; DoModal result checked at 0x42FB6C) -> toolkit screen (main
  window +0xCC = 2), model 8 * size cells square. Calling 0x41DA42 directly makes a model but leaves the UI on the
  start screen; experiments that way left a second main window behind (restart cleared it).
- Model functions verified: SetBlock 0x40BA33 (64 cubes in one call sequence), FindBlock 0x40B977, paint 0x40DFD8 and
  paint-with-uv 0x40E042 / detail 0x40E11E on a block copy + SetBlock, RemoveBlock 0x40C5FF, BaString append
  0x44F39B (truncate end = begin first: it APPENDS), M vt[0x38] save (28.5 KB file), M vt[0x34] load + vt[0x30] set
  current + posts 0x63CC69B9 / 0x63CC699D.
- View surface V+0x678: 822x768 RGB565 system-memory surface; lock S vt[0x1C](0x40), pixels *(D+0xF0), pitch
  *(D+0xF4) (1648), unlock vt[0x20]; 0.001 s per read. Construct mode draws untextured; paint mode textured (on the
  showcase racetrack lot). Zoom V+0x778 via view 0x43AC76(+-1) (1x1 lot: 4..5 in paint mode).
- Mode change: post {0x63CC69B7, 3, 0x63CC69A6, mode}.
- Undo log: entries 0x14 bytes at model+0x1B4, position model+0xA01A0; the program's undo (0x40F5DD) keeps going
  while the previous entry's op byte > 0, and programmatic edits write no step markers -> bat_mcp keeps per-call
  (start, end) ranges and replays them with the per-entry op function 0x40F4B2 (undo op byte 0, redo op byte 1).
  A render resets the log (history cleared).
- Render: M vt[0x18] (0x404488, the Render button's entry) with the open building kept (AddRef, render, vt[0x30]
  restore, Release) - vt[0x10] with a building open faulted (contained) and left the program inconsistent; with no
  building open vt[0x10] worked. Output to %TEMP%\sc3k-mcp\renders\<name>-<ms>.dat (unique names: a faulted render
  left its file locked).
- bldfile (re/agents/bld/bld.py) output loads in Baapp (Agent Box) and renders; props via shape-15 cells with view
  bitmaps in face slots 1..4 (paint uv = offset 1, detail uv byte = offset 2) render correctly (tree).
- Save drops completely enclosed blocks (cottage: 12 interior cubes) - the program's own behaviour.
- Gable roof verified: outer cell shape 10, inner shape 9, rotation 0 (rising to +x) / 2 (rising to -x).
- live/b1_stdio.py: all tools over MCP stdio, cottage built / saved / rendered (now 36 tools, 4 expected errors).

## Verified live, round 2 (2026-10-08)
- Rotate (view 0x43A8E5(+-1, 1) -> model 0x40B263(+-0x80)) turns the model data itself: one +1 turn moves (x, y) to
  (N-1-y, x) and adds 1 to every block's rotation; model byte +0x84 counts turns (SetBlock forces cubes and prop
  cells to that rotation). Each turn writes one undo entry (ops 3 / 4); with the model's "replaying" byte +0x1B0 set
  (the flag the undo loop 0x40F4B2 sets) nothing is logged -> view_image turns, reads, turns back without touching
  the history. Undo log: position +0xA01A0, redo limit +0x1A0184, snapshot count +0x1A0188 (append 0x40F472
  refuses while +0x1B0 is set or the log is full, 0x7FFE).
- SetBlock / RemoveBlock do not change texture-table use counts (table +0x1AC, 8-byte {count, item} per slot);
  the paint functions do. copy_blocks therefore rebuilds each copy with the paint functions. SetBlock recomputes the
  visible-face mask d1 (bit f = face f not covered).
- SetBlock refuses to put a prop cell (shape 15) over an existing block (the copy kept the house blocks) ->
  place_props / copy_blocks refuse occupied cells.
- Paint / detail with item 0 clears the face (verified, undoable).
- Fill tool = view 0x43BC71, recursive via 0x43B856: same face direction (shape face table 0x494228, 0x78 bytes per
  shape, 9 per face, + rotation), visible bit set, same paint slot; uv from 0x43B8A0. bat_mcp fill_paint follows
  the same rule by face number (exact for cubes).
- Library items load lazily: an unused item has image +0x04 = 0, id +0x10 = 0; a loaded one has the image object,
  the pixel-hash id and sizes (+0x18.. floats 64.0, 1/64; +0x30.. sprite box). Props placed with the paint function
  on an unloaded item draw as grey boxes in the view until the file is reopened (the loader loads them); paints were
  already loaded. Image setter 0x4178D8 (callers 0x413DD0, 0x4180A2, 0x4187F6, 0x419A3F).
- After save + render the live model also lacks the enclosed blocks (135 -> 123 in the cottage).
- The renderer (M vt[0x18]) draws with the view's current state: in construct mode the working plane / view volume
  clips the building (zoom-4 sprite 46 px wide instead of 64, walls cut into strips); file / paint / detail / props
  modes give identical, complete sprites. render_building switches to the File tab (the Render button's tab) for
  the render and restores the mode.
- Library loading (re/agents/batlib/REPORT.md) verified live: 0x419A77(L, cat) before using a stock item fixed the
  grey live-placed props; 0x41926E(L, cat, &BaString path) added a new BACustom paint (pixel-art BMP), detail (TGA
  with alpha) and the four bitmaps of a new prop, each loaded with an id; 0x41885D(L, 16, &met) + 0x419A77(L, 16)
  registered the prop (0x4187B5 record W/D/H 1/1/2). Re-adding a known file reloads it in place (0x4178D8(item, 0)
  + 0x419697(L, &name)). The new prop drawn on prop_template's geometry sits exactly on its cell in the view.

## Verified live, round 3: Empire State end-to-end test (2026-10-08, notes/BAT_E2E_EMPIRE_STATE.md)
- Face slots: each shape's slot carries a direction code (bldfile.SHAPES): 16 top, 48 bottom, 0..7 vertical side
  (odd = axis, even = diagonal; 7 +x, 1 +y, 3 -x, 5 -y), +8 steep slope, +32 shallow slope; rotation adds 2 per
  quarter turn (as the Fill tool 0x43BC71 compares). Cubes and props take the model rotation (+0x84), so after a
  building rotation even a cube's slot 1 is no longer -x. bat_mcp resolves faces by direction name.
- Stock prop bitmaps: squares of 32 / 64 / 128 / 256 px at one scale (cell 32 px wide, storey 16 px), the middle
  cell (index (n-1)//2) centred; e.g. radiotower1 1x1x13 in 256 px, column4 1x1x2 in 64 px. A 1x1 prop fits up to
  15 storeys.
- Game building sprites: Apps\Res\Sprites\*.DAT (IXF, group 10 in Landmarks.DAT), instance = occupant id << 16 |
  frame, frames 0..15 = zoom 1..4 x rotation 0..3 (zoom 5 = zoom 4 doubled); names from sc3k_mcp/data/
  occupants.json (979 of 1078 sprite owners named). The game's Empire State (0x252C) is a 5x5 landmark, 640 x 1430
  px at zoom 5 - taller than any Architect lot allows (4x4 max 144 cells, 5x5 max 80).
- A never-rendered .bld header ends after the architect string (no building id).
- 17,500-block tower: fill_box 6,400 blocks in 0.6 s; whole build incl. paint and props ~20 s; render 0.9 s.

## Verified live, round 4: Queen Anne end-to-end test (2026-10-08, notes/BAT_E2E_VICTORIAN.md)
- Shape tops as corner heights (bldfile.SHAPES vertices: corner v & 3 = (+x,+y), (-x,+y), (-x,-y), (+x,-y); level
  v >> 2 = bottom / top / half): cube (1,1,1,1); 2 wedge (1,0,0,1); 9 (1,.5,.5,1); 10 (.5,0,0,.5); 4 hip corner
  (0,0,0,1); 13 (.5,.5,.5,1); 14 (0,0,0,.5); 3 valley and 6 cut corner both (1,0,1,1) - 3 creases along the
  diagonal through the low corner (concave, centre 0.5), 6 along the other (convex, centre 1); 11 (1,.5,1,1);
  12 (.5,0,.5,.5). Rotation r moves corner c to (c + r) & 3. bat_mcp/roofs.py builds the lookup from this.
- Renderer colour response (render_building, zoom 5) for paint (128,128,128): top (119,117,119); +x-facing wall /
  slope (165,148,140); +y-facing wall (57,58,74); +y-facing slope (136,136,152). view_image's paint mode shows the
  same tones (both use the preview light set) - the earlier impression of different lighting was the roof colour.
- 2x2 house: ~1,300 blocks; whole build ~15 s; render 0.4 s.

## Round 5: photo to building without the Architect (2026-10-08, notes/PHOTO_TO_BUILDING.md)
- The game loads every *.DAT in Apps\BARender at start-up: a separate "MCP Photo Buildings.DAT" with group
  0xBA1DBF1E records showed up in building_replacements and replaced "Ike's House" in Madison (Query title changed).
- Sprite family frames 16-19 with scale 0 and their own 128 px-per-tile images are drawn unscaled by the game.
- The Architect writes empty image rows as {first pixel, left = width, 0x8000}.
- The Architect's lights turn with the model (compass directions); right-facing walls get 71,71,91 vs 190,174,164 on
  the left (0.37); the game's own sprites are about 0.55 - 0.65.
- FastMCP runs sync tools in a worker thread: a first `import numpy` there hung the server; import it at start-up.
- The mcp stdio client's shutdown also ends a game launched by the server in that session (one session per test).

## Verified live, round 6 (2026-10-08)
- Exit: the Architect ignores WM_CLOSE (the old bat_quit waited 15 s and gave up). The framework's Quit -
  framework *(0x4971C8), vtable 0x48414C slot 16 = 0x45F75C (PostQuitMessage, or a deferred quit flag at +0xFC) -
  closes it at once, without a save prompt.
- Command line: Baapp.exe -w -r1024x768 "<Buildings>\The Joneses.bld" starts with no building open: a path on the
  command line is ignored (live/b2_cmdline.py). open_building is the way to open a project.
- Texture table: 255 usable slots per building (M+0x1AC, slot 0 unused, one-byte slot ids in the face records).
  bat_mcp refuses a paint / detail call that would need more, before anything changes (a 1x1 tower: 260 new
  textures refused, 250 painted, then 10 more refused and 5 more painted).
- Building sets (.bst / .scs): the program's menu strings exist ("Load a Building Set", "Prepare Building Set"...),
  but its functions are stubs returning 0 in this build (re/agents/baapp/REPORT.md): nothing to drive.
