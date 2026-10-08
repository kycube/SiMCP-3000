# BAT render: rendered sprites, render pipeline, preview surfaces, .bld thumbnails (static RE by subagent; saved by main)

Static only. Preferred VAs (Baapp.exe 0x400000, SIMBABLD 0x12000000, others 0x10000000). Scripts in this folder:
batdat.py (every image in BAT.DAT -> PNG; --dat PATH for any DAT), bld.py (.bld header + 200x200 thumbnail -> PNG),
gzsurf.py (GZ/DirectDraw surface memory dump -> PNG), fmatch.py (Baapp.exe twin of a SIMBABLD function - both contain
the same BAT code), check.py (25 static facts, all pass). Output went to the scratchpad (batpng, bld2); defaults
%TEMP%\sc3k-batrender and %TEMP%\sc3k-bld. Nothing written to the game folder.

## 1. Rendered output in BAT.DAT (CONFIRMED; decoder verified on all 15 buildings)
`python batdat.py [OUT] [--dat PATH] [--sheet] [--no-x2]` -> OUT\NN_<name>\z<zoom>_r<rot>.png (RGBA, transparent),
optional sheet.png (zoom 4, four rotations), index.json (keys, size, name, architect, w/h, anchor per frame); ~3 s for
300 PNGs.
Container: IXF, magic D7 81 C3 80, index entries {group, instance, type, off, size} ending at all-zero; type 0xFFFFFFFF
= free slot. Every user building uses group 0xBA1DBF1E:
- type 0x856CD19A building record: u8 lot size, sprite-family key {0x6300, grp, inst}, 4 strings, u32; its instance =
  the .bld header id.
- type 0x6300 "BIN\r" sprite family: char[4] "BIN\r", u32 version 1, u32 SprInstCLSID 0x7300, u8 ZoomCount 5, RotCount
  4, ZoomSetCount 4, AnimSetCount 20, AnimFrames 1, RegRects 0, u32 LayerFlags 0, u16 Frames 20, then 20 frames
  {u16 idx, u32 grp, u32 inst, s8 scale, s16 dx, s16 dy} (15 bytes; dx = dy = 0). Readers SIMSPR 0x10001C90 (binary),
  0x10001909 (text twin; field names at 0x100713E0..0x100714A0). Frame index = zoom*4 + rot. Frames 16-19 (zoom 5)
  point at the zoom-4 images with scale 2 (SIMSPR 0x10001272 / 0x10001494 / 0x100014E7 scale anchor and rect;
  negative divides): zoom 5 = zoom 4 magnified 2x (pixel doubling LIKELY).
- type 0 image: u32 0x107, u32 0x00080000, u32 w, u32 h, u32 packed size, RefPack (10 FB). Unpacked: u32 size, u16 w,
  u16 h, u16 4, u16 7, u32 key 0xF81F, h row entries {u32 first pixel, u16 left x, u16 count | 0x8000}, RGB565 pixels.
  Format id 7 = RGB565 (GZGraphicD id table 0x10019669: 5 555, 6 655, 7 565, 8 556, 0xE 32-bit). Transparent = outside
  the row span or pixel 0xF81F; bit 0x8000 = row has no key pixel (19,744/19,744). No palette, no alpha, no night.
- type 1 (same instance as the image) anchor: 4 x s16 {0, h - w/4, w, w/4}; (x, y) = left corner of the lot diamond,
  the hot spot (stored at image+0x10; SIMSPR 0x10001454 / 0x10001494). SIMBABLD writer 0x1201D19B..0x1201D2D6: y =
  floor(D * scale), 4th field h - y.
Sizes: pixels per tile width z1 8, z2 16, z3 32, z4 64, z5 128 (z4 doubled); width = lot size x that (some rotations
cropped by 1-2 px); heights per building (The Joneses 1x1: z1 8x6, z4 64x42-50; 2x2: z4 126-128 x 78-258;
Headquarters 3x3 z4 192x305-309; Longview Park 4x4 z4 256x130-147). 15 buildings x 16 stored images = 240 (300 PNGs with
zoom 5). Clean 2:1 isometric renders of the building on its lot, lit with BATConfig "Preview" lights, one per 90-degree
turn. r0..r3 = LIKELY the game's view rotation (direction: live check).

