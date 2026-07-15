# Epaper Doorsign Manager

A web application that renders screens (e.g. door signs with room
calendars) as PNG images for e-paper displays. It is built with FastAPI
(REST API for the displays) and NiceGUI (management UI). Runs standalone,
or installable as a [nice4iot](https://github.com/clausgf/nice4iot)
extension (`extensions.epaper`) — see
[Standalone vs. nice4iot extension](#standalone-vs-nice4iot-extension).

Displays poll the API for their image; the server renders screens from
JSON configuration files, caches the result and answers with proper
`ETag`/`Cache-Control` headers so displays only download new images when
the content actually changed.

## Features

- **Screens**: JSON-configured layouts made of widgets (`Text`, `Date`,
  `RoomCalendar`, `WeatherNow`, `WeatherForecast`, `WeatherChart`) rendered
  onto an RGB canvas with Pillow.
- **Room calendar widget**: fetches an iCal feed (with recurring event
  expansion), caches it and shows the current/next appointments.
- **Weather widgets**: current conditions, an hourly forecast strip, and
  `WeatherChart` (one configurable bar/line chart -- `primary_metric`
  always shown, `secondary_metric` optional on its own right Y axis, e.g.
  temperature + precipitation combined), backed by
  [Open-Meteo](https://open-meteo.com) (no API key needed; uses the DWD
  ICON model for German/European locations). Icons reuse the bundled
  `fa-solid-900.ttf` (no new font/image assets). Charts are hand-drawn with
  Pillow, not a plotting library, so they render crisply on bilevel/limited
  palettes instead of dithering, with gridlines/axis labels rounded to
  nice human-friendly numbers — see `extensions/epaper/core/charting.py`.
- **Widget clipping / debug outline**: a widget's `clipping` flag cuts off
  content that overflows its box instead of letting it bleed into
  neighboring widgets; `show_bounding_box` draws its box outline, handy
  while laying out a screen.
- **Color models**: rendered images can be quantized to e-paper palettes
  (`bw`, `bwr`, `gs4`, `c7`, `e6`) via the `color_model` query parameter.
- **Update schedules**: a schedule file is a plain JSON list of weekly
  rules (weekdays, months, times of day) that determine when a screen
  expires and is re-rendered.
- **Display aliases**: an optional `data/aliases.json` file maps friendly
  names to screen ids, e.g. `{"hallway": "epaper_43bw"}`, so a display
  can be addressed by a stable name instead of the screen file name, and
  several displays can share one screen.
- **Management UI**: two top-level tabs, Screens and Schedules. Create
  and delete files; edit a screen's canvas size/update schedule plus a
  drag-reorderable widget list (add by type, drill down into a per-type
  form, live RGB/palette image previews on top) and schedules as a card
  per weekly rule with checkboxes/multiselects and inline validation. No
  built-in authentication — put it behind an authenticating reverse
  proxy if the UI shouldn't be open to anyone who can reach it.

## Project structure

```
epaper-nice
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
│   ├── wire/huffman_de.py       # fixed German Huffman codebook (see below)
│   └── resources/               # fonts/icons, bundled as package data
├── tests                       # pytest suite (unit + acceptance)
├── data                        # standalone-mode runtime data (not in git)
│   ├── screens/                  # screen configuration JSON files
│   ├── schedules/                # update schedule JSON files
│   ├── images/                   # rendered image cache
│   ├── ical/                     # iCal feed cache
│   └── weather/                  # Open-Meteo forecast cache
├── examples                    # example configuration files to copy into data/
├── firmware/huffman_de.h       # generated C codebook, see Low-bandwidth rendering
├── Dockerfile / docker-compose.yml
└── pyproject.toml / uv.lock
```

Everything under `extensions/epaper/` is reusable between standalone and
extension mode; `main.py`, `data/`, `examples/`, `tests/`,
`Dockerfile`/`docker-compose.yml` only matter for standalone deployment
(and aren't part of the wheel — see
[`pyproject.toml`](pyproject.toml)'s `packages = ["extensions/epaper"]`).

## Installation

The project is managed with [uv](https://docs.astral.sh/uv/).

1. Clone the repository and install the dependencies:

   ```
   uv sync
   ```

   The schedule editor's card UI is built on
   [niceview](https://github.com/clausgf/niceview), pinned in `uv.lock`
   as a git dependency (pre-1.0, no PyPI release yet) — `uv sync` needs
   network access to GitHub the first time. Run
   `uv lock --upgrade-package niceview && uv sync` to pick up upstream
   changes.

2. Create the runtime data directories and copy the example
   configuration to get a working screen right away:

   ```
   mkdir -p data/screens data/schedules data/images data/ical
   cp examples/schedules/default.json data/schedules/
   cp examples/screens/simple.json data/screens/
   ```

   `examples/screens/roomcalendar.json` shows the `RoomCalendar` widget;
   edit its `ical_url` (and `examples/aliases.json`,
   `examples/organizer_names.json` if needed) before copying it in, see
   [Examples](#examples) below.

## Usage

Start the application from the repository root:

```
uv run uvicorn main:app --reload
```

- Management UI: `http://127.0.0.1:8000/ui`
- API docs: `http://127.0.0.1:8000/docs`
- Display image: `http://127.0.0.1:8000/api/screen/<id>/image.png`
  (optional `?color_model=bw|bwr|gs4|c7|e6`)

`<id>` is the name of a JSON file in `data/screens` without the
extension, or an alias from `data/aliases.json`.

Alternatively use Docker: adjust `PUID`/`PGID` in `docker-compose.yml`
and run `docker compose up --build`.

## Standalone vs. nice4iot extension

This repository serves two purposes from the same code:

- **Standalone** (the above): one fixed data root (`data/`), its own
  login-free NiceGUI pages (`/ui/screens`, `/ui/schedules`, ...), own
  Docker deployment. Entry point: `main.py`.
- **nice4iot extension** (`extensions.epaper`): installed as a normal
  `uv`/pip dependency of a [nice4iot](https://github.com/clausgf/nice4iot)
  deployment (`uv add git+https://.../epaper-nice.git`, matching how
  epaper-nice itself depends on `niceview`). nice4iot discovers and
  calls `extensions/epaper/__init__.py`'s `register(app)` at startup
  (see nice4iot's `docs/extensions.md`); no separate configuration step.
  In this mode:
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
    [Display aliases](#features) above), and the card then shows the
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

## Low-bandwidth rendering (work in progress)

Besides the PNG image API, a second, very low-bandwidth rendering channel
is planned for e.g. LoRaWAN displays: instead of shipping a rendered
image, only widget *data* is sent (over MQTT to TTN) and the
(self-built) device firmware renders the widgets locally. Only string
fields (event titles, organizer names, ...) are meant to be compressed;
numeric/enum fields (dates, times, weekdays) are cheap enough to pack
directly without any coding.

So far only the compression codec exists, not the wire format or
transport: `extensions/epaper/wire/huffman_de.py` implements a *fixed*
(non-adaptive) Huffman codebook for German text, so encoder and decoder
never need to exchange a header — both must simply agree on the same
static symbol table. The current table (`_WEIGHTS`) is a generic
estimate from standard German letter frequencies, not yet derived from a
real corpus of the strings it will actually carry; expect to retune it
later. Characters outside the table fall back to raw UTF-8 bytes behind
an ESCAPE symbol, so encoding never fails, just compresses worse.

Since the device firmware is C, not Python, `firmware/huffman_de.h` is a
generated, self-contained C header with the same codebook baked in as
literal data (not recomputed from scratch in C, to rule out the two
implementations ever disagreeing) plus a decode function — encoding only
happens server-side. Regenerate it after editing `_WEIGHTS`:

```
uv run python -m extensions.epaper.wire.huffman_de
```

## Configuration

`extensions/epaper/config.py`'s `Config` (a pydantic-settings `BaseSettings`)
holds settings that are the same for every screen/root -- defaults, locale,
color models, the shared font/icon resource paths, ... This is process
configuration, not persisted anywhere: `app_config = Config()` is built once
at import time from its field defaults, optionally overridden by matching
environment variables (case-insensitive, e.g. `STORAGE_SECRET`), and there
is no `.env` file loading configured. Per-screen/per-widget settings (size,
position, fonts, ...) live in the screen/schedule JSON files instead (see
[Project structure](#project-structure) and [Examples](#examples)) --
`Config` is only for things that don't vary per screen.

Commonly overridden variables:

- `STORAGE_SECRET`: secret for NiceGUI browser session storage.
- `LOCALE`, `TIMEZONE`, `DATE_FORMAT`, `TIME_FORMAT`: defaults used where a
  screen/widget doesn't set its own.
- `ICAL_UPDATE_INTERVAL_S`, `ICAL_MAX_DAYS`: iCal feed polling/lookahead for
  the `RoomCalendar` widget.
- `WEATHER_UPDATE_INTERVAL_S`: Open-Meteo polling interval for the `Weather*`
  widgets. `COLOR_ACCENT`: RGB color the chart widgets use for their primary
  data series (defaults to red, the only accent the `bwr` color model has).

See the `Config` class itself for the full list (every field is overridable
the same way); complex fields (`epaper_color_models`, tuples) need their
environment variable value JSON-encoded, per pydantic-settings' rules.

There is no built-in authentication (the previous htpasswd/reverse-proxy
provider setup was removed — nice4iot integration, if pursued, handles
auth on its own). Put the UI behind an authenticating reverse proxy if
it shouldn't be reachable by anyone who can reach the host.

## Examples

`examples/` holds ready-to-copy configuration files (git-tracked, unlike
`data/`, so they double as living documentation of the JSON formats):

- `examples/schedules/default.json`: a weekly update schedule (three
  times on weekdays, once on weekends). Screens default to
  `update_schedule_id: "default"`, so most setups need this file.
- `examples/screens/simple.json`: a minimal screen with `Text` and
  `Date` widgets, no external dependencies.
- `examples/screens/roomcalendar.json`: a full-size door sign using the
  `RoomCalendar` widget. Set `ical_url` to a real iCal feed before use.
- `examples/screens/weather.json`: all three `Weather*` widgets (current
  conditions, forecast strip, and a combined temperature+precipitation
  chart) for Berlin; adjust `latitude`/`longitude` for your location.
- `examples/aliases.json`: maps the alias `hallway` to the
  `roomcalendar` screen, see [Display aliases](#features) above.
- `examples/organizer_names.json`: example entries for
  `organizer_names_file`, used to extract an organizer's name from an
  event summary when the iCal feed has no `ORGANIZER` field.

Copy the ones you need into the matching `data/` subdirectory (see
[Installation](#installation)); they are plain screen/schedule files, so
they also work as a starting point to edit in the management UI.

## Tests

All tests live in `tests/`; acceptance tests that exercise the HTTP API
end-to-end are in `tests/test_acceptance.py`, the rest are unit tests:

```
uv run pytest
```

## TODO / Open points

- **API keys for the display API**: `/api` is currently protected by
  external middleware in front of the app. If that check should move
  into the app, enforce it as a FastAPI dependency on the `/api` router
  (`X-Api-Key` header). Proposed key management: a file
  `data/api_keys.json` mapping a label per display to the SHA-256 hex
  hash of its key, e.g. `{"display-r101": "<sha256-hex>"}`. Plain
  SHA-256 is sufficient here (keys are high-entropy random strings, so
  brute-forcing the hash is hopeless, and bcrypt would waste ~100 ms on
  every image request). Generate a key and its hash with:

  ```
  python3 -c "import secrets, hashlib; k = secrets.token_urlsafe(32); print(k, hashlib.sha256(k.encode()).hexdigest())"
  ```

  Revocation = delete the line; one key per display so keys can be
  revoked individually.
