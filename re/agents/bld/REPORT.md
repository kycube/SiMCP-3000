# SC3U Building Architect .bld format (static RE by subagent; saved by main)

Static, on disk only. Deliverable: re/agents/bld/bld.py (parser, writer, editor API, RefPack codec, preview renderer,
example). All 17 samples parse (52,668 blocks, 849 props); `python bld.py roundtrip` re-serialises all 17
byte-identically and rebuilds every model from its block list identically (record numbering, masks, free list);
`bld.py render` previews match the stored thumbnails (visual + silhouette IoU); `bld.py example OUT.bld` writes a new
building (copy at <scratchpad>\AgentBox.bld, 30,604 bytes; round-trips; NOT loaded in Baapp or the game yet). Other
commands: summary (JSON per file), thumbs OUTDIR (thumbnails + embedded textures as PNG).
Addresses (SIMBABLD base 0x12000000; Baapp twins): load .bld 0x12003ED3 / 0x4063C8; save 0x12003BF6 / 0x4060EB; read
model 0x1200975B / 0x413E1A; write model 0x1200A849 / 0x414F08; read info 0x1200B348 / 0x415A07; write info 0x1200B7EF /
0x415EAE; read embedded-texture metadata 0x1200ADBA / 0x415479; visible-face masks 0x12011C4A / 0x40E77A; paint texture
offsets 0x12039F42 / 0x43B8A0; insert block 0x1200F55A / 0x40C08A; compaction 0x1200D86E / 0x40A330; new building
- / 0x41DA42.

## 1. Container: IXF (CONFIRMED)
Magic D7 81 C3 80, 20-byte index entries {group, instance, type, offset, size} ended by all-zero; the index area is
always 1024 slots (data starts at 0x5004; LIKELY fixed); data contiguous in index order. In memory the GZ key order is
{type, group, instance} (SIMBABLD 0x12003F71). Every .bld resource has group 0xC3F8D4A9. Little-endian; str8 = u8 length
+ bytes; str32 = u32 length + bytes.

## 2. Resources
- E3F87B0C / A3F8D615 model (section 3; r 0x1200975B / w 0x1200A849) CONFIRMED.
- E3F87B0F / 63FBE1CC info: u8 lot (1..4); str8 name; str8 architect (samples add u32 0, u32 id - ignored by the reader,
  not written by the shipped writer; for 13 of 15 rendered samples the id = the instance in BARender\BAT.DAT).
- 644D7178 / A44D71AA description (str8). 644D7179 / A44D71AB u32 building type = BATStringsMain id (0x208
  Residential, 0x209 Commercial, 0x20A Industrial, 0x20B Police .. 0x216 Performing Arts Center, 0x217 Other).
- B9EC8F72 / 99EC9601 u32 at model+0x54 (1 in every sample; ctor default 0; missing -> value from singleton
  0x1205671C). Write 1. Meaning OPEN.
- 99F88B9E / B9F88BD2 4 bytes at model+0x50..53: byte 0 ground/visibility mode (1 legacy - 16 samples and the loader
  default; 2 current - ctor default 0x1200DFB5, Longview Park); rest 00 1C 00 in v2 (OPEN).
- DA6DC9A9 / 63FBE1CC str32 + u32 from the registry value ...\SimCity 3000 Unlimited\ergc (registration code); written by
  the shipped writer, no sample has it, the loader works without it (0x1200B748 / 0x1200BAF6).
- E3F87B0E / E3F8D655 thumbnail 200x200 RGB565, magenta F81F background (image read 0x1201BC09).
- E3F87B0D / n embedded custom-texture metadata: u8 version 0x0A; two rects 2x4 i32 (used pixel area); u32 uid; u32
  flags; 4 floats width, height, 1/w, 1/h of the power-of-two texture; str32 file name; 3 x u32 key of the pixel
  resource {E3F87B10, group, n}; u32 category (7, 6, 0x10 seen).
- E3F87B10 / n embedded texture pixels (image; normally 0xF1 / 0x0E ARGB).
- FA662D17 / n embedded custom prop MET line: u8 0x0A; 4 x str32 view bitmaps; u32 x, y, z size (loader callback
  0x120096A3, LIKELY).
