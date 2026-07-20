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
│   ├── config.py                # settings that are the same for every root
│   ├── api/endpoints.py         # build_standalone_router() / build_extension_router()
│   ├── ui
│   │   ├── panels.py            # content-only rendering (reused by both modes)
│   │   └── standalone.py        # @ui.page routes + chrome, standalone only
│   ├── core
│   │   ├── screen.py            # screen rendering, screen cache
│   │   ├── imagecache.py        # image + metadata cache, palette quantization
│   │   ├── drawingcontext.py    # drawing helpers (fonts, text, alignment)
│   │   ├── updateschedule.py    # update schedule evaluation
│   │   ├── charting.py          # hand-rolled bar/line charts (no plotting library)
│   │   ├── widgets/             # Text, Date, RoomCalendar, Weather* widgets
│   │   └── datasources/         # iCal and Open-Meteo weather loading/caching
│   ├── models/                  # pydantic models for screens and schedules
│   ├── wire/huffman_de.py       # fixed German Huffman codebook (LoRaWAN, WIP)
│   └── resources/               # fonts/icons, bundled as package data
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
- UI: a project Dashboard card (screen/schedule counts, link into the
  Screens tab) plus Screens/Schedules tabs registered via
  `register_project_tab` on nice4iot's own project page — no separate
  routes of our own. No built-in login here either — nice4iot's own
  auth and per-project activation gate access.
- Each nice4iot **device**'s General tab gets an "E-Paper" card
  (`register_device_card('general', ...)`) to optionally assign one of
  the project's screens to that device. Assigning a screen adds an
  entry to `<project>/.epaper/aliases.json` keyed by the device's own
  name (the same alias mechanism described under
  [Display aliases](screens.md#display-aliases)), and the card then shows the
  resulting device-specific image URL — so the device firmware only
  ever needs to know its own name, never the screen id, and every
  existing query parameter/header (`color_model`, `If-None-Match`, ...)
  keeps working unchanged since it's the same image endpoint.

`extensions/epaper/__init__.py` defers every nice4iot-specific import
(`app.extensions`, `app.paths`, `app.routes`) into `register()`'s
body rather than module level. Python runs a package's `__init__.py`
on import of *any* of its submodules, so a module-level import there
would break standalone mode outright (nice4iot's `app` package isn't
installed/importable in that process).
