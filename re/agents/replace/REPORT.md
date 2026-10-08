# Building Replacement Manager (static RE by subagent; saved by main; SC3U GOG 2.0.949)

Preferred VAs (exe 0x400000, DLLs 0x10000000, SIMBABLD 0x12000000), thiscall, UI thread. S = *(*(SC3U 0x4FA86C)+0x108);
app = *(SC3U 0x4FA86C); X = *(app+0xDC) (SIMINIT class 0x42FBF1D7, vtable 0x1002F458): GM = *(X+0xC) occupant-group
manager (= appIface vt[0x40]; class 0xC306B854, vtable 0x1002F350), OM = *(X+0x10) occupant-prototype manager (=
appIface vt[0x44]; class 0x4306B914, vtable 0x1002FB44). re/agents/replace/check.py re-checks 28 facts (all pass). Keys
in memory are 12 bytes {type, group, instance} (IXF index entries are (group, instance, type, off, size)).

## 1. Names, sizes, filters
User-made buildings (CONFIRMED): S vt[0x80] (0x10005AE2) loads <Apps>\BARender\*.DAT (string 0x10037354) as database
segments and keeps every key of type 0x856CD19A (callback 0x10004FE2) in the vector S+0x80..+0x84 (stride 0xC);
vt[0x84] (0x10006A8F) unloads, vt[0x88] count, vt[0x8C](buf, max, &n) copies the keys. The 0x856CD19A record is a
SIMGEOM resource (factory 0x10012A59, 0x84 bytes); the pointer passed around is the IID 0x656CD1DD interface at obj+0x18
("b"). Record (reader SIMGEOM 0x10023AA7): u8 size 1..4 (1x1..4x4), sprite-family key {0x6300, 0xBA1DBF1E, inst} (the
"BIN\r" record), strings name, architect, s3, s4 (u32 length + bytes), one u32. Live b: size u8 b+4 (vt[0x2C]); name text
*(b+0xC)..*(b+0x10) (vt[0x24]); architect *(b+0x20)..*(b+0x24) (vt[0x28]); own key b-0x14 (= vt[0xC]()); sprite key b+0x44.
Static list (bat.py, the 15 keys seen live): 1x1 The Joneses; 2x2 North Shore Cannery, Proton Building, Dupont House,
Garvey Plaza, Hotel Splash, GuestHouse Building; 3x3 Kankakee Jr. High School, Maxis Towers, Northeast Nonwovens, Trash &
Burn, Headquarters, HiTech Lab, Den Burg Bruges; 4x4 Longview Park. Not rendered into BAT.DAT: Tutorial House, Zweikky
Unpainted (Buildings\*.bld projects only).
The manager's list: S vt[0x9C] (0x100053A4) lazily builds the collection S+0x98 via the resource manager *(S+8)
vt[0x14](key, 0x656CD1DD, &out); items u32 *(C+4)..*(C+8). S vt[0xA0](list, size) (0x100053BE) keeps those with
b->vt[0x2C]() == size (a 1x1 filter shows only "The Joneses", as observed). Recipe: C = call(SIMINIT 0x100053A4, [], S);
read name / architect / size / key of each b.
Replaceable defaults (CONFIRMED): the [ReplaceableBuildings] parser 0x10004E42 parses only the key into the set S+0xB0
(header *(S+0xB0), count *(S+0xB4); node +4 parent, +8 left, +0xC right (NULL leaves), key at +0x10; the text after = is
unused). 323 rows {0x207EDC0E, 0x57E, id}, 15 airport/runway rows {0x220055E1, 0x57E, id}.
Prototype per key: OM map at OM+0x1C (header *(OM+0x1C), count +0x20, node key +0x10, prototype P at +0x1C; P = IID
0xE075EF51 interface), or OM vt[0x18](key*, &P) (AddRefs - Release after); from a building occ->vt[0x80](). P (SIMGEOM
vtable 0x1002B5A8): own name text *(P+0x10)..*(P+0x14) (CONFIRMED); displayed name vt[0x3C](str) (the replacement's
name when replaced; CONFIRMED); key vt[0x14]() -> obj+4; type id *(P+8) (vt[0x50]); size in tiles *(P+0x24) (vt[0x40];
LIKELY, component 0 of property 0x66); current replacement *(P+0x120) (vt[0xA8]; b or 0; CONFIRMED).
Rows: SIMUI 0x1001C3A8 walks every prototype (OM vt[0x2C]) and keeps those with S vt[0x98](P) true (key in S+0xB0):
{P, chosen b, category} - 338 rows. Filters: strip shows P->vt[0x40]() == size and category; size radio 0x65902B57 items
0x65902B58..5C -> size 1..5 (controller+0x30; filters the user list too); category radio 0x65902B51 items 0x65902B52..56
-> category 0..4 (controller+0x2C) from SIMUI 0x1001BAD8 with type id t: 0 if GM vt[0x24](0xBB8, t), 1 if (0x1388, t),
2 if (0x1F40, t), 3 if S vt[0x94](t) (reward group from [REWARD_BUILDINGS] of Advisor-CityPlanner.INI, vector S+0xA4),
else 4 (labels residential / commercial / industrial / rewards / other LIKELY). GM vt[0x24] = 0x10002F3B.