## 3. The Architect's preview pixels in memory (Baapp)
Chain (CONFIRMED by code, LIKELY at runtime): M = *(Baapp 0x4954E0) (getter call(0x4010C9); class 0xF9F699CE, vtable
0x480C78); X = *(M+0x2C) (M vt[0x1C] 0x405369; the main frame adds X as a child at 0x411A71); V = *(X+0xA4) (M vt[0x24]
0x4053E2) = the 3D building view (0x2258 bytes, vtable 0x4817FC, ctor 0x41E852): V+0x674 current model, V+0x678
offscreen view surface (3D render + grids/overlays, sized to the view rect V+0x67C), V+0x690 R3D (Direct3D wrapper,
0x318 bytes, ctor 0x42631B). R3D SetRenderTarget 0x42622A: surface at R3D+0x2A0 (= *(V+0x678)), rect +0x284, float w/h
+0x2A8/+0x2AC, then 0x423122 builds R3D+0x2B8 IDirectDraw4, +0x2C0 IDirect3D3, +0x2C4 IDirect3DDevice3
(IID_IDirect3DRGBDevice = software rasterizer), +0x2C8 IDirect3DViewport3 (+0x2BC Surface4 released / zeroed).
GZ surface S (GZGraphicD DirectDraw surface class vtable 0x1001E894): width *(S+0x24), height *(S+0x28), GZ format id
*(S+0xC), bpp *(S+0x10); holder D = *(S+0x44) (vtable 0x1001F7D4): *(D+4) IDirectDrawSurface, D+0xC DDSURFACEDESC (0x6C;
after a lock D+0x60 bit count, D+0x64/68/6C R/G/B masks). Lock call(S->vt[0x1C], [0x40], S) (al != 0); pixels *(D+0xF0)
(= S vt[0x1A8]), pitch *(D+0xF4) (= vt[0x1AC]); read pitch*h; unlock call(S->vt[0x20], [0x40], S). Unlock does not clear
D+0xF0 (lock-free read possible on these system-memory targets, may tear - LIKELY). gzsurf.surface_to_png(raw, w, h,
pitch, fmt, path, key); the view surface uses the display format (read S+0xC).
File-dialog preview W (LIKELY "file mode"): 0x1A4 bytes, ctor 0x44DFFD, vtable 0x483360, init vt[0x24] 0x44DBFE, draw
vt[0x144] 0x44C808; created at 0x449060 as child 0x641CF25D, 171x171 at (17,16) on dialog init message 0xA2BF8ACE
(handler 0x448F7E; 0xA2BF8AD0 -> 0x4496F9 LIKELY selection changed); W+0xA4 model, W+0xA8 own R3D, W+0xBC 3D target
(171x684), W+0xB4 composited 171x171 preview (background W+0xB0 + scaled render). No global pointer (find by heap scan
for 0x483360 while the dialog is open - OPEN).
Render one building at a rotation offscreen: V method Baapp 0x421A62 = SIMBABLD 0x1201CF3E (rot, &surface, out): clear
to 0xFFFF00FF, render, crop (0x1201D364 / 0x1201DC55), downscale x0.5/0.25/0.125/0.0625 (0x1203C161 = Baapp 0x43DABF),
convert to 565 surfaces (0x1201D501; 555 variant 0x1201D767). Each call turns the model 90 degrees cumulatively
(0x1200E7A1(0x80)): rotations in order 0..3. Needs V vt[0x1F0] (Baapp 0x41F242) which replaces the live view's model
and render target: not on Baapp's visible view; use the DAT recipe. The in-game Replacement Manager preview (0x65902B4A,
SIMUI picture control vtable 0x100AA638, iface 0x7587239D at +0xA4 vtable 0x100AA610, vt[0x1C]/[0x20] set pictures at
+0x28/+0x2C) shows the same sprites (LIKELY).

