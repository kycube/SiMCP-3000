# Examples

Complete builds made with the `buildingarchitect` server. Every step is a plain MCP tool call, so any MCP client can
replay them; `live/mcp_run.py` runs a list of calls over stdio:

| Example | What | Run |
|---|---|---|
| `empire_state/` | The Empire State Building on a 4x4 lot, built with the Building Architect from public references (`build_v1.py` = the first attempt, before comparing with the game's own landmark) | `python live/mcp_run.py bat examples/empire_state/build.py` |
| `victorian/` | A Queen Anne house on a 2x2 lot with the Building Architect (roof tool, turret as a custom cone prop) | `python live/mcp_run.py bat examples/victorian/build.py` |
| `photo_queen_anne/authored.py` | The Haas-Lilienthal House (San Francisco, 1886) from one photograph, without the Architect: walls drawn as authored facades from the photo's measurements, rendered into the game's sprite format | `python examples/photo_queen_anne/authored.py`, then `photo_model_render` / `photo_model_export` with `model_path` = the printed `authored.json` |
| `photo_queen_anne/model.py`, `build.py` | The same house with photo regions pasted onto the model (the earlier method; needs the photo below) | `set PHOTO=<the photo file>` then `python live/mcp_run.py bat examples/photo_queen_anne/build.py` |

How each was made and what it taught: `notes/BAT_E2E_EMPIRE_STATE.md`, `notes/BAT_E2E_VICTORIAN.md`,
`notes/PHOTO_TO_BUILDING.md`; the best practices are in the agent guide (`bat_mcp/guide.md`, the `guide` tool).

`photo_queen_anne/v3_ingame_vs_photo.png`: the authored house in SimCity 3000 (closest zoom, enlarged 3x) beside the
reference photo.

## Credits

The Haas-Lilienthal House reference photo is
["Haas-Lilienthal House exterior 2025.jpg"](https://commons.wikimedia.org/wiki/File:Haas-Lilienthal_House_exterior_2025.jpg)
by Ppienovagem, licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). It is not included in this
repository except, resized and placed beside an in-game picture, in `photo_queen_anne/v3_ingame_vs_photo.png`.
SimCity 3000 is a trademark of Electronic Arts; the in-game picture shows the game's own art around the example
building.
