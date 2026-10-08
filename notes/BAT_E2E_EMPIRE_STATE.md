# End-to-end test: the Empire State Building, built with the buildingarchitect MCP (2026-10-08)

Request (user): find an image of a famous, detailed building and recreate it with the Building Architect MCP, to find
gaps and best practices other agents can use; build it WITHOUT looking at the game's own copy first, then compare.

Everything was done the way any MCP client would do it: tool calls over stdio (`live/mcp_run.py`, a generic runner
written for this), no direct memory access. The replayable result is `examples/empire_state/`.

## 1. Reference (before building)

- Wikipedia, "Empire State Building" (Architecture, Form, Facade, Spire sections): 102 floors to 381 m, 443 m with
  the pinnacle; a five-storey base over the whole lot; a 60 ft setback above the 5th floor; further setbacks at
  floors 21, 25, 30, 72, 81 and 85; 86th-floor observatory; Indiana limestone with vertical window bays, nickel
  mullions and aluminium spandrels; a mast of four rectangular tiers, a cylinder and a cone, then the antenna.
- Photograph: Wikimedia Commons "Empire State Building (aerial view).jpg" by Sam Valadi (public domain), viewed in
  the browser at full size: notched (re-entrant) tier corners, wings with recessed centres on the lower tower,
  red-brown setback roofs, cream piers with dark window strips.
- The game's own Empire State (a landmark in Res\Sprites\0000000A_Landmarks.DAT) was NOT looked at until the build
  was finished (user's instruction).

## 2. Version 1 (photo and text only)

- `library` / `texture_image` / `shapes` to find materials: a stock "deco" detail set (Art Deco windows, piers,
  bands), limestone-coloured stone walls, `radiotower1` (1x1x13 antenna), balustrades `blstrd*`, ground textures.
- Lot 4x4 (32 x 32 cells, max 144 high), one cell = one storey: 102 floors + spire fit; long axis along y so the long
  facade is on the left in the default view, like the photograph.
- Massing: 11 tiers with `fill_box` (base, 6-20, 21-24, 25-29, shaft 30-71, 72-80, 81-84, 85, 86, mast tiers),
  notched corners and the lower tower's recessed centre with `remove_blocks`, the mast's octagonal tiers with
  diagonal half-cubes (shape 1, four rotations). 17,500 blocks; the biggest `fill_box` (6,400 blocks) took 0.6 s.
- Textures with `create_texture` (pixel rows + palette): facade (alternating wide / narrow limestone piers, window
  strips with a mullion, reddish spandrels), base, granite storefront, red-brown roof, mast; an entrance detail
  (48 x 48: gold lettering, deco transom, three doors) placed on the Fifth Avenue face.
- A custom spire prop (`create_prop`, 1 x 1 x 15 cells, 256 px views drawn on `prop_template`'s grid: the 102nd
  floor drum, balcony ring, cone, antenna with platforms) on top of the mast.
- Painted broad to narrow with `paint_box`, ground with `fill_paint`, balustrades around the 86th-floor deck,
  saved, rendered with `render_building(zoom=5)` and inspected (crops of the 512 x 1028 px sprite).
- Iterations: proportions (shaft 9 x 17 -> 11 x 15 after comparing face widths with the photo), pier / window
  balance, cooler limestone, chamfered mast, entrance, lower-tower wings.

## 3. Gaps found while building, and what was done

| Gap | Found when | Fix |
|---|---|---|
| Custom props were fixed at 128 x 128 px, so tall or tiny props were impossible | the antenna (`radiotower1` is 1x1x13 in a 256 px bitmap) | stock props use 32/64/128/256 px squares at one scale with the middle cell centred (verified on 14 stock props of every size); `prop_template` / `create_prop` now pick / accept the smallest that fits |
| Painting assumed cube faces: on other shapes the face slots are in the shape's own frame and turn with the rotation, so `paint_box` painted wrong slots and textures came out sideways (and after `rotate_building` even cubes would have been painted on the wrong sides) | the chamfered mast (shape 1) | decoded the per-slot direction codes (0-7 side direction, +8 steep slope, +32 shallow slope, 16 top, 48 bottom; rotation adds 2 per quarter turn - the same rule as the program's Fill tool 0x43BC71); `paint_box` / `fill_paint` / texture layout now use them and the program's visible-face bits; faces can be named ("top", "+x", "slope -x", ...); `blocks` / `shapes` list each slot |
| A multi-face detail needed hand-computed u / v for every face | the 3 x 3 entrance | new `place_detail` (whole decal from its top-left face, like the Apply Decal tool) |
| Browsing a detail set took one call per texture (about 50 calls for "deco") | choosing materials | new `texture_sheet` (40 labelled per picture) |
| `projects` showed nothing for projects saved but never rendered | listing projects | a never-rendered project's header has no building id; the reader now accepts that |
| A union-typed parameter (`int | str`) broke the portability rule (some clients reject anyOf) | `fill_paint(face=...)` | parameters stay single-typed; face names are strings (slot numbers as text) |
| No way to see the game's own buildings for scale / style | after the build (comparison) | new `game_building_image(name)`: the game's sprites decoded from Res\Sprites (sprite instance = occupant id << 16 | frame; names from the occupant catalog, 979 named buildings) |

