# Baapp.exe library (L): loading, palettes, adding items at runtime (static RE by subagent; saved by main)

Static only (disassembly of Apps\Baapp.exe, base 0x400000). L methods are thiscall (ecx = L), callee cleans.
(L) = likely, (unverified) = not confirmed. Live verification notes are in notes/BAT_PHASE0.md.

## 1. How M init 0x40569D fills L
- Runs once per process (guard M+0x1C == 0, M+0x4C flag in 0x4052E1). L = new(0x54), ctor 0x41A639. Base folder from
  the directory-manager service 0x44F8B3 vt[0x1C] (Apps\, L). Paths base+"Res\BA\" and base+"BACustom\" with
  {Paints,Details,Props}\ and their subfolders.
- Order (0x405D35..0x405EB0): 0x418AF4(L, cat, &dir) for cats 0..3; 0x4054B2(L) (cdecl) generates the "color r,g,b"
  items; scan cats 4, 5; cats 8..15 scan + 0x419D46(L, cat); then cats 6, 7, 16 (BACustom) and 0x419D46(L, 16).
- Directory scan 0x418AF4(L, cat, BaString* dir) ret 8 -> bool: returns 0 if the folder does not exist (0x45870B);
  lists "." plus immediate subfolders only (lister 0x457D87 flags 4|1 via 0x458922(list, 1), no recursion); two
  passes over files (0x458914, flag 8): pass 1 lowercases (0x44F669) and pushes {cat, path} of .met files to the
  vector at L+0x0C and of .plt files to L+0x00 (0x41AAEE); pass 2 calls 0x41926E for every file.
- Per-file add 0x41926E(L, cat, BaString* fullPath) ret 8 -> bool: .bmp -> format 2 (magenta 0xFFFF00FF key), .tga
  -> format 4 (alpha), anything else returns 0 without side effects; _splitpath (0x457373) -> name = lowercase
  "file.ext"; calls 0x4195E2(L, &name, cat, &lowerFullPath, format, 0, 0, 0).
- Create item 0x4195E2 (7 args, ret 0x1C): new(0x84) Item (ctor 0x41860F); +0x48 name, +0x5C path, +0x14 flags,
  +0x0C cat; img != 0 -> 0x4178D8(item, img) (colour items); rects to +0x28 / +0x38; then Insert 0x4194A1(L, item).
- Insert 0x4194A1(L, Item*) ret 4: rejects only when both a name match (0x41874A) and an id match (0x418705) exist;
  a file item still has id 0 there, so the same file added twice gives a duplicate. Pushes to vector<Item*> L+0x3C
  (0x41AC36) when the name is not empty; cats 3, 6, 7, 16 then call 0x419697(L, &item->name) at once.
- Load + register 0x419697(L, BaString* name) ret 4 (true if a new map entry): cdecl 0x419ADE(name, L, 0) finds the
  item by name (newest first), skips cat 3 and empty paths, checks the file exists (0x456BAE), returns if item+8 is
  set (0x4185BD), else loads through the loader at M+0x30 (via 0x40F6F9) vt[0x14](BaString* path, &img, &rect), sets
  rects (+0x28 whole image; +0x38 32x32 bottom-left for cats 0-2, 6, else clamped to 156 px) and 0x4178D8(item, img);
  then inserts {id -> item} into std::map L+0x24 (0x41B5EC); an existing id keeps the older item.
- No name map: 0x41874A is a backwards linear scan of the vector with a case-sensitive memcmp (newest wins).
- Item::SetImage 0x4178D8(Item*, img | 0) ret 4: 0 releases +0, +4, +8; else w/h floats at +0x1C / +0x18 and
  reciprocals at +0x24 / +0x20, +0x10 id = CRC32 of the pixels (0x418010, table 0x495A2C built in L's ctor; bytes
  hashed unverified), +0x70 opaque bounding box, +0x14 |= 1 when fully opaque, a 16-bit DirectDraw surface at +0x04
  QI'd (IID 0x485920) to the texture at +0x08; custom categories keep the source cGZImage at +0x00 (embedded in
  saved .bld files).
- Stock items (cats 0-2, 4-5, 8-15) load lazily: id 0, not in the id map, no texture until 0x419A77(L, cat) runs
  (palette tab handler) or LoadBuilding loads what a .bld references (~0x414D94). 0x419A77 is idempotent.
- Other L fields (ctor 0x41A639): +0x18 vector of 255 per-category records (0x20: BaString + vector<Group 0x28>);
  +0x30 map<view0 id, PropRec*>; +0x48 vector<PropRec*>.

## 2. One-file add, rescan, reload
- One file: 0x41926E (above); lower: 0x4195E2 (name/path or in-memory image) and Insert 0x4194A1.
- LoadBuilding 0x4063C8 -> 0x413E1A registers reader callbacks: 0x413D94 (embedded texture item, 0x415479 ->
  0x4194A1) and 0x413DD0 (PropRec -> 0x41957A, 0x41974F).
- No rescan: 0x418AF4 (17 call sites) and 0x419D46 (9) are only called from 0x40569D. Nothing clears L at runtime
  (only 0x419934 via 0x419D83 at M shutdown 0x4052FE); re-initialising L would leave stale Item* in models and
  palette buttons. Re-running the scan duplicates every item (id 0 at insert).

## 3. Palettes and painting
- One controller (0x1C bytes, ctor 0x447D6D) at toolkit controller+0xD8; listener at +4, vtable 0x4829EC, DoMessage
  0x446C2A. The four palette windows (0xA429FBBA blocks, ..BB paints, ..BC details, ..BD props) are created by
  0x4422AD -> 0x442160 -> 0x44589C; each 0x445B24 registers for 0x9A27E1C0 and 0x63CC69B7 and pushes its tabbed
  window (vtable 0x483110) into controller+0x10; destroy 0x446BC8.
