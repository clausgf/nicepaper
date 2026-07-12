# Epaper Doorsign Manager

A web application that renders screens (e.g. door signs with room
calendars) as PNG images for e-paper displays. It is built with FastAPI
(REST API for the displays) and NiceGUI (management UI).

Displays poll the API for their image; the server renders screens from
JSON configuration files, caches the result and answers with proper
`ETag`/`Cache-Control` headers so displays only download new images when
the content actually changed.

## Features

- **Screens**: JSON-configured layouts made of widgets (`Text`, `Date`,
  `RoomCalendar`) rendered onto an RGB canvas with Pillow.
- **Room calendar widget**: fetches an iCal feed (with recurring event
  expansion), caches it and shows the current/next appointments.
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
  and delete files, edit screens with a validated JSON editor and live
  image previews, edit schedules as a card per weekly rule with
  checkboxes/multiselects and inline validation. No built-in
  authentication — put it behind an authenticating reverse proxy if the
  UI shouldn't be open to anyone who can reach it.

## Project structure

```
epaper-nice
├── app
│   ├── api/endpoints.py      # REST API for the displays
│   ├── ui/frontend.py        # NiceGUI management frontend
│   ├── core
│   │   ├── screen.py         # screen rendering
│   │   ├── imagecache.py     # image + metadata cache, palette quantization
│   │   ├── drawingcontext.py # drawing helpers (fonts, text, alignment)
│   │   ├── updateschedule.py # update schedule evaluation
│   │   ├── widgets/          # Text, Date, RoomCalendar widgets
│   │   └── datasources/      # iCal feed loading and caching
│   ├── models/               # pydantic models for screens and schedules
│   ├── config.py             # application settings
│   └── main.py               # FastAPI app wiring
├── tests                     # pytest suite (unit + acceptance)
├── data                      # runtime data (not in git)
│   ├── screens/              # screen configuration JSON files
│   ├── schedules/            # update schedule JSON files
│   ├── images/               # rendered image cache
│   └── ical/                 # iCal feed cache
├── examples                  # example configuration files to copy into data/
├── resources
│   ├── fonts/
│   └── icons/
├── Dockerfile / docker-compose.yml
└── pyproject.toml / uv.lock
```

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
uv run uvicorn app.main:app --reload
```

- Management UI: `http://127.0.0.1:8000/ui`
- API docs: `http://127.0.0.1:8000/docs`
- Display image: `http://127.0.0.1:8000/api/screen/<id>/image.png`
  (optional `?color_model=bw|bwr|gs4|c7|e6`)

`<id>` is the name of a JSON file in `data/screens` without the
extension, or an alias from `data/aliases.json`.

Alternatively use Docker: adjust `PUID`/`PGID` in `docker-compose.yml`
and run `docker compose up --build`.

## Configuration

Settings live in `app/config.py` and can be overridden with environment
variables (pydantic-settings), e.g.:

- `STORAGE_SECRET`: secret for NiceGUI browser session storage.

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