## 2. Replacements: Replace / Revert / OK
Setters (CONFIRMED): S vt[0xA4](const Key* occKey, b or NULL) (0x10005BDE, ret 8): OM vt[0x40](occKey, b) (0x1000D150),
then the map S+0x8C (insert / overwrite node with b->vt[0xC]()'s key at node+0x1C; NULL erases); returns 1 whenever OM
exists (no check that the key is replaceable or sizes match; the map entry is stored even without a prototype).
S vt[0xA8](const Key* occKey, const Key* bldKey) (0x10005B95): resolves bldKey via the resource manager, calls vt[0xA4]
(unknown building key -> NULL -> silent revert). S vt[0xAC](const Key* occKey) (0x100062D0): OM vt[0x40](key, NULL),
erase node; returns 1 only if a node existed. S vt[0xBC]() (0x10004F9F): revert all, clear the map.
Map S+0x8C (STLport RB tree): header *(S+0x8C), count *(S+0x90); root *(hdr+4), children +8/+0xC (NULL leaves); in order
from *(hdr+8) back to hdr; node+0x10 default occupant key; node+0x1C user key {0x856CD19A, 0xBA1DBF1E, inst}.
Effect in a running city (code CONFIRMED, visual LIKELY): OM vt[0x40] finds P in OM+0x1C then 0x1000D186: city locks
(vt[0x21C], vt[0x234]); pulls every occupant with that prototype key out of the three occupant managers (city vt[0x11C],
[0x120], [0x124]; filter OM+0xC); P->vt[0xA4](b) (NULL reverts); occ->vt[0x1C](P) and re-inserts (om->vt[0x3C](occ));
releases (vt[0x238], vt[0x220]). Existing buildings of that type change sprite at once.
Manager window: Replace (0x65902B4B) / Revert (0x65902B4C) only change the UI row; OK (0x1001B38D) calls
S->vt[0xA4](P->vt[0x14](), row.b) for rows with P->vt[0xA8]() != row.b; Close/Cancel discards. The Query tool's
"Building Replacement For:" dialog also uses S vt[0x98] / vt[0xA4] (SIMUI 0x10063FBC, 0x10065DA8).
Recipes: read = walk S+0x8C. Replace: occKey {0x207EDC0E or 0x220055E1, 0x57E, id} and bldKey {0x856CD19A, 0xBA1DBF1E,
inst} in bridge memory; call(SIMINIT 0x10005B95, [&occ, &bld], S); check first that occKey is in S+0xB0 and *(P+0x24) ==
b's size byte (as the UI). Revert: call(SIMINIT 0x100062D0, [&occ], S). Clear: call(SIMINIT 0x10004F9F, [], S). No outer
lock needed.

## 3. Import Set, Clear Set, Edit List
Clear Set (0x1001B5E2, CONFIRMED): Yes/No box (text 0x41F2625:0x141), then S vt[0xBC] immediately (Cancel does not undo).
Import Set ("Import Set from Selected City", 0x140, CONFIRMED): the game's city chooser (GZCOM 0x310E8C85, Load-City
dialog), then S vt[0xB8](cIGZString* path) (0x100057F9): opens that .sc3 as a database (class 0x80C381D7) and runs
vt[0xB0](db, 0) - merges the city's replacement record into the current set (no clear), applied immediately. Recipe:
fake cRZString {SIMINIT 0x1002F230 (rebased), begin, end, end, ref=100} around a full NUL-terminated path, call(SIMINIT
0x100057F9, [&str], S) (vt[0xBC] first to replace instead of merge). repl.py reads .sc3 records statically (all
shipped cities: empty).
Edit List: "Building List Editor" (strings 0x13B..0x13F Active List, Look in, Remove, Add); LIKELY: "Look in" defaults to
<game>\Buildings\*.BLD; Apply (SIMUI 0x1002A7DC) confirms then S vt[0x90](nAdd, cIGZString** bldFiles, nRemove, Key*
removeKeys) (0x10006C35) rewrites Apps\BARender\BAT.dat via *(S+0xA0) (SIMBABLD class 0xF9F699CE, vt[0x10] ->
0x12001FAF, the in-game BAT renderer, Res\BA\RenderedBuildingsBackup.IXF), rescans (vt[0x80]), reverts replacements
whose user building disappeared. Renders 3D models and writes under Program Files: not recommended for the MCP; a
read-only list of .bld files vs rendered buildings is safe. .scs / .bst building sets are a Building Architect
(Baapp.exe) feature (BuildingSets folder; file-dialog modes 0x83172AD8, 0xC414CC57 in the BAT code linked into
SIMBABLD); the game's UI never offers .scs (LIKELY).

## 4. Saved with the city; cosmetic only
Saved per city (CONFIRMED): save SIMCITY 0x10004CCD -> S vt[0xB4](db) (0x10006328) writes record {0x99F47014,
0x79F4702D, 0}: key {0,0,0}, u32 count, count x {occKey[3], bldKey[3]}; the same save writes the scheme record
{0x0525A6B9, 0x4525A6E2, 1} = u32 buildings set, trees, landscape (resolves the styles report's "writer not found").
Load: SIMINIT 0x10009E1F, after SetScheme, S vt[0xB0](db, 1): clears the set, then vt[0xA8] per saved pair.
Cosmetic only (LIKELY, close to confirmed): kept only at P+0x120; within SIMGEOM read only by name (vt[0x3C]: replaced
buildings show the BAT name in Query), architect (vt[0xAC]), sprites (vt[0x54], vt[0x58]), get/set (vt[0xA8]/[0xA4]).
Footprint, type id and simulation fields untouched; sizes not enforced (mismatch = visual glitch only).

## Open (live)
1. Does New City clear the S+0x8C map? 2. *(P+0x24) = tile size; category labels R/C/I/Rewards/Other? 3. *(S+0xB4) ==
338 at runtime? 4. Sprite swap and Query name after vt[0xA8]. 5. Can vt[0x90] add a .scs path?

Files (re/agents/replace/): bat.py (user-made buildings from BARender), repl.py (INI list, -v prints all 338; .sc3
replacement / scheme records), check.py (28/28), strs.py, xall.py, appvt.py.