- Pages (tab ids 0x644BB2xx; jump table 0x446F43): paints B2 walls (2), B3 ground (0), B4 roofs (1), B5 colors (3),
  B6 custom (6); details B7 traditional (5), B8 contemporary (4), B9 custom (7); props BC..C3 (8..15), BA custom (16).
- A tab click: 0x44BA75 shows the page and posts {0x9A27E1C0, pageId, 0, 0} (message server vt[0x10]); 0x446C2A
  finds the owning tabbed window (vt[0x1F0] = 0x44BCBF) and builds the page only if its populated byte (entry+0x20,
  vt[0x1F4] = 0x44BD09) is clear - except B6, B9, BA, which are always cleared (page vt[0x1F0] = 0x44A7CB), reset
  (vt[0x1F8] = 0x44BD55) and rebuilt. Build: 0x419A77(L, cat) (for-each 0x419697; cats >= 8 also 0x41974F); detail
  cats also 0x419D0A(L, cat) (re-parse .plt files from L+0x00) and 0x44716D(page, L, cat) (lays out .plt sets, marks
  items +0x14 |= 8); then 0x446F8B(page, L, cat): names via 0x4186C3, sorted unless cat 3, skips flag-8 items,
  thumbnail 0x4180A2 (needs +0 or +4), button id = item+0x10. Stock tabs are cached; custom tabs rebuilt every show.
- Selecting: button -> 0x445988 posts {0x63CC69A8, id} and {0x63CC69A7, 0x15}; view handler 0x436735 stores the id
  in V+0x808 (paint, 0x41FFB7), +0x804 (detail, 0x41FFC4), +0x80C (prop, 0x41FFE8) without validation.
- Painting: the tools (Fill 0x43C1EA, Decal 0x43C486) resolve the id with 0x418705 (need the id map). The model
  calls 0x40DFD8 / 0x40E042 need only an Item*: the texture table model+0x1AC is keyed by Item* (search 0x41A87E,
  allocate 0x41A918, max 255 per building). The renderer reads item+8 (0x4185BD) and SetTexture (~0x423D06); a null
  item+8 draws the face untextured. Items are never freed (AddRef/Release stub 0x41860B returns 1).

## 4. Props
- One Item per bitmap (cat 16 via 0x41926E); the custom palette shows one icon per bitmap.
- One PropRec per .met line (0x70 bytes, ctor 0x416321): +0 view0 id, +4 view0 name, +0x18 W (< 40), +0x1C D (< 40),
  +0x20 H (< 20), +0x24 / +0x38 / +0x4C names of views 1..3, +0x60 / +0x64 / +0x68 their ids, +0x6C refcount
  (release 0x40B8D7).
- Parse: wrapper 0x41885D(L, cat, BaString* met) ret 8; parser 0x419D88(L, Group*, BaString* met) ret 8 (strtok
  ",:\r\n", 7 tokens per line, names stripped of their first/last character and lowercased); each line ->
  0x41957A pushes to L+0x48, deduplicated by view0 name (old record kept). The wrapper also appends a Group to
  L+0x18[cat] (unused for props, L).
- Ids: 0x41974F(L, &view0Name) fills the ids and inserts {view0 id -> rec} into map L+0x30 (0x41B98B); run by
  0x419A77(cat >= 8) and on .bld load.
- Placing (prop tool): 0x43CA7C -> 0x40B669 -> 0x40B6BF uses 0x418705 for the items and 0x4187B5 for the record
  (map L+0x30, AddRefs): needs the record plus all four view items in the id map.

## 5. Runtime recipe (main thread)
1. Write the file completely, in Apps\BACustom\Paints|Details|Props\ (or one subfolder deep, so the next launch
   finds it too); unique lowercase name.
2. M = *(0x4954E0), L = *(M+0x1C), both non-zero.
3. Duplicate check: 0x41874A(L, &BaString("name.bmp"), &it); an item with the same cat (+0x0C) and lowercase path
   (+0x5C) is already present.
4. s = 0x14-byte BaString; 0x402C4C(s, char* fullPath) (ret 4).
5. ok = (u8) 0x41926E(L, cat, s), cat 6 / 7 / 16; destroy s with 0x450A28(s).
6. Verify: item = last of L+0x3C..L+0x40; +0x0C == cat, +0x08 != 0, id = +0x10 != 0; 0x418705(L, id, &x) gives
   x == item (otherwise an existing item has identical pixels).
7. Props: add every bitmap first, then 0x41885D(L, 16, &BaString(metPath)), then 0x419A77(L, 16); verify with
   0x4187B5(L, view0Id, &rec) (W/D/H at +0x18/+0x1C/+0x20, ids +0x60..+0x68), release 0x40B8D7(rec).
8. UI refresh (optional): post {0x9A27E1C0, 0x644BB2B6 | B9 | BA, 0, 0}. Caveat: for the custom ids 0x446C2A
   dereferences vt[0x1FC]'s result without a null check (0x446CCD): only post once the toolkit and all four palette
   windows exist (unverified edge). Custom tabs rebuild themselves whenever shown anyway.

Limits: adding the same file twice duplicates; an overwritten file gives a second item (newest wins name lookups);
re-parsing a .met never updates an existing prop's size; re-showing B9 re-appends custom .plt sets (unverified).
In-place pixel refresh (unverified): 0x4178D8(item, 0) then 0x419697(L, &item->name).
Restart alternative: exit and relaunch (init runs once per process; BACustom and first-level subfolders are loaded
eagerly).

Scratch disassembly: session scratchpad libre\ (init*.txt, scan.txt, met.txt, load.txt, pal*.txt, build.txt).