Before reading the model, the reader imports every embedded texture (callback 0x12009667) and prop (0x120096A3).
Image resource (0x1201BC09): u8 kind (0xF0 16 bpp, 0xF1 32 bpp), u8 pixel format (7 RGB565, 0x0E ARGB8888 as B,G,R,A),
u16 w, u16 h; then u32 total length (incl. itself) + RefPack (standard EA QFS, header 10 FB + 3-byte size; bld.py has
an encoder with the BAT's opcode mix and a decoder).
Save order (reproduced): model; per n: E3F87B0D, E3F87B10, [FA662D17]; info, description, type, B9EC, flags,
[registration], thumbnail.

## 3. Model resource (version 8; reader accepts 4-7)
Header: u8 8 (version); u8 view_rot (model+0x84); u8 grid (= 8 * lot; clamped to 0x30); u8 lot; u8 EA (ignored); u16
height (z capacity); u16 EAEA (ignored); u32 used (= free-list head = blocks + 1; record 0 null); 5 x u32 (EAEAEAEA, 4,
32, EAEAEAEA, grid^2*4; ignored).
Body: column heads grid x grid u32 x-major head[x][y] (0 = empty); u32 EAEAEAEA; record pool: u32 n then n bytes (u32 n +
RefPack); the pool holds bound = used*32*10/9 + 1000 bytes (the saver passes its compressor's size bound as source
length - 0x12059F0F, 0x1200AA2E - so free-list records are saved too; free list i -> i+1 with z = 0x1FF; all 17 match);
u32 EAEAEAEA; texture table: u32 count, count x {str32 name, u32 uid} (index 0 unused; uid ignored; max 255); u32
EAEAEAEA.
Record (32 bytes, CONFIRMED): d0 bits 0-16 next index, 17-25 z, 26-29 shape (0..15), 30-31 rotation; d1 visible-face
bitmask (bit = face slot; renderer 0x1201F600 skips cleared; 0x100 hidden marker never in files); 6 faces x {u8 paint,
u8 paint_uv, u8 detail, u8 detail_uv} (texture-table indices; detail = decal layer; setters 0x120114A8, 0x1201151A,
0x12011584, 0x120115FA). Each column a linked list with strictly increasing z; after compaction records are numbered
x, then y, then z from 1. z = 0 ground layer (one cube per cell, landscape paint on top); buildings from z = 1.
New-building tables (Baapp 0x41DA42): grid 8/16/24/32/40, height 28/64/108/144/80 for lot 1..5 (samples also have
heights 65/109/257/288/385).
Visibility masks (0x12011C4A): a face on a cell side is hidden when the neighbour's face on the shared plane covers its
corner set; props and non-props never hide each other; two prop cells only if the same prop; in v2 the non-top faces of
z = 0 cubes facing out of the lot are hidden. compute_masks() reproduces 100% of masks in 8 samples (incl. Longview v2
and every prop cell); other differences = v1 ground artefacts and stale bits (harmless).

## 4. Geometry, shapes, coordinates (CONFIRMED)
Cell vertices (neighbour tables 0x120795E0 / 0x12077A8C; renders match thumbnails): 0 (1,1,0), 1 (0,1,0), 2 (0,0,0),
3 (1,0,0); 4-7 above at z = 1; 8-11 at z = 0.5. Rotation r renames vertex v -> (v & ~3) | ((v + r) & 3) (table
0x12078258) = 90 degrees counter-clockwise per step (x right, y up). Cube face slots at r = 0: 0 top, 1 -x, 2 -y, 3 +x,
4 +y, 5 bottom. Camera: BAT view 0 looks from the +x,+y side (screen x ~ y - x); visible cube faces top, +x, +y. Shape
table 0x12078750 (16 x 0x78: faces {code, 4 vertices, 4 uv corners}; per-rotation back-to-front draw lists at +0x48;
embedded in bld.py as SHAPES).
Shapes (geometry CONFIRMED, names LIKELY): 0 cube [6 faces]; 1 half-cube prism, vertical diagonal [5]; 2 wedge / ramp,
full height at +x down to 0 at -x [5]; 3 valley corner [7]; 4 hip-corner pyramid [5]; 5 inverted wedge [5]; 6 cube with
one top corner sliced off [7]; 7 corner tetrahedron [4]; 8 floor plate (legacy ground) [1]; 9 ramp full to half height;
10 half-height ramp; 11-13 half-height corners [7]; 14 half-height pyramid; 15 prop cell. Samples use only 0-7, 9, 10,
15; every cube and prop cell has rot == view_rot.
view_rot: rotating the view in the BAT rotates the DATA: (x, y) -> (g - 1 - y, x), rot += 1; the thumbnail shows the
canonical orientation (data turned back by -view_rot; best IoU at k = -a for all 17). New files: view_rot 0.
rotate_blocks() provided.

## 5. Paints, details, props
Texture names are file names, lowercased by the loader (0x12009AE7) and the registry (0x12014555). Lookup:
Res\BA\{Paints\Walls, Roofs, Ground, Details, Props}, BACustom\{Paints, Details, Props}, embedded textures; unresolved
-> untextured. 220 built-in solid colours = textures named `color R,G,B` (table 0x12069504, created at 0x1200301B; only
those exact names): bld.py COLOR_PAINTS / color_paint(r, g, b).
uv byte = (u << 4) | v: which 16x16 cell of the texture this face shows (packing 0x1203A2F9). Side faces: u increases to
the viewer's right; v counts rows downward (one z level up = v - 1). Top faces at view 0: u = (y0 - y - 1), v = (x0 - x)
(0x1203A29C). Verified on sample data; the sampler wraps modulo the texture size (Maxis stored u = 15 on a 128-px
texture - LIKELY). Details use the same encoding in bytes 2 and 3.
Props (rule from data): each placed prop fills its x * y * z volume from the MET line with shape-15 cells (clipped to
the lot); face slots 1..4 hold the 4 bitmaps of the chosen MET line (line index = orientation); bytes 1 and 3 hold
signed sprite offsets of the cell relative to the reference cell (cx, cy, z0 + (sz - 1) // 2): slot 1 u = dy - dx,
v = dx + dy - 2dz; slots 2-4 the same with the delta turned 90/180/270 degrees CCW, the delta first un-rotated by the
cell's rot; the renderer draws the sprite from slot rot + 1 (0x1201F8CC). place_prop() rebuilds all 48 prop cells of
The Joneses byte-exactly; props() groups cells into placed props and matched all but 3 of 849 sample props to a MET
line (recovering orientation).

## 6. Minimal valid file / example (NOT TESTED in the BAT or the game)
Required: IXF with model + info (the loader's result is the model-read result; info defaults if missing). Recommended:
description, type, B9EC = 1, flags 02 00 1C 00, thumbnail. Example (bld.example()):
    b = bld.Building.new("Agent Box", "sc3k-mcp", lot=1, building_type=0x208)   # 8x8, height 28, grass ground
    m = b.model; bi, ri = m.texture_index("brick 04.tga"), m.texture_index("flatr 01.tga")
    for x in 2..5, y in 2..5, z in (1, 2): k = b.add_block(x, y, z); side faces get Face(bi, bld.wall_uv(...));
        z == 2 top gets Face(ri, bld.top_uv(x, y, (128, 128)))
    b.finalize()   # masks, compact pool + free list, RefPack, 200x200 thumbnail, BAT resource order
    b.save("Agent Box.bld")
place_prop(b, bld.read_met_files()['sm decid1'][0], cx, cy) adds a tree.

## OPEN
B9EC8F72 and flags bytes 1-3; texture-metadata category / uid / flags; uv corner ids 5/6 (both (1, 0.5)?); the
"%08lx |name" texture-name form (0x12009A5C; LIKELY uid-prefixed); which lot side the game treats as the street front
(Maxis buildings face +x in canonical view 0); whether Baapp and the game's renderer accept generated files (next step:
load the example in Baapp).
(Later answers: the generated files load and render in Baapp (notes/BAT_PHASE0.md). Tested in the game 2026-10-08: SimCity 3000 does not turn buildings toward their street - every copy is
drawn the same way; the game's houses show their fronts on +x in view 0. See notes/PHOTO_TO_BUILDING.md.)
