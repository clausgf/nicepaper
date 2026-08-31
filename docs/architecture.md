# Architecture

[← Documentation](README.md)

## Project structure

```
nicepaper
├── main.py                     # standalone entry point (uvicorn main:app);
│                                # NOT part of the installable extension package
├── extensions/epaper           # the installable package (extensions.epaper)
│   ├── __init__.py              # register(app) -- nice4iot extension entry point
│   ├── paths.py                 # EpaperPaths: per-root file locations
│   ├── config.py                # package-resource paths (fonts/icons), not user-editable
│   ├── api/endpoints.py         # build_standalone_router() / build_extension_router()
│   ├── catalog/                 # models.py (Palette, PanelTypeModel), backend.py (package + per-root catalog, no ui.py -- read-only reference data, selected inside screen/ui.py)
│   ├── screen/                  # feature pkg: models.py, backend.py (render/cache), ui.py (editor), simplified_ui.py (Templates, scaffolding)
│   ├── schedule/                # feature pkg: models.py, backend.py (evaluation), ui.py (editor)
│   ├── room/                    # feature pkg: models.py, backend.py (storage), ui.py (editor tab), simplified_ui.py
│   ├── bookingsystem/           # feature pkg: models.py, backend.py (storage), simplified_ui.py
│   ├── display/                 # feature pkg: models.py (row), backend.py (device<->room<->screen join), simplified_ui.py (grid)
│   ├── devicebinding/           # feature pkg: models.py, backend.py (device->screen/room store), ui.py (device card)
│   ├── global_config/           # feature pkg: models.py (GlobalConfig), backend.py (app_config singleton + persist), ui.py (form)
│   ├── project_config/          # feature pkg: models.py (ProjectConfig, per-root), backend.py (read/persist), ui.py (form)
│   ├── ui                       # shared content-only rendering, reused by both modes
│   │   ├── forms.py             # form vocabulary: field styling, spacing, hints
│   │   ├── drilldown.py         # file list <-> editor chrome, inline rename
│   │   ├── widget_types.py      # per-widget-type table: icon, title, form
│   │   ├── preview.py           # preview image, pixel ruler, toolbar
│   │   ├── cards.py             # nice4iot dashboard summary card
│   │   ├── standalone.py        # @ui.page routes + chrome, standalone only
│   │   └── simplified_ui/       # room-focused page: shared frame (layout, common)
│   ├── core                     # shared rendering infrastructure
│   │   ├── imagecache.py        # image + metadata cache, palette quantization
│   │   ├── drawingcontext.py    # drawing helpers (fonts, text, alignment)
│   │   ├── charting.py          # hand-rolled bar/line charts (no plotting library)
│   │   ├── gauge.py             # gauge rendering
│   │   ├── widgets/             # Text, Date, RoomCalendar, Weather* widgets
│   │   └── datasources/         # iCal and Open-Meteo weather loading/caching
│   ├── wire/huffman_de.py       # fixed German Huffman codebook (LoRaWAN, WIP)
│   └── resources/               # fonts/icons + display/palette catalogs (package data)
├── tests                       # pytest suite (unit + acceptance)
├── data                        # standalone-mode runtime data (not in git)
│   ├── screens/                  # screen configuration JSON files
│   ├── schedules/                # update schedule JSON files
│   ├── images/                   # rendered image cache
│   ├── ical/                     # iCal feed cache
│   └── weather/                  # Open-Meteo forecast cache
├── examples                    # example configuration files to copy into data/
├── firmware/huffman_de.h       # generated C codebook (see design-lorawan.md)
└── pyproject.toml / uv.lock
```

Everything under `extensions/epaper/` is reusable between standalone and
extension mode; `main.py`, `data/`, `examples/` and `tests/` only matter
for standalone (development/debugging) use and aren't part of the wheel
(see [`pyproject.toml`](../pyproject.toml)'s `only-include = ["extensions"]`).

## Standalone vs. nice4iot extension

This repository serves two purposes from the same code:

- **Standalone**: one fixed data root (`data/`), its own login-free NiceGUI
  pages (`/ui/screens`, `/ui/schedules`, ...). For development and debugging
  only, not a deployment target. Entry point: `main.py`. See
  [Development](development.md).
- **nice4iot extension** (`extensions.epaper`): installed as a normal
  `uv`/pip dependency of a [nice4iot](https://github.com/clausgf/nice4iot)
  deployment (`uv add git+https://github.com/clausgf/nicepaper.git`,
  matching how nicepaper itself depends on `niceview`). nice4iot discovers and
  calls `extensions/epaper/__init__.py`'s `register(app)` at startup
  (see nice4iot's `docs/extensions.md`); no separate configuration step.
  Deploying nice4iot with this extension enabled — the Docker/Compose
  image, reverse-proxy wiring, etc. — is owned by
  [nice4iot](https://github.com/clausgf/nice4iot) itself (build it with
  the `epaper` extra: `uv sync --extra epaper`), not by this repository.

In extension mode:

- Each nice4iot **project** gets its own screens/schedules, stored at
  `<project>/.epaper/` (via `extension_project_dir`), not the shared
  `data/` directory.
  - REST: `/api/ext/epaper/<project>/screens/<id>/image.png`, gated
    by nice4iot's per-project extension activation (General tab →
    Extensions card) before the handler runs.
- UI: a project Dashboard card (screen/schedule counts, plus one health line
  per weather location / Home Assistant entity / iCal feed / image source
  that is failing or serving stale cached data, so an outage is visible
  without opening a screen -- see `ui/cards.py`'s `dashboard_card()`) and a
  link into the Screens tab; a Settings card on nice4iot's project Settings
  sidebar group (`register_project_card('settings', ..., title='Settings')`,
  chrome supplied by nice4iot); and Rooms/Screens/Schedules/Booking systems
  tabs registered via `register_project_tab` on nice4iot's own project
  page — no separate routes of our own. No built-in login here either —
  nice4iot's own auth and per-project activation gate access.
- Each nice4iot **device**'s General tab gets an "E-Paper" card
  (`register_device_card('settings', ...)`) to assign the device a screen
  (the image it renders) and a room (where it hangs). Both are stored in
  `<project>/.epaper/device_bindings.json` keyed by the device's own name
  (the same binding described under
  [Display bindings](screens.md#display-bindings)), and the card then shows the
  resulting device-specific image URL — so the device firmware only
  ever needs to know its own name, never the screen id, and every
  header (`If-None-Match`) keeps working unchanged since it's the same
  image endpoint. The room half is the device→room relation the simplified
  UI reads back as the displays in a room.

`extensions/epaper/__init__.py` defers every nice4iot-specific import
(`app.extensions`, `app.paths`, `app.routes`) into `register()`'s
body rather than module level. Python runs a package's `__init__.py`
on import of *any* of its submodules, so a module-level import there
would break standalone mode outright (nice4iot's `app` package isn't
installed/importable in that process).
