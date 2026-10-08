# UI STATE FROM MEMORY (static RE by subagent; saved by main, 2026-10-07)

Preferred-base VAs (DLLs 0x10000000, exe 0x400000). "iface" = window+0xA4. check.py re-verifies 23 facts
against the binaries. HIGH = proven by code, LIKELY, OPEN = needs a live check.

## 1. GZWIND widgets
- Every window: id at +0x10 (getter GZWIND 0x10007E65, vtable +0xE8). HIGH.
- Buttons (RVA 0x2B190): type +0xF4 (2 text, 3 image, 4/5 toggle, 6 check box, 7 radio item); state dword +0xA8,
  bit 0 = checked/on, 0x1000 pressed, 0x2000 hover. iface vt[0x38] IsOn, vt[0x34](bool) SetOn; flag setter
  GZWIND 0x1000883A(mask, on).
- Radio groups: class RVA 0x2A5EC (COM 0xA1336CC1, iface 0xA1336CC0, 0xE8 bytes, ctor 0x1000283E); items are type-7
  child buttons; selected item id at group+0xC4; iface vt[0x30] GetSelected, vt[0x34](id) Select (0x10002F09).
- Edit fields (RVA 0x2A8CC): text buffer (cRZString layout) at +0xC4; iface vt[0x54](&str) GetText.

## 2. New City Options / City Options (SIMUI)
Dialog object = the modal window, vtable SIMUI 0x100AA8E8 (ctor 0x1005B6F4, builder 0x1005BBD5, click handler
0x1005E3A1, apply 0x1005EB40). Mode dlg+0xEC (L): 0 City Options, 1 new city, 2 starter town, 3 real terrain.
| What | Id | Read |
|---|---|---|
| Difficulty group | 0x25524844 | +0xC4: ..45 Easy, ..46 Medium, ..47 Hard |
| Start year group | 0x25524849 | +0xC4: ..4A 1900, ..4B 1950, ..4C 2000 |
| City size group | 0x2552484E | +0xC4: ..4F 64, ..50 128, ..51 192, ..52 256 |
| Disasters check box | 0x25524854 | [+0xA8] & 1 |
| Auto Budget check box | 0x25524855 | [+0xA8] & 1 |
| City name edit | 0x2552483F | rz_string(+0xC4) |
| Mayor name edit | 0x25524841 | rz_string(+0xC4) |
| OK | 0x2552483D | (user-made buildings: Select 0x2552485A, list 0x25524843) |
OK writes: +0x160 funds int64, +0x168 hard-loan byte, +0x16C difficulty 1..3, +0x170 year, +0x174 size, +0x17C
auto budget, +0x17D disasters, +0x114/+0x118/+0x11C style ids, +0x120 city name, +0x134 mayor. The creator
(0x10011CF2) accepts only EndModal result 1: EndModal(0x5301814A) = Cancel here. Accept by clicking OK or
SIMUI 0x1005E3A1(dlg, 0x2552483D). Radios: grp iface vt[0x34](id); check boxes: btn iface vt[0x34](bool).
City afterwards: +0x1F1 auto budget (get vt+0x90, set +0x94, msg 0x6569DE54); +0x1F2 disasters (get +0x98, set
+0x9C, msg 0x0373D8CE).

## 3. Terrain editor
Controller TE (vtable SIMUI 0x100AAAE0, 0x28 bytes, COM 0x72E85997): TE = *(mm+0x28), mm = *(SC3U 0x4FAA30)
(mode manager, vtable 0x100A2FC8; mm+0x26 editor active, mm+0x25 city screen, LIKELY); also *(panel+0xD8).
TE +0x0C feature (0 none, 1 lake, 2 river NW-SE, 3 river SW-NE, 4 mountain; default 2); +0x10 word coast mask
(1 NW y=0, 2 NE x=0, 4 SW x=max, 8 SE y=max; default 8); +0x12/+0x13/+0x14 hills/water/trees 0..255 (0x80).
Handler 0x1005F352: msg 0xC2EBAAA6 feature, 0xC2EBAAA5 coast mask, window msg 3 code 0xC slider ids 0x72E867AD/AE/AF.
Preview (id 0x72E867B0, vtable 0x100AAB14): +0xA8 feature, +0xAC word coast mask (mouse-down 0x100613D1 toggles by
the hover byte +0xB4). Sliders: iface vt[0x14](v) SetValue (0x10007E69) clamps and notifies the parent.
Buttons: Accept 0x72E867A1, Re-Generate 0x72E867A2, camera A3..A6, tools A7..AC (commands 0x42E76444 lower,
0x02E76439 raise, 0x22E7644E level, 0x4253EC3F trees, 0x02E763C1 water, 0xE3166801 bulldoze).
Re-Generate posts {0x02F2EE63, (trees>>1)<<16 | (water>>1)<<8 | (hills>>1), flags, 0}; flags NW 1, SW 2, SE 4,
NE 8, feature 3 0x10, 2 0x20, 1 0x40, 4 0x80. SIMDIRT 0x10005500 builds generator 0xA2705D06 (vt[0xC](W,H),
vt[0x1C](-1, hills7, water7, trees7, flags), clears flora, vt[0x28](dirt), posts 0xE35A8E29). Accept posts
{0x624A8221, 0, 0, 0}. Only Re-Generate regenerates.

## 4. Other
Picker (L): p = [modal+0xD8] - 0x1C (vtable SIMUI 0x100AB514); p+0x24 category; items vector p+0x08..; selected
index p+0x2C (set by 0x10069029); byte p+0x29 chosen; item->vt[0x30](0xBA64F91E/0xFA64F93A/0xFA64F957) key.
Data view: view = (*(SIMSPR 0x10072F24))->vt[0x74](); r = *(view+0xB8); lm = *(r+0x154): lm+0xCC mode (0 normal,
1 subways, 2 pipes, 0xA aura, 0xB crime, 0xC power, 0xD flammability, 0xE land value, 0xF pollution, 0x10 traffic,
0x11 density), lm+0xD0 flags (2 zones, 4 transport, 8 power lines, 0x10 flora, 0x20 zoned bldgs, 0x40 other).
City Layer Views Apply posts {0x635EE3C3, mode, flags, 1}.
Speed: city vt+0x208 GetSpeed = (city+0x38 & 1) ? +0x150 : +0x14C; SetSpeed +0x204 (1..4, msg 0xC2684066);
clock rates 120/10080/43200/129600/525600; paused = city+0x140 != 0; Pause +0x20C, Resume +0x210.

## Open
Preview+0xAC vs the live observation (+0x80..+0x100 unchanged); coast/feature click regeneration (static: only
Re-Generate); edit notification timing; picker item property ids; lm+0xCC per overlay; speed box order.
