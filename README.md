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
- **Update schedules**: JSON-configured schedules determine when a screen
  expires and is re-rendered.
- **Management UI**: create, edit, validate and delete screen and
  schedule files with a JSON editor and live image previews.

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
├── data                      # runtime data (not in git)
│   ├── screens/              # screen configuration JSON files
│   ├── schedules/            # update schedule JSON files
│   ├── images/               # rendered image cache
│   └── ical/                 # iCal feed cache
├── resources
│   ├── fonts/
│   └── icons/
├── Dockerfile / docker-compose.yml
└── requirements.txt
```

## Installation

1. Clone the repository and create a virtual environment:

   ```
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Create the runtime data directories:

   ```
   mkdir -p data/screens data/schedules data/images data/ical
   ```

## Usage

Start the application from the repository root:

```
uvicorn app.main:app --reload
```

- Management UI: `http://127.0.0.1:8000/ui`
- API docs: `http://127.0.0.1:8000/docs`
- Display image: `http://127.0.0.1:8000/api/screen/<id>/image.png`
  (optional `?color_model=bw|bwr|gs4|c7|e6`)

`<id>` is the name of a JSON file in `data/screens` without the
extension.

Alternatively use Docker: adjust `PUID`/`PGID` in `docker-compose.yml`
and run `docker compose up --build`.

## Configuration

Settings live in `app/config.py` and can be overridden with environment
variables (pydantic-settings), e.g.:

- `STORAGE_SECRET`: secret for NiceGUI browser session storage.
- `AUTH_USER_HEADERS`: JSON list of request headers carrying the
  username forwarded by an authenticating reverse proxy (defaults match
  oauth2-proxy: `X-Forwarded-Preferred-Username`, `X-Forwarded-User`,
  `X-Forwarded-Email`). The UI shows the first non-empty value.
- `AUTH_LOGOUT_URL`: logout link shown in the user menu, e.g.
  `/oauth2/sign_out`; unset hides the entry.

## Tests

```
pytest app
```
