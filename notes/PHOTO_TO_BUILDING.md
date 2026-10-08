# Photo to building, without the Building Architect (2026-10-08)

Request (user): turn a photo (or several) into a decent-quality SimCity 3000 building directly, without the
Architect, with guidance through the MCP on best practices; Queen Anne as the example; ideally a higher-quality
option than the Architect's blocks.

## Pipeline (bat_mcp, no Baapp needed)

1. `photo_add` / `photo_view` (grid in the photo's pixels) / `photo_rectify` (homography: four corners -> flat).
2. A model in metres (photomodel.py): parts box / extrude / prism-cylinder / cone-pyramid / roof (hip, gable,
   pyramid, shed, flat; pitch, overhang) / ground / patch / prop (stock Architect props as billboards drawn from their
   own four views); materials colour / pattern / Architect texture / photo quad / photo cylinder unwrap.
3. render3d.py: numpy software renderer - z-buffer triangles, orthographic texture mapping, smooth normals on
   cylinders and cones, a shadow map with 3x3 PCF, 4x4 supersampling, box-filtered to the five zooms.
4. datwriter.py: the game's sprite database: RefPack compressor, RGB565 row-span images with the 0xF81F key,
   anchors, the "BIN\r" sprite family (20 frames), the 0x856CD19A building record; IXF writer; install into our own
   Apps\BARender\MCP Photo Buildings.DAT (backup first).

## Verified

- Format: every one of the 240 images in the Architect's BAT.DAT decodes and re-encodes to identical pixels, anchors
  and unpacked bytes (the Architect writes left = width for empty rows); our RefPack output is ~6 % smaller.
- Projection and light: a grey test house built in both the Architect and the renderer: same sprite sizes and
  silhouettes within a pixel in all four rotations, colours within ~7 levels. The Architect's lights are fixed to the
  building (compass directions turning with the model), not to the camera. BATConfig.ini documents both the
  Architect's Preview lights and Maxis' six-light 3DS rig.
- In the game: the file is loaded at start-up (the game reads every *.DAT in Apps\BARender) - the building appears in
  the user-made list; replace_building("Ike's House", ...) in Madison, WI; the game's Query on that tile shows
  "MCP Haas-Lilienthal House"; screenshots and Photo Album snapshots show it in all four rotations.
- Native zoom 5: frames 16-19 with scale 0 pointing at 128 px-per-tile images are drawn unscaled - in a screenshot at
  the closest zoom 14 % of the building's 2x2 pixel blocks are uniform against 96 % for a neighbouring Maxis house
  (zoom 4 doubled). Photo-built buildings are sharper at the closest zoom than Architect or stock buildings.
- live/p1_photo.py: all photo tools over MCP with a synthetic photo (perspective facade, striped tower), export read
  back (20 frames, native zoom 5, widths 8..128 px per tile), encoder vs BAT.DAT.

## The Queen Anne example (Haas-Lilienthal House)

Photo: "Haas-Lilienthal House exterior 2025.jpg", Ppienovagem, Wikimedia Commons, CC BY 4.0 (viewed in the browser;
the test used browser captures at half resolution = crop [820, 280, 2396, 2990] scale 0.5 of the original).
Model: 2x2 lot, front on +x; raised basement, three 4 m storeys (16 x 13 m), hip roof crossed by a 47-degree front
gable (photo gable end), porch with columns and a photo pediment, steps, garden wall, props; the corner tower is a
1.75 m rounded bay (two storeys) under a 2.2 m turret band, both unrolled from the photo on the street side, clapboard
/ fish-scale behind; eave ring, a blunt shingle cone (4.2 m on a 5 m base), a turned finial (collar, bell, two knobs,
spike) and a gabled dormer. 2.6 s to export; 144 KB.

## Mistakes made on the way (now in the guide as best practices)

1. Side walls tiled from a photo crop of shaded windows looked like an office block -> clapboard_window pattern in
   the photo's wall colour.
2. Sky showed at the edges of photo regions around the narrow turret and gable -> remove_color (fills from the
   wall around it).
3. A gable pitch that differs from the photo's shows the photo's sky in the triangle -> match the pitch to the
   photo (height / half-width in photo pixels).
4. Architect lighting made the house look black next to the game's own houses (right walls 0.37 of the left, game
   sprites about 0.55 - 0.65) -> "game" light set (default) and "architect" for parity with Architect renders.
5. The spire (user: "looking a little funky"): cone twice too tall, finial far too thin, the cone's pink cast ->
   proportions measured on the photo, a turned finial, a pattern in the measured shingle colour (a tiled photo patch
   made radial stripes).
6. The turret (user: "still rendering as a warped image that is skewed poorly on top of it"): a flat photo strip
   wrapped around the cylinder, centred 90 degrees off the street (the front had been turned to +x), its squeezed
   edges stretched again, and repeated around the back -> the cylinder unwrap (x = centre + r sin(angle) per row,
   equal angle steps over 160 degrees), placed on the side the photo looks from, a pattern elsewhere, and the tower
   modelled as the narrower bay under the wider turret it really is.
