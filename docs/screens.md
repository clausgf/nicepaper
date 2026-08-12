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
- **`Image`** — renders an image loaded from a `url` or from a `file` in the
  project directory (`source_type` selects which). By default the image is
  loaded once and cached; set `reload_each_time` to re-fetch on every render
  (the editor also has a *Reload now* button). Size behaves specially: setting
  only `size_width` **or** `size_height` scales the image to that dimension
  keeping the aspect ratio, setting both scales to exactly that size, and
  leaving both empty uses the natural size. If the image can't be loaded within
  a fixed timeout, the configurable `image_error` message
  (see [Configuration](configuration.md)) is drawn instead. The widget has no
  font of its own. The selectable files live in the project directory — in the
  nice4iot extension that is the project directory where *Project Files* are
  managed, standalone it is the `data/` directory.
- **`HomeAssistant`** — shows one [Home Assistant](https://www.home-assistant.io)
  entity, fetched through HA's REST API (`GET /api/states/<entity_id>`). Pick
  the entity with `entity_id` and optionally read one of its attributes instead
  of the state (`attribute`, e.g. `temperature` of a `climate` entity).
  `label`/`unit` default to the entity's own `friendly_name`/
  `unit_of_measurement`, `decimals` rounds numeric values, and `show_label`
  toggles the label. `display` selects how the value is drawn:
  - `value` — one line of text (`alignment` as for `Text`).
  - `gauge` — a gauge on the `min_value` … `max_value` scale, either a 240° dial
    (`gauge_style: arc`) or a horizontal bar (`bar`). Values outside the scale
    are clamped; a non-numeric state (`on`, `unavailable`, …) leaves the scale
    empty and just shows the text.

  Gauges are drawn locally with Pillow (`extensions/epaper/core/gauge.py`), not
  fetched from Home Assistant: HA's own gauge cards are browser-rendered and
  can't be retrieved as an image, and a screenshot would dither on an e-paper
  palette. The filled part is solid (in the accent color), the rest stays an
  outline, so a gauge is still readable on a pure black/white display. An image
  Home Assistant *does* serve — a camera snapshot, an add-on-rendered dashboard —
  can be shown with the `Image` widget instead. The URL, token and intervals are
  global settings (see [Configuration](configuration.md)); as with weather,
  fetches back off on failure, the last-known value keeps being shown with the
  `homeassistant_stale_notice` marker, and the outage appears on the nice4iot
  Dashboard.
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
  are placed by `latitude`/`longitude` — leave **both** empty to use the
  default location from the global settings (see
  [Configuration](configuration.md)). The fallback is all-or-nothing: filling
  in only one of the two keeps the other at 0 rather than completing it from
  the global setting, which would put the widget somewhere neither setting
  describes. Icons reuse the bundled
  `fa-solid-900.ttf` (no extra font/image assets). Charts are hand-drawn with
  Pillow, not a plotting library, so they render crisply on bilevel/limited
  palettes instead of dithering, with gridlines/axis labels rounded to nice
  human-friendly numbers — see `extensions/epaper/core/charting.py`. During an
  Open-Meteo outage the fetch backs off and the last-known data keeps showing
  (`WeatherNow` with an "as of HH:MM" marker); the outage is also surfaced on
  the nice4iot Dashboard — see [Configuration](configuration.md).

### Clipping and debug outline

A widget's `clipping` flag cuts off content that overflows its box instead of
letting it bleed into neighboring widgets.

For laying out a screen, the **outline toggle** in the preview's toolbar shows
every widget's box at once. It renders on demand and is never cached, so the
outlines can't reach a display — which is why it replaced the old per-widget
`show_bounding_box` flag: that one was part of the screen and got drawn into
the image a display fetches, so it had to be remembered and turned off again.

A widget that sizes itself has no box to outline (its extent is only decided
while drawing), so the toggle marks its anchor — the `position_x`/`position_y`
point — with a small corner instead.

## Displays, palettes and colors

A screen is laid out for one panel, so the panel's properties are screen
settings — not something a display asks for per request:

| Field | Meaning |
| --- | --- |
| `width`, `height` | canvas size in pixels |
| `color_model` | id of the palette the image is quantized to before it is served (`bw`, `bwr`, `bwy`, `gs4`, `c7`, `e6`). Empty serves the unquantized RGB image. |
| `color_background`, `color_primary`, `color_accent` | this screen's colors; each empty field falls back to the global default (see [Configuration](configuration.md)) |
| `display_id` | which display preset was applied last, see below |

`/api/screen/<id>/image.png` serves the image quantized to that screen's
`color_model`, so the display needs no palette knowledge of its own and can't
ask for the wrong one — it is also exactly what the editor's Image Preview
shows. `?raw=true` returns the unquantized RGB render the quantization started
from, for debugging a color that dithers; a display never needs it.
`?boxes=true` renders the screen with every widget outlined — see
[Clipping and debug outline](#clipping-and-debug-outline). Both are editor
views; neither touches the cached image.

The preview is framed by a pixel ruler with labelled ticks on all four sides,
and moving the mouse over it shows the exact pixel under the cursor — widgets
are positioned by typing `position_x`/`position_y`, so the preview is only
useful if it can be read back as coordinates. Both are scale-independent: the
ruler is placed in percentages and the readout divides by the rendered size, so
they stay correct at whatever width the browser scales the image to.

Individual widgets can override `color_primary`/`color_accent` for themselves,
each aspect falling back to the screen's color independently — the same
per-aspect override `font_name`/`font_size` use. These two fields are not in
the editor form yet and are set in the screen JSON directly.

### Display presets

Instead of typing size, palette and colors by hand, pick a panel from the
**Display** list. It fills in all of the above — for a black/white panel it also
sets the accent to black, since red could only quantize to black there anyway.

Adding a screen offers the display list up front, since size and palette are
the first decisions about a screen and every widget position depends on them.
The same list is in the screen's settings, so the panel can be picked or
changed later just as well.

**No preset** is the default, and a listed choice in both — for a panel that
isn't in the catalog, or when you'd rather set size, palette and colors
yourself. A new screen then starts blank at 800×480 (no palette, so it is
served as RGB, and the global colors apply); picking it for an existing screen
only drops the `display_id` record and leaves its values untouched.

A preset is a **template, applied once**: after that the screen's own fields are
what renders, they stay editable, and a preset that is later changed or removed
never alters an existing screen. `display_id` only records which one was used.

The catalog ships with the package (currently Waveshare 4.2"/7.5"/7.3" and the
Seeed XIAO 7.5" panel) and is extended per data root by an optional
`data/displays.json` (`<project>/.epaper/displays.json` in extension mode).
Entries are merged by `id`, the root file wins, so it can both add panels that
aren't shipped and correct one that is:

```json
[
  {
    "id": "my-panel", "name": "My 5.83\" panel", "vendor": "Waveshare",
    "width": 648, "height": 480, "color_model": "bw",
    "color_background": "#ffffff", "color_primary": "#000000", "color_accent": "#000000",
    "gxepd2_class": "GxEPD2_583"
  }
]
```

`gxepd2_class` is informational only — nicepaper renders a PNG and never talks
to a panel driver. It is shown under the display list so a panel can be found
by the name its firmware knows it under.

Palettes work the same way: an optional `data/color_models.json` adds to (or
overrides) the shipped ones. Unlike `displays.json`, editing it changes what
gets served — a screen references a palette by id rather than containing it —
so a change there re-renders every screen using it.

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
- `examples/screens/homeassistant.json` — `HomeAssistant` widgets as arc and bar
  gauges plus text values (an attribute of a `climate` entity and a
  `binary_sensor`). Replace the entity ids with your own and configure the
  Home Assistant URL/token first.
- `examples/aliases.json` — maps the alias `hallway` to the `roomcalendar`
  screen, see [Display aliases](#display-aliases).
- `examples/organizer_names.json` — example entries for `organizer_names_file`,
  used to extract an organizer's name from an event summary when the iCal feed
  has no `ORGANIZER` field.

Copy the ones you need into the matching `data/` subdirectory (see
[Development](development.md)); they are plain screen/schedule files, so they
also work as a starting point to edit in the management UI.
