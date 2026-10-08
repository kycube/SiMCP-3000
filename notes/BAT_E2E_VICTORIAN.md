# End-to-end test 2: a Queen Anne Victorian house with the buildingarchitect MCP (2026-10-08)

Request (user): build a building that fits within the Architect's lot limits - a Victorian-style home - from a
reference image, and use it for lessons learned. Same process as the Empire State test
(notes/BAT_E2E_EMPIRE_STATE.md): public references first, every step an MCP call (`live/mcp_run.py`), the game's
own buildings looked at only after the build. Replay: `python live/mcp_run.py bat examples/victorian/build.py`.

## 1. Reference

- Wikipedia "Queen Anne style architecture in the United States" (features: asymmetrical facade, dominant front
  gable, round / polygonal towers, porches, bay windows, patterned shingles such as fish scales, 2-4 storeys).
- Wikipedia "Haas-Lilienthal House" (San Francisco, 1886, Queen Anne - Eastlake, architect Peter Schmidt) and its
  photograph "Haas-Lilienthal House exterior 2025.jpg" by Ppienovagem (Wikimedia Commons, CC BY 4.0, 2992 x 2992),
  viewed at full size: round corner turret with a conical shingle roof, dormer and finial; front gable with
  fish-scale shingles over a recessed 3rd-floor loggia with a balustrade; two-storey angled bay; pedimented entry
  porch on columns with double doors; raised grey basement; sage-green clapboard, darker trim, cornice brackets.
- Scale check without looking at any possibly-Victorian game building: the Architect's sample "The Joneses" (1x1,
  two storeys in about 3 cells) - about 1.5 - 2 cells per storey.

## 2. Build

- Lot 2x2 (16 x 16 cells, max 64 high), 2 cells per storey: z 1 basement, storeys z 2-3, 4-5, 6-7, roof from z 8;
  body 10 x 9 cells, front on +y (right side of the default view), turret on the front-left corner from the street.
- `texture_sheet` found a Victorian detail kit in the stock "silver spoons" set (1 x 2 windows, 2 x 2 arched double
  door, cornice band, diagonal rake trim); stock siding 08 was too bright, so the paints are custom
  (`create_texture` rows): clapboard (8 px boards with 2 px shadows), fish-scale shingles (U-shaped 8 px scallops),
  ashlar foundation, trim, roof shingles.
- Massing with `fill_box` / `place_blocks` / `remove_blocks`: body, octagonal turret (shape 1 half-cubes on three
  corners, the fourth inside the house), angled bay (two half-cubes and a cube), porch floor and wedge steps,
  loggia opening. Turret roof: a custom 3x3x5 prop (128 px) ray-cast as a shaded shingle cone with an eave band and
  a turned finial, on `prop_template`'s grid; it sits exactly on the octagon.
- Paint broad to narrow; 110 window faces and 37 cornice faces in two `detail_faces` calls; door with
  `place_detail`; props: loggia balustrade, porch columns, trees, shrubs, a low front wall; lawn and walkway.
- The whole build is about 1,300 blocks and runs in about 15 s.

## 3. Gaps found, and what was done

| Gap | Found when | Fix |
|---|---|---|
| Roofs had to be assembled cell by cell from wedges, hip corners and valley shapes; where the front gable met the hip roof the hand-placed shapes left holes and odd flat patches (valleys need shape 3, and which shape fits depends on all four corner heights) | first build | new `roof(parts, z, pitch)`: roof parts (hip, pyramid, gable_x / gable_y, shed, flat; 45 or 26.6 degrees; optional flat deck) combined as a height field (highest surface wins); each cell's four corner heights pick the shape and rotation from a table built from the shapes' own vertex data; the convex cut corner and the concave valley (same corner heights) are told apart by the height at the cell centre. Paints slopes and gable ends. Re-creates the cottage's hand-verified gable exactly |
| `paint_faces` / `detail_faces` stopped at the first missing cell and left the faces before it changed | a cornice list that included the loggia opening | all or nothing: the whole request is checked first (cells, face names on each block's shape, texture names) and the error lists every problem; nothing changes |
| Roof colours: a dark grey roof rendered pinkish beige on its lit slope | first render | measured the renderer with a neutral grey test house (below); the guide gives the factors; repainting the roof darker and slightly blue fixed it |

## 4. Colours through the renderer (measured, `render_building` at zoom 5)

Neutral grey paint (128, 128, 128): tops about (119, 117, 119) = 0.93x; walls / slopes facing left (+x in the
default view) about (165, 148, 140) = 1.25 - 1.3x, warm; walls facing right (+y) about (57, 58, 74) = 0.47x, bluish;
slopes facing right about (136, 136, 152) = 1.07x, bluish. `view_image` in paint mode gives identical pixel values
(construct mode is untextured), so either shows the true colours.

## 5. Comparison with the game (after the build)

No game building is a Queen Anne house ("Gingerbread House" is a garden plot, "Fancy House" an Italianate 1x1,
"Bayberry Manor" a Greek Revival 2x2 mansion). Bayberry Manor confirms the scale: a 2x2 house with the same storey
size as the build. The game's houses use saturated body colours with bright white trim / columns and neutral grey
roofs; the first build was low in contrast and its lit roof slope pink - fixed with the colour rules above.

## 6. Lessons (in bat_mcp/guide.md, "Best practices")

Colours through the renderer; ~2 cells per storey for homes; `texture_sheet` to find a matching detail set;
silhouette and contrast matter more than fine trim at game size; towers as block octagons under a cone prop; build
order walls - roof - things rising through the roof - details - props; paint calls are all or nothing.

## 7. Files

examples/victorian/ (textures.py, turret_roof.py, build.py); bat_mcp/roofs.py (the roof tool); test content left
in place: Buildings\MCP Queen Anne.bld, Buildings\MCP Colour Test.bld, BACustom paints "vic *" and "cal grey",
prop "vic turret roof".
