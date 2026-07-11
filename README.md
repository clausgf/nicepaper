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
- **Management UI**: create and delete screen and schedule files, edit
  screens with a validated JSON editor and live image previews, edit
  schedules as a card per weekly rule with checkboxes/multiselects and
  inline validation.

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

### Authentication

`AUTH_PROVIDER` selects how the UI authenticates users:

- `proxy` (default): an authenticating reverse proxy in front of the
  app (e.g. Caddy with oauth2-proxy) handles the login; the app reads
  the forwarded identity from request headers.
  - `AUTH_USER_HEADERS`: JSON list of headers carrying the username
    (defaults match oauth2-proxy: `X-Forwarded-Preferred-Username`,
    `X-Forwarded-User`, `X-Forwarded-Email`); the first non-empty
    value is shown in the UI.
  - `AUTH_LOGOUT_URL`: logout link shown in the user menu, e.g.
    `/oauth2/sign_out`; unset hides the entry.
  - The headers are only trustworthy when the app is reachable
    exclusively through the proxy.
  - Deployment note (Caddy + oauth2-proxy): oauth2-proxy must be told
    to expose the identity (`--set-xauthrequest`, and/or
    `--pass-user-headers` when proxying through oauth2-proxy itself)
    and Caddy's `forward_auth` block must forward it to the app, e.g.

    ```
    forward_auth oauth2-proxy:4180 {
        uri /oauth2/auth
        copy_headers X-Auth-Request-Preferred-Username>X-Forwarded-Preferred-Username X-Auth-Request-User>X-Forwarded-User X-Auth-Request-Email>X-Forwarded-Email
    }
    ```

    Set `AUTH_LOGOUT_URL=/oauth2/sign_out` for a working logout entry.
    After deploying, check once which of the configured headers
    actually arrives and adjust `AUTH_USER_HEADERS` if needed.
- `password`: built-in login page. Users live in an htpasswd file with
  bcrypt hashes (`AUTH_HTPASSWD_FILE`, default `data/htpasswd`),
  maintained with the standard Apache tool:

  ```
  htpasswd -c -B data/htpasswd alice   # create file and first user
  htpasswd -B data/htpasswd bob        # add/update further users
  ```

  Only bcrypt entries (`-B`) are accepted; the file is re-read on each
  login attempt, so changes apply without a restart. Set a strong
  `STORAGE_SECRET`, since it signs the session cookie.
- `none`: no authentication (local development).

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
  into the app, add an `ApiKeyAuthProvider` next to the existing
  providers, enforced as a FastAPI dependency on the `/api` router
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
