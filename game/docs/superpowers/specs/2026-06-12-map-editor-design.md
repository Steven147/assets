# Map Editor — Design

**Date:** 2026-06-12
**Status:** Draft (awaiting user review)

## Goal

Add a browser-based map editor to the existing map pipeline. The user draws a tile grid (single chars: G/S/O/R/r/L) on top of a live OpenStreetMap background and exports a standard `*_decl.json` that feeds directly into `stage1-local` → `stage2` → `stage3` → `stage4`.

The editor is purely a drawing tool. It does **not** fetch OSM data into the grid — the OSM tiles are visual reference only. The character grid is 100% user-authored.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  user: just edit [<name>] [--city X] [--rows N --cols M]│
└────────────────────┬────────────────────────────────────┘
                     ↓
        pipeline/editor/editor_server.py
        ┌────────────────────────────────────┐
        │ 1. Read tile registry (or default) │
        │ 2. Build JS resolver lookup        │
        │ 3. Inject tiles.js (path-only)     │
        │ 4. Inject meta.json                 │
        │ 5. Start http.server, open browser │
        └────────────────────────────────────┘
                     ↓
┌────────────────────────────────────────────────────────┐
│  Browser                                              │
│  ┌──────────────────────────────────────────────┐    │
│  │ Leaflet map (OSM tiles, pan, zoom)           │    │
│  │   ↑                                          │    │
│  │ Canvas overlay (grid lines + tile rendering) │    │
│  │   ↑                                          │    │
│  │ Mouse handlers (paint, drag, undo)           │    │
│  └──────────────────────────────────────────────┘    │
│  Toolbar: pens, size, undo/redo, export, city picker  │
│  Status bar: lat/lng under cursor, cell (r,c)         │
└────────────────────────────────────────────────────────┘
                     ↓ user clicks [Export]
        input/<name>_decl.json  (matches existing schema)
                     ↓
        just build <name>   (existing pipeline)
```

## Components

### `pipeline/editor/editor_server.py`

Thin Python wrapper. Responsibilities:
- Accept CLI args: optional name, city preset, rows, cols.
- Generate `meta.json` (center_lat, center_lng, span_km, rows, cols).
- Generate `lookup.js` (one big object mapping char × 4-neighbor combos → tile file path).
- Copy `editor.html` to a working dir.
- Start `http.server` on a free port.
- Open browser to `http://localhost:PORT/editor.html`.

### `pipeline/editor/editor.html`

Single HTML file with inline CSS and `<script>` tags. No build step. Uses CDN for Leaflet.

### `pipeline/editor/editor.js`

Modular JS (no bundler). Classes:
- `MapEditor` — orchestrator. Holds state, wires DOM events.
- `GridModel` — `string[][]` (rows × cols). Methods: `get`, `set`, `clear`, `fillRect`, `toDeclMap`.
- `TileResolver` — pre-loaded lookup. `resolve(grid, r, c) → tilePath`.
- `Renderer` — single `<canvas>`. `drawAll()`, `drawCell(r, c)`. Tracks which tile images are loaded.
- `BackgroundAligner` — configures Leaflet bounds from meta. Re-anchors grid on center change.
- `History` — `push(snapshot)`, `undo()`, `redo()`. Snapshots are small (delta-based is fine; full copy is acceptable for grids ≤ 200×200).
- `TileLoader` — lazy-loads `kenney_pixel-shmup/Tiles/*.png` on demand via `<img>` + cache.
- `Toolbar` — pen selection, size input, city preset dropdown, undo/redo buttons, export button.
- `DeclExporter` — builds the JSON object and triggers download / writes to `input/`.

### `pipeline/editor/lookup.js` (generated)

One big JS object mapping (char + 4-bit neighbor mask) → tile file path. Generated at server start by replaying `resolve.py` rules over a synthetic grid. Example shape:

```js
window.TILE_LOOKUP = {
  "S":     { "any": "kenney_pixel-shmup/Tiles/tile_0098.png" },
  "G_0000":{ "any": "kenney_pixel-shmup/Tiles/tile_0050.png" },
  "G_0001":{ "top": "kenney_pixel-shmup/Tiles/tile_0108.png", ... },
  // ... ~80-120 entries total
};
```

### `pipeline/editor/meta.json` (generated)

```json
{
  "name": "shanghai_50km",
  "center_lat": 31.2304,
  "center_lng": 121.4737,
  "span_km": 50,
  "rows": 60,
  "cols": 80,
  "city_presets": ["shanghai", "beijing", "hangzhou", "syracuse"]
}
```

## Data Flow

### Launch

1. User runs `just edit` (or `just edit shanghai_50km --rows 60 --cols 80`).
2. `editor_server.py` resolves city preset → meta (center, span_km).
3. Python replays `resolve.py` rules to build `lookup.js`. Tile file paths come from the `kenney_pixel-shmup/Tiles/` directory; the script scans the directory and uses known suffixes from `resolve.py` to assign each (char, neighbor-mask) to a tile.
4. `meta.json` is written. `editor.html` and `editor.js` are served as-is.
5. Browser opens, Leaflet initializes centered on `meta.center_lat/lng` with the right zoom level for `span_km`.
6. Canvas overlay is sized to cover the visible map area, divided into `rows × cols`.