## 2. Render pipeline and recipe
Entry (CONFIRMED): M vt[0x10] = SIMBABLD 0x12001F71 / Baapp 0x40446B -> thunk to 0x12001FAF / 0x4044A9 with flag 0;
vt[0x18] = 0x12001F8E / 0x404488 same with flag 1 and M+0x70 = 1 (skips a cache flush). Signature (cIGZString* datPath,
int nBld, cIGZString*** pBldArray, int nKeep, Key* keepKeys), ret 0x14. In the game M = *(S+0xA0). Inputs are .bld
paths; models loaded internally by vt[0x34] (0x12003ED3, (const char*, Model**)).
Steps: (1) an existing datPath is moved (MoveFileEx) to Apps\Res\BA\RenderedBuildingsBackup.IXF, a new DAT created;
(2) .bld files bucketed by lot size (vt[0x40]); init once (0x12002DEC); (3) V = vt[0x24]: V vt[0xFC] then V vt[0x24]
init; renderer R (0x30, ctor 0x12006BE1) at M+0x50 with R+8 = V; (4) per .bld 0x12002879: load model, rotate per
model+0x84, R.Prepare 0x12006A2D creates a 32-bit (format 0xE) target 128 px per tile (128x512, 256x1024, 384x1792,
512x1792, 640x1792 for lots 1..5; 0x12006B23), R.RenderRotation 0x12006A9D rot 0..3 (out +4/+8/+0xC/+0x10 = z4/z3/z2/z1
565 surfaces, +0x24/+0x34/+0x44/+0x54 rects), DAT writer vt[0x3C] writes sprites, vt[0x70] the 0x856CD19A record;
(5) kept buildings copied from the backup (0x1200461B), backup deleted, V uninit (vt[0x28]).
Needs DirectDraw (GZGraphicD) + DX6 Direct3D IM RGB software device rendering into a system-memory DDSCAPS_3DDEVICE
surface (no hardware device). Progress via posted GZ messages (0x35EE501), not a modal; byte M+0x4D = 0 skips them
(LIKELY).
Recipe (game or Baapp, UI thread, long timeout): fake cRZStrings {vtable, begin, end, end, ref=100} (vt[0x14] = c_str =
*(this+4); vtables SIMBABLD 0x120692E0 in the game, Baapp 0x480344 in Baapp): one for a non-existent temp DAT path
(e.g. %TEMP%\sc3k-mcp\r.dat), one per .bld; arr = [&bldStr], parr = &arr; call(SIMBABLD 0x12001F71 | Baapp 0x40446B,
[&datStr, 1, &parr, 0, 0], this=M); then batdat.py OUT --dat <temp DAT>. Side effects: deletes Res\BA\
RenderedBuildingsBackup.IXF only if a stale one exists. New ids: group 0xBA1DBF1E, building instance = .bld header id.
In Baapp it borrows the live view V (prefer the game process). Duration OPEN.

## 4. Thumbnails inside .bld (CONFIRMED; all 17 decode)
`python bld.py [OUT]`. Same IXF container, group 0xC3F8D4A9: header (type 0xE3F87B0F, inst 0x63FBE1CC): u8 lot size,
Pascal-string name, Pascal-string architect, u32 0, u32 building id. Thumbnail (type 0xE3F87B0E, inst 0xE3F8D655): u16
0x07F0, u16 200, u16 200, u32 (size - 6), RefPack -> 200x200 RGB565 with 0xF81F magenta background = the Architect's own
preview render (Joneses, Maxis Towers, Zweikky checked). Model (type 0xE3F87B0C) not decoded. Reader M vt[0x14]
(0x12004216 / 0x40670B); LIKELY writer vt[0x3C] (0x120043B6 / 0x4068AB), which also reads an "ergc" registry value and
XORs with the key 'ahv5jdkcosjfkeotaf' (0x12006C03) - purpose OPEN.

## Open / live
1. Rotation direction r0..r3 vs the game; zoom 1 farthest. 2. Render duration; M+0x4D = 0 honoured? 3. Temp-DAT render
in the game writes nothing under Program Files? 4. Pixel format of V+0x678; lock-free read clean? 5. Global path to W.
6. Small .bld settings records (types 0x644D7178/9, 0xB9EC8F72, 0x99F88B9E).
