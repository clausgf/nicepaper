# Screens, widgets & schedules

[← Documentation](README.md)

A **screen** is a JSON file in `data/screens/` describing an RGB canvas and a
list of widgets rendered onto it with Pillow. A display fetches the rendered
result at `/api/screen/<id>/image.png`. This page describes the JSON formats;
the ready-to-copy files under [`examples/`](../examples) are the living
reference for them.

## Widgets

A screen's `widgets` list is made of typed widgets, each positioned with
`position_x`/`position_y`/`size_width`/`size_height`:

- **`Text`** / **`Date`** — static text and a formatted current date
  (`date_format`, e.g. `EEEE, dd. MMMM yyyy`), with configurable font and size.
- **`RoomCalendar`** — fetches an iCal feed (`ical_url`) with recurring-event
  expansion, caches it, and shows the current and next appointments plus a
  list of further ones. `room_number`/`room_name` label the screen.
- **`WeatherNow`** / **`WeatherForecast`** / **`WeatherChart`** — current
  conditions, an hourly forecast strip, and one configurable bar/line chart.
  `WeatherNow` shows temperature, the condition, and wind (speed, direction as
  an 8-point compass, and gusts). Its text language follows `LOCALE` and the
  wind-speed unit follows `WIND_SPEED_UNIT` (see [Configuration](configuration.md)).
  In `WeatherChart`, `primary_metric` is always shown and `secondary_metric`
  is optional on its own right Y axis (e.g. temperature + precipitation
  combined). Available metrics are `temperature`, `precipitation`, `humidity`,
  `pressure` and `wind` (the wind series honours `WIND_SPEED_UNIT`). Each axis
  is titled with its metric name and unit above the plot (primary left,
  secondary right) — e.g. `Temperatur (°C)`, `Wind (km/h)` — in the `LOCALE`
  language. All three are backed by [Open-Meteo](https://open-meteo.com)
  (no API key needed; the DWD ICON model for German/European locations) and
  are placed by `latitude`/`longitude`. Icons reuse the bundled
  `fa-solid-900.ttf` (no extra font/image assets). Charts are hand-drawn with
  Pillow, not a plotting library, so they render crisply on bilevel/limited
  palettes instead of dithering, with gridlines/axis labels rounded to nice
  human-friendly numbers — see `extensions/epaper/core/charting.py`.

### Clipping and debug outline

A widget's `clipping` flag cuts off content that overflows its box instead of
letting it bleed into neighboring widgets; `show_bounding_box` draws its box
outline, handy while laying out a screen.

## Color models

Rendered images can be quantized to e-paper palettes via the `color_model`
query parameter: `bw`, `bwr`, `gs4`, `c7`, `e6`
(`/api/screen/<id>/image.png?color_model=bwr`). The management UI's Image
Preview shows the same palettes as tabs. `COLOR_ACCENT` (see
[Configuration](configuration.md)) is the RGB color the chart widgets use for
their primary series — red by default, the only accent the `bwr` model has.

## Display aliases

An optional `data/aliases.json` file maps friendly names to screen ids, e.g.
`{"hallway": "epaper_43bw"}`, so a display can be addressed by a stable name
instead of the screen file name, and several displays can share one screen.
(In nice4iot extension mode, assigning a screen to a device writes such an
alias automatically — see [Architecture](architecture.md).)

## Update schedules

A schedule file in `data/schedules/` is a plain JSON list of weekly rules
(weekdays, months, times of day) that determine when a screen expires and is
re-rendered. Screens reference one by `update_schedule_id` (default:
`"default"`, so most setups need a `default.json`). The management UI edits a
schedule as one card per weekly rule with weekday checkboxes, a month
multiselect, and time chips.

Leaving `update_schedule_id` empty means the screen has no schedule and is only
re-rendered on request or when a widget provides its own expiry (e.g. a
`RoomCalendar`'s next event). A *non-empty* `update_schedule_id` that points at
a missing schedule file is a dangling reference: the screen still renders but
isn't re-rendered on a schedule. This is flagged in the management UI (an inline
warning in the screen editor and a warning icon in the screen list) and logged
at `warning` level, rather than failing silently.

## Examples

[`examples/`](../examples) holds ready-to-copy configuration files
(git-tracked, unlike `data/`, so they double as documentation of the JSON
formats):

- `examples/schedules/default.json` — a weekly update schedule (three times on
  weekdays, once on weekends). Screens default to `update_schedule_id:
  "default"`, so most setups need this file.
- `examples/screens/simple.json` — a minimal screen with `Text` and `Date`
  widgets, no external dependencies.
- `examples/screens/roomcalendar.json` — a full-size door sign using the
  `RoomCalendar` widget. Set `ical_url` to a real iCal feed before use.
- `examples/screens/weather.json` — all three `Weather*` widgets (current
  conditions, forecast strip, and a combined temperature+precipitation chart)
  for Berlin; adjust `latitude`/`longitude` for your location.
- `examples/aliases.json` — maps the alias `hallway` to the `roomcalendar`
  screen, see [Display aliases](#display-aliases).
- `examples/organizer_names.json` — example entries for `organizer_names_file`,
  used to extract an organizer's name from an event summary when the iCal feed
  has no `ORGANIZER` field.

Copy the ones you need into the matching `data/` subdirectory (see
[Development](development.md)); they are plain screen/schedule files, so they
also work as a starting point to edit in the management UI.