### Painting

1. `mousedown` on canvas → translate pixel → cell (r, c) → `GridModel.set(r, c, penChar)`.
2. `TileResolver.resolve(grid, r, c)` → returns tile file path.
3. `TileLoader.load(path)` → returns cached `<img>` or fetches it. Add to render queue.
4. `Renderer.drawCell(r, c)` → blit image onto canvas.
5. `History.push(gridSnapshot)`.
6. Debounced (300ms) save of `grid` to `localStorage` for crash recovery.

### Re-anchor / Re-size

1. User changes center lat/lng OR rows/cols OR span_km in the toolbar.
2. `BackgroundAligner.reconfigure(meta)` updates Leaflet bounds.
3. Canvas is resized: new `cols × rows` cells fit the new visible area.
4. Existing painted cells are kept by relative position (top-left of grid stays anchored) OR cleared (user choice, default: keep, re-flow).

### Export

1. User clicks [Export] → modal shows generated JSON.
2. `DeclExporter.build()` constructs:
   ```json
   {
     "name": "<name>",
     "kind": "single",
     "rows": <rows>,
     "cols": <cols>,
     "center_lat": <center_lat>,
     "center_lng": <center_lng>,
     "span_km": <span_km>,
     "map": ["SSS...", "SGG...", ...]
   }
   ```
3. Three actions available:
   - **Download** — saves `<name>_decl.json` via browser download.
   - **Copy** — copies JSON to clipboard.
   - **Save to input/** — POSTs to `editor_server.py` which writes to `input/<name>_decl.json` and returns 200.
4. After save, terminal shows: `Saved input/<name>_decl.json — run: just build <name>`.

## Tile Resolver (JS port of `resolve.py`)

Direct translation of `_beach`, `_road`, `resolve_tile` from `pipeline/resolve.py`. Same char set, same neighbor analysis, same desc string format. The lookup is generated at server start by iterating over all `(char, 4-bit-mask)` combinations, calling the Python `resolve_tile` against a synthetic minimal grid, and recording the resulting desc → file mapping.

The JS side just does a dictionary lookup; the actual logic lives in `resolve.py` and is the single source of truth.

## Storage

- **Draft state** (during editing): `localStorage` keyed by `<name>`. Auto-save every 300ms.
- **Exported file**: `input/<name>_decl.json` (matches existing schema, feeds `stage1-local`).
- **No intermediate files** in `output/`. The editor is upstream of the pipeline.

## Constraints & Non-Goals

- **No build step.** Single HTML file, vanilla JS, CDN Leaflet.
- **No new dependencies.** Uses existing `kenney_pixel-shmup/Tiles/*.png` and `pipeline/resolve.py`.
- **No server-side state.** `editor_server.py` is just a static-file server + a single `POST /save` endpoint.
- **One map at a time.** No multi-map UI. Close tab to switch.
- **No multi-user / collaboration.** Single browser session.
- **No undo for "clear all" / "resize" operations.** These are destructive and show a confirm dialog.
- **Tile registry is read-only in v1.** User picks pen from fixed set (G/S/O/R/r/L); no custom tile upload.

## Error Handling

| Scenario | Behavior |
|----------|----------|
| City preset not found | Fall back to blank center (0,0), warn user |
| Tile image 404 | Show red cell + console error, allow continued editing |
| `localStorage` full | Disable auto-save, show warning in status bar |
| Export: rows/cols mismatch map shape | Reject with explicit error, show in modal |
| `POST /save` fails | Show error, suggest "Download" as fallback |
| Resize to > 200×200 | Confirm dialog (perf warning for 100k+ cells) |

## Testing

- **Unit (Python):** test `editor_server.py` generates valid `lookup.js` for all char × mask combinations.
- **Unit (JS):** test `TileResolver` against fixtures generated from `resolve.py` outputs.
- **Integration:** end-to-end test: `just edit foo` → paint few cells → export → `just build foo` → assert `output/foo/foo_resolved.json` matches expectations.
- **Manual:** smoke test with `just smoke` after adding editor to the smoke test workflow.

## Launch / CLI

```bash
# Blank editor, user picks city in UI
just edit

# Pre-filled with a known city
just edit shanghai_50km --city shanghai --span-km 50 --rows 60 --cols 80

# Open an existing draft (loads from localStorage)
just edit shanghai_50km
```

`just` recipes added to `justfile`:
```makefile
edit name="":
    @if [ -z "{{name}}" ]; then \
        {{PY}} pipeline/editor/editor_server.py; \
    else \
        {{PY}} pipeline/editor/editor_server.py --name {{name}}; \
    fi
```

## Open Questions

(none — all resolved during brainstorming)
