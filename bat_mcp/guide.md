# Building Architect MCP: guide for agents

This server makes new buildings for SimCity 3000 Unlimited in two ways:
- with the game's Building Architect ("Building Architect Plus", Apps\Baapp.exe): every edit goes through the
  program's own functions; every picture is read from its render buffer or decoded from the files it writes, never
  from a screenshot (sections Start .. Best practices);
- straight from photographs, without the Architect: a model of 3D parts with walls drawn from measurements of a
  photo, rendered by the server into the game's own sprite format - higher quality (section "Photo to building").
The `guide` tool returns this text (or one section, e.g. guide(topic="photo")).

## Start

1. `bat_launch` starts the Building Architect in a 1024x768 window (or attaches to a running one).
2. `new_building(size, name, ...)` starts an empty lot, or `open_building(name)` opens a project
   (`projects` lists them; `project_image` shows each one's stored preview).
3. Build, paint, decorate (below), look at it with `view_image`, save with `save_building`.
4. `render_building()` shows exactly how SimCity 3000 will draw it; `render_building(install=true)` adds it to the
   game (see Using it in SimCity).

## Lot, cells and coordinates

- A building stands on a square lot of 1..5 city tiles a side. Each tile is 8 cells wide, so a 1x1 lot is 8 x 8
  cells (x 0..7, y 0..7) and up to 28 cells high; 2x2 16 x 16 x 64; 3x3 24 x 24 x 108; 4x4 32 x 32 x 144;
  5x5 40 x 40 x 80. One cell is one block; one block face shows a 16 x 16 pixel patch of a texture.
- z = 0 is the ground layer (one block per cell, created with the lot); the building starts at z = 1.
- The default camera looks at the lot from the +x, +y side: the top, +x and +y faces of a block face the viewer
  (the +x wall on the left of the picture, +y on the right).
- Name faces by direction in the paint tools: "top", "bottom", "+x", "-x", "+y", "-y", diagonals such as "-x+y",
  "slope" / "slope -x". (Slot numbers also work: a cube's are 0 top, 1 -x, 2 -y, 3 +x, 4 +y, 5 bottom, but other
  shapes number their faces differently and a rotation turns them; `blocks` and `shapes` list what each slot is.)
- `shapes` lists the 16 block shapes: 0 cube, 1 vertical half (diagonal), 2 wedge / ramp, 3 valley corner, 4 hip
  corner pyramid, 5 inverted wedge, 6 cube with a corner cut, 7 corner tetrahedron, 9-14 half-height slopes and
  corners, 15 prop cell (used by props). Rotation 0..3 turns a shape 90 degrees counter-clockwise; for the wedge
  (shape 2) rotation 0 is high on the +x edge.

## Building

- `fill_box(x0, y0, z0, x1, y1, z1)` fills a box with cubes (or any shape) - the usual way to make walls, floors
  and the body of a building; `place_blocks([...])` places single blocks; `remove_blocks` clears cells or a box.
- Roofs: use `roof(parts, z, pitch)`. Give one or more rectangles with a style (hip, pyramid, gable_x, gable_y,
  shed_+x..., flat) and it places the right shape in every cell - slopes, hip corners, and the valleys where two
  roofs meet (a front gable crossing a hip roof is just two parts in one call). pitch 1 = 45 degrees, 0.5 = 26.6;
  `max_height` flattens the top into a roof deck; even widths give a sharp ridge. `roof_texture` / `gable_texture`
  paint the slopes and the gable ends. (By hand: a 45-degree slope is shape 2; a half pitch uses shape 10 on the
  outer and 9 on the inner cell; hip corners are shape 4; valleys shape 3 - getting these right where roofs meet is
  error-prone, which is why the roof tool exists.) A flat roof is just a painted top layer.
- `copy_blocks(box, dx, dy, dz)` copies everything in a box (blocks, paint, details, props) by an offset - the
  quick way to add identical storeys or repeat a bay; `move=true` cuts and pastes. Target cells must be empty
  unless `overwrite=true`.
- `rotate_building(turns)` turns the whole building on its lot (the Rotate button): coordinates turn with it (one
  turn moves (x, y) to (N-1-y, x)). It decides which side faces which way in SimCity. Only to look at other sides,
  use `view_image(rotation=...)`, which leaves the building as it is.
- `blocks` reads back what is there (with each face's paint); `building_info` gives the totals.
- When saving, the Architect leaves out blocks that are completely enclosed (no face can be seen), so a reopened
  building may have fewer blocks than were placed; it looks the same.
- `undo` / `redo` use the Architect's own undo.

## Paint, details, props

- `library(kind)` lists what exists: walls, roofs, ground, colors (220 plain colours, named like
  "color 162,161,201"), details (windows, doors, signs...), props (trees, cars, benches, rooftop units...), custom
  (what the user added in Apps\BACustom). `texture_sheet(kind, search)` shows up to 40 of them in one labelled
  picture (e.g. kind="details", search="deco" for the Art Deco set); `texture_image(name)` shows one.
- `paint_box(x0..z1, walls=, roof=, wall_detail=)` paints the outside of a box in one call: uncovered side faces
  get the wall texture (and optionally a detail such as a window pattern), uncovered tops the roof texture.
- `fill_paint(x, y, z, face, texture)` is the Fill tool: the face and every connected face in the same plane with
  the same paint - one call paints a whole wall, a flat roof, or the whole lot ground (z = 0, face 0).
- `paint_faces([...])` / `detail_faces([...])` paint or decorate single faces (`"texture": ""` clears).
- `place_detail(x, y, z, face, detail)` puts a whole multi-face detail (a 48 x 48 px door covers 3 x 3 faces) with
  the given face as its top-left corner seen from outside. Textures are laid out across
  neighbouring faces the way the Architect's Paintbrush does (a 128 px wide texture spans 8 blocks), so walls look
  continuous. The ground (z = 0 top faces) can be painted with ground textures (grass, asphalt...).
- `place_props([{prop, x, y, z, orientation}])` puts props on the lot or on the building (z = the cell above a
  roof). A prop fills its size in cells, which must be empty. `placed_props` lists them, `remove_props` removes
  whole props.

## Your own textures and props

The Architect takes user-made paints, details and props from its Apps\BACustom folders; these tools write them
there and add them to the running program's library at once (no restart), so they can be used straight away and
also appear in the Architect's Custom palettes.

- `create_texture(name, kind="paint" | "detail", ...)`: a picture whose sides are multiples of 16 px (16 px = one
  block face; 32 x 32 covers 2 x 2 faces and repeats). Give it as a file (`image_path`), as base64
  (`image_base64`), or as pixel rows - one string per row, one palette character per pixel - with
  `palette` {"b": "#3a5f9a", "m": "220,220,210", ".": "transparent"} and `scale` to enlarge. Paints are opaque;
  details may have transparent parts (the paint shows through), like windows and signs. Example: a running-bond
  brick is 4 courses of `bbbbbbbmbbbbbbbm` / `bbbmbbbbbbbmbbbb` (3 rows each) with a mortar row `mmmmmmmmmmmmmmmm`
  between, scale 2.
- `prop_template(width, depth, height)` shows exactly where a prop of that size sits in its four view pictures:
  2:1 isometric, one cell 32 px wide and 16 px deep, one storey 16 px high, the middle cell at the centre; views 1
  and 3 see the footprint turned. The pictures are squares of 32, 64, 128 or 256 px - the smallest that fits, as
  the stock props use (a 1x1x1 bench 32 px, a 1x1x13 antenna 256 px; a 1 x 1 prop can be up to 15 storeys). Draw
  each view inside its box (pink or transparent = empty).
- `create_prop(name, width, depth, height, views | view_paths | view_rows)`: the four views (view 0 = the
  building's default camera, then each quarter turn) are saved as BMPs with the .met file giving the size; then
  `place_props(prop=name)`. Re-creating a prop with `overwrite=true` replaces its pictures; a changed size is
  used by place_props at once but by the Architect's own prop tool only after it restarts.

## Seeing the building (no screenshots)

- `view_image(mode)`: the Architect's live view from its render buffer. `construct` shows untextured blocks
  with the edit grid; `paint` / `detail` / `props` show the textured building (on the program's showcase lot);
  `zoom` 0..5 enlarges it; `rotation` 1..3 shows another side and `all_sides=true` all four in one picture (the
  building is turned for the picture and turned back). Pictures are cropped to the building (`crop=false` for
  the whole view).
- `render_building()`: renders the saved building with the Architect's own renderer into the sprites SimCity uses
  and returns the four rotations at the chosen zoom - exactly what the game will draw (it renders from the File
  tab, as the Render button does: construct mode would clip the building at the working plane).
- `project_image(name)`: the preview stored in a project file. `rendered_image(name)`: any building already
  rendered for the game.

- `game_building_image(name)`: any of SimCity 3000's own buildings and landmarks as the game draws it, with its lot
  size - the reference for scale and style (compare at the same zoom as `render_building`).

## Best practices

Learned from end-to-end tests: an Empire State Building (tall, 4x4) and a Queen Anne Victorian house (2x2).

### General and tall buildings (learned building the Empire State Building)

`examples/empire_state/` in the repository is a complete worked example (every step a plain MCP call; replay with
`python live/mcp_run.py bat examples/empire_state/build.py`); notes/BAT_E2E_EMPIRE_STATE.md has the full account.

1. Reference first. Read the facts (heights, setbacks, materials) and look at photographs; call
   `game_building_image` for a game building of a similar kind to see the game's scale, palette and detail.
2. Choose the lot by height. Maximum heights: 1x1 28 cells, 2x2 64, 3x3 108, 4x4 144, 5x5 only 80. Towers taller
   than 80 cells need 4x4 (the game's own landmarks can exceed what the Architect allows: its Empire State is 5x5
   and taller than 144 cells). For a tower, one cell per storey is a good scale; the stock window details assume
   about 1.5 - 2 cells per storey (low buildings).
3. Massing before paint. `fill_box` each tier (thousands of blocks take well under a second), `remove_blocks` for
   notches, recesses and light courts (cell lists), shapes for chamfers and roofs; check `view_image(all_sides=
   true)` before painting. Rebuilding from scratch is cheap: a 17,000-block tower with all its paint takes about
   20 s, so keep the build as a list of calls and replay it instead of undoing (undo keeps about 32,000 changes).
4. Paint broad to narrow: one `paint_box` over the whole building with the main wall and roof textures, then
   smaller `paint_box` calls over zones (base, ground floor, crown, mast) to override, then `place_detail` /
   `detail_faces` for doors and signs, `fill_paint` for the lot ground.
5. Design textures for the game's resolution. In the rendered game sprite a 16 px face shows at about 8 - 11 px,
   so lines 1 px wide alias into stripes: keep features 2 px or wider, vary windows slightly (blinds, lit / dark),
   and use 32 x 32 textures (2 x 2 faces) so the repeat is less obvious. The renderer lights warmly: choose colours
   a little cooler and darker than the photograph (cream limestone, blue-grey glass, dark roofs), and check with a
   quick `render_building` early.
6. Fine vertical elements (spires, antennas, statues) are props: draw them on `prop_template`'s grid and
   `create_prop` them; `radiotower1` and the balustrades (`blstrd*`) are useful stock rooftop props.
7. Judge with `render_building(zoom=5)`, which is the game's own sprite at full size; `view_image` cannot zoom in
   on a tall building as a whole. Compare with `game_building_image` at the same zoom.

### Colours through the renderer (measured)

The Architect's renderer lights each side differently. A neutral grey paint (128, 128, 128) comes out as: tops
about 0.93x (neutral); walls and slopes facing left in the default view (+x) about 1.25 - 1.3x and warm (more red,
less blue); walls facing right (+y) about 0.47x and bluish; slopes facing right about 1.07x and bluish. So a dark
grey roof turns pinkish beige on its lit slope unless it is painted darker and a little blue (e.g. 54, 58, 70), and
a pale wall glows on the lit side. `view_image` in paint mode shows the same tones as `render_building` (measured:
identical pixel values), so either can be used to judge colours; construct mode is untextured.

### Houses and other small buildings (learned building a Queen Anne Victorian)

`examples/victorian/` replays a 2x2 Queen Anne house (notes/BAT_E2E_VICTORIAN.md):

1. Scale for homes: about 2 cells per storey (the stock traditional windows, e.g. "silver spoons 15", are 1 x 2
   faces = one storey; Maxis' sample house The Joneses uses about 1.5). A large house or mansion fits 2x2 (16 x 16
   cells) with a yard; the game's 2x2 mansion Bayberry Manor has the same storey size.
2. Browse sets with `texture_sheet`: "silver spoons" is a ready Victorian kit (windows, arched double door,
   cornice bands, diagonal rake trim for gable edges).
3. At game size (a 2x2 lot is 256 px wide at zoom 5) fine trim disappears; the silhouette (turrets, gables, porch,
   chimney) and strong contrast (light trim on a darker body, as the game's own houses use) carry the style.
4. Round towers: an octagon of blocks (shape 1 half-cubes at the corners) under a custom cone prop drawn on
   `prop_template`'s grid (a 3x3x5 cone is a 128 px prop).
5. Build in an order that keeps paint where it belongs: walls and their paint, then `roof` (with its textures),
   then anything that rises through the roof (towers, chimneys), then details and props.
6. Paint and detail calls are all or nothing: if any cell or face does not exist, nothing changes and the error
   lists every problem - fix the list and call again.
7. Choose the front's side knowingly: the game never turns a building toward its street, every copy is drawn the
   same way. The game's own houses show their fronts on +x (lower-left, lit, in the default view); +y (lower-right)
   is the other side visible by default. (Photo to building, best practice 11.)

## Photo to building (without the Building Architect)

A second way to make buildings, for higher quality: describe the building as simple 3D parts in metres, draw its
walls as authored facades (windows, doors, bands, friezes, railings, ornaments at positions measured from a
photograph), and let the server render the game's sprites itself - true round towers and cones, real roof planes,
anti-aliasing, soft shadows, lighting matched to the game's own buildings, and full-resolution zoom-5 images (the
Architect stores zoom 4 and lets the game double it; verified: the game shows these images unscaled). The Building
Architect is not needed. `examples/photo_queen_anne/authored.py` is a complete example (the Haas-Lilienthal House,
San Francisco); notes/PHOTO_TO_BUILDING.md tells how its three versions were made and judged.

### Workflow

1. `photo_add(name, image_path, crop, scale)` - a front photo (more photos for other sides if you have them).
2. `photo_view(name, x0, y0, x1, y1, grid)` - read pixel positions off the grid: corners, eaves, ridge and gable
   apex, tower edges, storey lines, every window and door. Turn them into metres (best practices 3 - 5).
3. Write the model as a script that prints JSON (as authored.py does: constants for the main lines, small helper
   functions for repeated windows): {"name", "lot", "materials": {...}, "parts": [...]}.
4. `photo_model_render(model, rotation=-1)` - all four sides exactly as the game will draw them. Enlarge the
   picture 3 - 4x with nearest-neighbour scaling to judge pixels, and put it beside the photo. Iterate.
5. `photo_model_export(model, install=true)` writes the game's sprite file into Apps\BARender (our own
   "MCP Photo Buildings.DAT"; BAT.DAT is not touched; the old file is kept as a dated .bak). Installing the same
   name again replaces it. Restart SimCity 3000 (it reads the folder at start), then use the game server's
   `replace_building(<a default building of the same lot size>, <your building's name>)`.
6. Check it in the game at the closest zoom, in all four rotations, among its neighbours (game server:
   `center_view(x, y, zoom=4)`, `set_view(rotation)`, `screenshot`; `take_snapshot` works even when the display
   is asleep). `query` on its tile shows its name.
7. `photo_buildings` lists what is installed; `photo_building_remove(name)` takes a test building or an old
   version out again (first undo replace_building in any city that shows it).

### Parts and materials

Parts (all lengths in metres; a lot tile is 16 m; z up; the default view shows +x on the left, +y on the right):
box (walls; "faces" {"+x": material, ...} per side), extrude (any footprint polygon; faces named by edge index),
prism / cylinder (sides 0 = round), cone / pyramid, roof (hip, gable_x, gable_y, pyramid, shed, flat; pitch,
overhang, "gable" material for the gable ends, "bargeboard", "finial", "ends", "ridge_cap"), beam (a box between two
points: brackets, rails, posts), panel (one vertical sheet seen from both sides: fences, open balustrades, porch
fascias), ground, patch (paths), prop (any stock Architect prop: trees, shrubs...). Overlapping parts are fine: the
renderer uses a z-buffer, so a cross gable simply pierces the main roof. photomodel.py's header documents every
key.

Materials: {"facade": {"size_m": [face width, face height], "palette": {...}, "base": {...}, "elements": [...]}}
(authored walls - recommended; elements window, door, band, rect, arch, field, railing, ornament, repeat; u =
metres from the face's left seen from outside, v = metres down from its top; the colour "clear" cuts the face away
there; on a round prism u runs from its "angle", so "angle": -180 puts the +x side at half the circumference;
facade.py's header documents every option), {"color"}, {"pattern": clapboard | clapboard_window | wall_window |
shingle | fishscale | brick | stone | roof_shingle | slate | paving, "color", "color2", "size_m"}, {"texture": a
library name}, {"photo", "quad": four corners TL, TR, BR, BL, "fit": true} for flat faces, and {"photo",
"cylinder": {"left": [[x, y_top], [x, y_bottom]], "right": [...], "span_deg": 160}} for ROUND faces; options
"brightness", "tint", "remove_color" + "tolerance".

### Best practices

Learned on the Haas-Lilienthal House over three versions (photo-pasted, authored, authored with corrected massing
and detail); each point was a visible mistake first, most of them pointed out by a person looking at the game.

The approach
1. Use the photo as the REFERENCE, not as the paint. Pasted photo pixels come out rough at game size: blurred,
   noisy, lit by the photo's own sun and lit again by the renderer, with sky and neighbours at the edges. Measure
   everything from the photo and draw each wall as a {"facade": ...} material in clean flat colours. (The verdict
   on the pasted version: "still looking rough - use them as reference to RECREATE it in actual pixels".)
2. Massing first, details second. At game size the silhouette and the proportions are what make a building
   recognisable. The second version had every window right but a front 30 % too wide, and read as a generic box;
   making it narrow, deep and tall did more for the likeness than any detail.

Measuring
3. One scale per photo: in a photo taken with the camera level (verticals stay vertical; otherwise straighten it
   first with photo_rectify) everything in the facade's plane has the same pixels per metre. Find it from known
   sizes - a door leaf 0.9 - 1.0 m (a double door 1.8 - 2 m), a car 4.5 - 4.9 m, a storey 3 m in a modern house
   and 3.5 - 4.5 m in an old one - and check two of them against each other. Pick one origin (a corner, a tower
   axis) and convert every position: u = u0 + (px - px0) / scale.
4. Parts nearer the camera than the facade (a projecting tower, the porch, a car) look larger; parts behind it
   smaller. A photo from street level hides roofs and squashes cones: a turret roof seen from below shows about
   half its real height, so reason with the depth or use typical pitches (Queen Anne turret cones 55 - 60 degrees,
   gables 45 - 50).
5. Colours: sample the photo in sun and in shade (photo_view, or the image itself) and decide which is lighter,
   the body or the trim - in the Haas-Lilienthal House the trim (frames, bands, columns, bargeboards) is lighter
   than the body, and the version with dark trim did not look like it. Keep strong contrast between body, trim and
   recesses, as the game's own houses do.

What reads at game size (8 px per metre at the closest zoom; a 2x2 lot is 256 px wide)
6. Volumes beat paint. Make every projection a part with its own facade: bays (box or extrude), a balcony slab,
   a gable that stands out over the storey below, the porch, chimneys, dormers. Shading and shadows then show them.
7. Light lines draw the shape: bargeboards along gable rakes, finials, ridge caps on every roof, floor ledges and
   a cornice as thin boxes slightly larger than the body, rings on towers, porch columns.
8. Open things should be see-through: a porch with arches, a balustrade, an iron fence. Use a panel part with a
   facade whose base is {"color": "clear"} (or an "arch" element in "clear"); the renderer cuts those pixels away,
   so lawn and walls show through as in the real thing.
9. No long plain walls. A 17 m side wall with a regular grid of windows reads as an office block in the game:
   break it with a cross gable, a slanted bay, a chimney, varied windows.
10. Round towers: windows on a round prism go at angles from the street (u = half the circumference + r * angle);
    a turret that overhangs a narrower bay is two prisms of different radius; a wall dormer is a small box with its
    own gable roof standing through the cone's eave.

Orientation and the city
11. SimCity 3000 does not turn buildings toward their street. Every copy of a building
    is drawn the same way in a given view, whatever side its road is on - tested with a box with four coloured
    walls on four lots with roads on four different sides: identical; the game's own row houses also keep their
    stoops on one side. So put the street front on +x (lower-left and lit in the default view, where the game's
    own houses show theirs) and a secondary front on +y. Where the replaced default building's lots happen to have
    the road behind, the house faces away from it; nothing in the building can change that.
12. A quick way to answer any "which side is which" question in the game: export a box whose four walls have four
    colours, replace a building with it, screenshot, then photo_building_remove it.

Photo materials (only when likeness matters more than finish: flat, evenly lit, sharp photos)
13. Round surfaces need the cylinder unwrap: use a "cylinder" material and the round prism's "photo": {"mat",
    "toward_deg"} so the photo sits on the side it was taken from (0 = the photo looks at the tower from +x); never
    repeat a photo around the back - give the rest a pattern in the photo's colour.
14. Cones and other small busy surfaces: a pattern in the measured colour, not a tiled photo patch (it stripes).
15. Photos carry their own light: use "brightness" (0.7 - 1.3) and a slight "tint" to bring photo parts and
    patterns to one colour; "remove_color" fills sky showing at the edges of a region; match a gable's pitch to the
    photo or the photo's sky shows in the triangle.

## Saving and using it in SimCity

- `save_building(name)` writes Buildings\<name>.bld (the game's own sample projects cannot be overwritten).
  `render_building` needs the building saved (it renders from the file).
- `render_building(install=true)` adds the building to Apps\BARender\BAT.DAT, keeping all other user-made buildings
  (the previous file is backed up next to it). SimCity 3000 must not be running while this happens (it keeps the
  file open). In the game, user-made buildings replace look-alike default buildings: use the game server's
  `building_replacements` / `replace_building` to show the new building in a city.

## Errors

A failed call is an MCP tool error whose text is JSON {"error": ..., "hint": ...}. Placing outside the lot, painting
a cell without a block, or an unknown texture / prop name is refused with a message saying why.