Not gaps, verified: 17,000-block builds are fast; the Architect's undo log holds 32,766 changes and then simply
stops recording (edits continue) - replaying the build script is the better "undo" for big builds; `view_image`
cannot show a tall building large (zoom is limited per lot) - `render_building(zoom=5)` is the inspection view.

## 4. Comparison with the game's own Empire State (after building)

`game_building_image("Empire State Building")`: a 5x5-tile landmark, 640 x 1430 px at zoom 5 (the game stores
zooms 1-4; zoom 5 is zoom 4 doubled, as for user buildings). Version 1 is 512 x 1028 px on 4x4.

What the MCP build missed (and why):
- Scale: the game's version is on 5x5 and taller than the Architect allows anywhere (5x5 lots are capped at 80
  cells, 4x4 at 144). An Architect-made Empire State can only be a smaller 4x4 version. (Architect limit; now in
  the guide.)
- Palette: the game's is cool and dark (blue-grey glass dominant, cream piers as highlights, dark roofs); v1 came
  out pink / warm: the Architect's renderer lights warmly and v1's 1 px mullions aliased into pink stripes at game
  resolution. (Best practice: cooler colours, no 1 px features, check a render early.)
- Massing: the game's shaft has full-height recessed centre bays on every face (true of the real building); v1 had
  them only on the lower tower. The photograph showed them; I under-read it.
- Crown and base: the game's floodlit crown and dark mast; a plaza with trees and a fountain on the lot.

## 5. Version 2 (applying the lessons)

Same massing plus the recessed centre bays (330 + 4 x 70 cells removed), textures redesigned (2 px minimum, 2 x 2
face tiles with window variation, blue-grey glass, dark spandrels and roofs, a cream "floodlit" crown texture for
floors 72-86), street trees. Much closer to the game's look; the remaining difference is the scale cap and the
game's 3D-rendered shading. `examples/empire_state/build.py` replays it with 0 errors.

## 6. Best practices (also in bat_mcp/guide.md, "Best practices")

Reference first (facts, photos, `game_building_image`); choose the lot by height; massing before paint and check
all sides; keep the build as a replayable list of calls; paint broad to narrow; design textures for the game's
resolution and lighting; fine vertical elements as props on `prop_template`'s grid; judge with
`render_building(zoom=5)` next to `game_building_image` at the same zoom.

## 7. Files

- examples/empire_state/: geometry.py (tiers, chamfers, recesses), textures.py (v1), textures2.py (v2), spire.py
  (draws the spire prop), build_v1.py, build.py (v2).
- live/mcp_run.py: generic MCP stdio runner (steps as JSON or Python), used for every step of this test.
- Test content left in place: Buildings\MCP Empire State.bld; Apps\BACustom paints "esb *" / "esb2 *", detail
  "esb entrance", prop "esb spire".
