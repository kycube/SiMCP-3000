# UI atlas (client coords of a 1024x768 windowed game; verified with synthetic clicks unless marked ~)

Synthetic input: bridge OP_MOUSE/OP_KEY (fakes GetCursorPos/GetAsyncKeyState/GetKeyState in SC3U.exe,
GZWIND, GZGraphicD for ~600 ms). Text fields accept WM_CHAR typing; `end` + backspaces clears them.

## Main menu (menu art 800x600 centred at +112,+84)
- Start New City (357, 400) -> New City Options. Others (~): Starter Town (470, 290), Play Scenario
  (640, 255), Load City (690, 470), Preferences (440, 560), Real City Terrain (580, 560), Exit (760, 610).
- WM_CLOSE is ignored here.

## New City Options dialog
- City Name field ~(307, 260), Mayor Name ~(307, 300)
- Difficulty: Easy ~(223, 340), Medium ~(223, 364), Hard ~(223, 388)  ($50,000 / $20,000 / $10,000 loan)
- Start Date: 1900 ~(223, 412), 1950 ~(223, 436), 2000 ~(223, 460)
- City Size: Miniature ~(309, 412), Small ~(309, 436), Medium ~(309, 460), Large ~(309, 484)
- Disasters checkbox (213, 500); Auto Budget ~(213, 520); OK (797, 544)
- Right side: Landscape / Trees / Buildings style icons, "User-Made Buildings: Select".

## Terrain Edit screen
- "Accept this Terrain" (937, 590); Re-Generate Terrain ~(940, 470); sliders ~(912..976, 370..420).

## City view
- First entry: simulator paused; "Llama Suggests" tip: OK (635, 497) (leave "Show tips at startup" alone).
- Status bar y=740: city name, Pop, funds, date. Pause (722, 722), Play (750, 722), speed boxes ~(722..756, 742).
- Right toolbar x=990: Landscape 115, Zone 152, Build Transportation 190, Build Utilities 225,
  Place Civic/Special Bldgs 260, Emergency 330, (advisors/meetings ~395, data views ~435),
  Change Settings & Exit 470. Each opens a pill column at x=943.
  - Landscape: trees 135, water 168, raise 203, lower 240, level 275, bulldoze 310 (~).
  - Transportation: road 133 (verified: drag built a road, $385 for ~14 tiles), others below (~).
  - Change Settings & Exit: Preferences 240, City Options 277, Save City 315, Save As 351, Load 387,
    New City 421, Exit 457.
- Save As dialog (game's own browser, folder `Apps\..\Cities`): File Name field (700, 476), OK (717, 531),
  list of cities/folders (Scenarios, StarterTowns, Terrains, ...). Verified: wrote `Cities\mcp_test.sc3`.

## Added 2026-10-07 (round 2)
- Main menu entries (client coords, label centres): Start New City (357, 400), Load City (690, 470), Play
  Scenario (611, 243), Starter Town (447, 269), Real City Terrain (587, 543), Preferences (~440, 560), Exit (~760, 610).
- Change Settings & Exit (990,470) -> Load pill (943,387): a click loads a saved city; press-and-hold opens the
  submenu (Load Saved City / Starter Town / Real City Terrain / Scenario at x 801..927, y 371/387/403/419). The
  server uses the Load command with [kind, 0, 0] instead.
- Neighbors Map (COMM 0x630288e9): quadrants relative to the window's top-left NE (231,143), NW (133,143),
  SW (133,241), SE (231,241); Discuss Deal (341,326); one deals list box per neighbor (the selected one first).
- Terrain Edit panel (x 852..1024, y 144..624): sliders at x 908 (hills), 941 (water), 974 (trees), y 324..406;
  Pick Features preview (881,198)-(1005,260) with zoom/rotate buttons around it (camera only); tools 2x3 grid at
  (880..1007, 486..566): lower, raise, level / trees, water, bulldoze; Re-Generate (945,445); Accept (945,593).
- Scenario briefing window 474x432: mission rich text, Scenario Goals list, OK at (718,578).