7. A first numpy import inside an MCP tool hung the server (tools run in a worker thread) -> numpy is imported when
   the server starts.

## Limits

- One photo means one lit side: the shaded parts of the photo stay darker; other sides are patterns. More photos
  (sides, back) can be added as more materials.
- Texture resolution follows the photo: about 30 - 60 px per metre is plenty for zoom 5 (8 px per metre).
- Hand-entered geometry: proportions come from reading the photo; there is no automatic photogrammetry.
- The game reads Apps\BARender at start-up: restart it after installing (the replacement is chosen in each city).

## Version 2: authored from the photo (the recommended method)

User, on the photo-pasted turret in the game: "This is still looking rough. You may not be able to use actual
photos here, but instead use them as reference to RECREATE it in actual pixels."

New: facade.py - a wall drawn element by element (window with frame / sash / transom / hood / pediment / sill /
curtain, panelled door, band plain / dentil / molding / frieze / brackets, rect, shingle field, railing, ornament
sunburst / fan / rosette / diamond, repeat) at metre positions in a palette; material {"facade": ...} stretched over a
face (on round prisms around the circumference). examples/photo_queen_anne/authored.py measures every position from
the photo and draws: the front (loggia with spindle frieze and balustrade, transomed and hooded windows, rosette,
panelled double door, bracket cornice, dentil and molding bands), a 7.6 m 52-degree projecting front gable
(fish-scale, bracket band, sunburst, dentil), the porch pediment (fan), the rounded bay (three tiers of windows at
-60 / 0 / +60 degrees from the street), the turret (pedimented windows, carved frieze, fish-scale), side and back walls
(hooded windows in rhythm), basement windows; 3D ledges at each floor, a cornice, tower rings, a balustrade in front
of the loggia; palette body #76897a, trim #4a584f, dark slate roof #3e434f. In the game (Madison, four rotations) it is
crisp and sits with the Maxis houses; the photo-pasted version stays as model.py for comparison.

Lesson: at game size (8 px per metre at the closest zoom) a building reads through clean shapes, strong trim
contrast and consistent light - which authored facades give and pasted photos do not.

## Version 3: massing, volumes and line work (user: "Keep going!", then "This looks great")

Re-measured the photo with one scale for the facade plane (the camera is level: verticals stay vertical): about
58 px per metre from the double door (115 px) and the parked car (4.8 m = 415 px, a few metres nearer). Origin = the
tower axis (photo x 130); porch floor at photo y 990 = z 2.

Changes and why:
- Massing: the front is about 10.5 m, not 13 m; the body became narrow and deep (10.5 x 17.5 m, eaves 12.4 m), the
  storeys 4.6 / 3.6 / 2.2 m (the third floor sits under the gable), the main hip roof 40 degrees. This did more for
  the likeness than any detail.
- Palette: photo samples in shade show the trim LIGHTER than the body (body #374342, frames and columns #9daba3 -
  #a0aca4, recesses #262c2a); version 2 had dark trim. Trim #a6b2a3, bargeboards #b3bdaf.
- Volumes: the second-floor bay (0.7 m proud, garland frieze, sunburst panels), a balcony slab running over it, the
  third floor under the gable 0.5 m proud with the loggia arch, the 5.8 m 47-degree gable over it; a 6.1 m porch
  with a 32-degree pediment, four columns on plinths, open arches (see-through fascia panels) and balustrades;
  steps on the door's axis; a wall dormer on the turret; slanted two-storey bays on both sides and a cross gable on
  the garden side (a 17.5 m plain side wall read as an office block).
- Line work: bargeboards along every gable's rakes, finials at the apexes, ridge and hip caps on every roof.
- Garden: a stone wall with a see-through iron fence; shrubs; trees moved off the visible sides.

New in the server for it: roof "bargeboard" / "finial" / "ends" / "ridge_cap"; parts "beam" and "panel"; facade
colour "clear" (cut-out), element "arch", railing "style": "iron" and "back", band "u" / "w"; tools photo_buildings
and photo_building_remove; BAT_MCP_TRACE=1 adds a traceback to error results.

Bugs found on the way: a gable end triangle rose overhang x tan(pitch) above the ridge (now it meets the ridge;
live/p1 checks it); a texture lookup could index one past the edge when a float modulo rounded up to the width
(the first render in a fresh server failed on one model; now wrapped again).

## Do buildings face their street? (tested in the game)

User: "I noticed the house does not face a street, which should be automatic, yes?" - In Madison the replaced Ike's
House lot has its road behind the house. Test: a box with four coloured walls (+x red, +y blue, -x green, -y yellow)
replaced the most common 2x2 house (Pinky's Plaza, 52 copies); four copies with their only road on x-, x+, y- and
y+ all showed the same frame at view rotation 0 (red lower-left, blue lower-right), and the game's own row houses
nearby keep their stoops on the same side whatever their road. SimCity 3000 does not turn buildings toward their
street: every copy of a building is drawn the same way. The game's houses show their fronts on +x (lower-left in
the default view), as this model does. Then the test building was taken out again (photo_building_remove).
