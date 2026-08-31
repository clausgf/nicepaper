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
- **`RoomCalendar`** — shows whichever room the *device* rendering the screen
  is bound to (Displays, or the device's E-Paper/general card): its number,
  name and notes (multiline, under the date), and its booking system's iCal
  feed (recurring-event expansion, cached) with the current and next
  appointments plus a list of further ones. A card's color comes from the
  event's iCal `CATEGORIES` matched against the booking system's
  `category_colors` (Settings › Booking systems) — a picker restricted to
  the 6-color display's own colors (black, white, yellow, red, blue,
  green), since a booking system isn't tied to one panel. A screen whose
  panel can't show that exact color (e.g. `bw`/`bwr` have no blue/green)
  falls back to plain black rather than a nearest-color guess. Rendered
  with no room bound (e.g. a Templates preview)
  it shows placeholder room data instead of erroring. Since the widget
  carries no room data of its own, one screen can serve every room's door
  sign — see [Auto-generated Room Calendar templates](#auto-generated-room-calendar-templates)
  below.
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
  can be shown with the `Image` widget instead. The URL and token are project
  settings, the update interval/backoff/error text are global settings (see
  [Configuration](configuration.md)); as with weather,
  fetches back off on failure, the last-known value keeps being shown with the
  `homeassistant_stale_notice` marker, and the outage appears on the nice4iot
  Dashboard.
- **`WeatherNow`** / **`WeatherForecast`** / **`WeatherChart`** — current
  conditions, an hourly forecast strip, and one configurable bar/line chart.
  `WeatherNow` shows temperature, the condition, and wind (speed, direction as
  an 8-point compass, and gusts). Its text language follows `LOCALE` and the
  wind-speed unit follows `WIND_SPEED_UNIT` (see [Configuration](configuration.md)).
  In `WeatherChart`, `primary_metric` and `secondary_metric` each add a
  trace on their own Y axis (primary left, secondary right) — e.g.
  temperature + precipitation combined. Either can be left empty to omit
  its trace entirely (a chart with just one metric is the other one left
  unset); leaving both empty draws nothing. Available metrics are
  `temperature`, `precipitation`, `humidity`, `pressure` and `wind` (the
  wind series honours `WIND_SPEED_UNIT`). `line_style`
  (`solid`/`dashed`/`dotted`) sets `primary_metric`'s line style when it
  renders as a line (bar metrics, e.g. `precipitation`, ignore it);
  `secondary_metric` always stays dashed, to keep it visually distinct from
  the primary series even on a black/white/red panel. Each axis is titled
  with its metric name and unit above the plot (primary left, secondary
  right) — e.g. `Temperatur (°C)`, `Wind (km/h)` — in the `LOCALE`
  language, with a short sample of that trace's own style (line or bar)
  right next to the title, so the two traces stay distinguishable in the
  legend the same way they do in the plot. All three are backed by
  [Open-Meteo](https://open-meteo.com)
  (no API key needed; the DWD ICON model for German/European locations) and
  are placed by `latitude`/`longitude` — leave **both** empty to use the
  default location from the project settings (see
  [Configuration](configuration.md)). The fallback is all-or-nothing: filling
  in only one of the two keeps the other at 0 rather than completing it from
  the project setting, which would put the widget somewhere neither setting
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
| `Name` | the screen's file name and its id in `/api/screen/<id>/…`; editing it renames the file (editor only, not a field of the screen JSON) |
| `width`, `height` | canvas size in pixels |
| `palette_id` | id of the palette the image is quantized to before it is served (`bw`, `bwr`, `bwy`, `gs4`, `c7`, `e6`). Empty serves the unquantized RGB image. |
| `color_background`, `color_primary`, `color_accent` | this screen's colors; each empty field falls back to the global default (see [Configuration](configuration.md)) |
| `panel_type_id` | which panel type was applied last, see below |

`/api/screen/<id>/image.png` serves the image quantized to that screen's
`palette_id`, so the display needs no palette knowledge of its own and can't
ask for the wrong one — it is also exactly what the editor's preview
shows. `?raw=true` returns the unquantized RGB render the quantization started
from, for debugging a color that dithers; a display never needs it.
`?boxes=true` renders the screen with every widget outlined — see
[Clipping and debug outline](#clipping-and-debug-outline). Both are editor
views; neither touches the cached image.

When `<id>` is a device's own name (resolved via its binding, see
[Display bindings](#display-bindings)), a real `200 OK` response (not a
`304`) is also remembered as that device's "last delivered" snapshot — the
exact PNG bytes plus when, served back unchanged at
`/api/screen/<id>/last_delivered.png` (404 before the device has ever
fetched). This is what the simplified UI's Display Detail shows next to the
live preview, so a device that stopped polling or missed an update is
visible there, not just assumed from its online status.

The preview is framed by a pixel ruler with labelled ticks on all four sides,
and moving the mouse over it shows the exact pixel under the cursor — widgets
are positioned by typing `position_x`/`position_y`, so the preview is only
useful if it can be read back as coordinates. Both are scale-independent: the
ruler is placed in percentages and the readout divides by the rendered size, so
they stay correct at whatever width the browser scales the image to. The frame
stops growing at 48rem — a preview is for judging the layout, not for reading
it at 1:1 — and scales down freely below that.

Individual widgets can override `color_primary`/`color_accent` for
themselves, each aspect falling back to the screen's color independently —
the same per-aspect override `font_name`/`font_size` use. In the widget
editor's Appearance section, both show as small, compact controls rather
than full-width fields: a font icon opens a dialog with a Font Name/Size
picker, and a color swatch opens a menu of the screen's palette colors
(`palette_id`, above) — so only colors the panel can actually display are
offered — with a "Default" entry to clear the override. A screen with no
palette set falls back to a plain, unrestricted color picker instead.

### Panel types

Instead of typing size, palette and colors by hand, pick a panel from the
**Panel type** list. It fills in all of the above — for a black/white panel it
also sets the accent to black, since red could only quantize to black there anyway.

Adding a screen offers the panel-type list up front, since size and palette are
the first decisions about a screen and every widget position depends on them.
The same list is in the screen's settings, so the panel can be picked or
changed later just as well.

**No preset** is the default, and a listed choice in both — for a panel that
isn't in the catalog, or when you'd rather set size, palette and colors
yourself. A new screen then starts blank at 800×480 (no palette, so it is
served as RGB, and the global colors apply); picking it for an existing screen
only drops the `panel_type_id` record and leaves its values untouched.

A preset is a **template, applied once**: after that the screen's own fields are
what renders, they stay editable, and a preset that is later changed or removed
never alters an existing screen. `panel_type_id` only records which one was used
— and stops recording it the moment you edit past it: editing width, height,
palette or any of the three colors directly clears `panel_type_id` back to
"No preset", since the screen no longer actually matches what that panel type
describes.

`Screen.panel_label` (used wherever a screen needs a one-line description of
its panel, e.g. a future screen list) reflects this: with a resolved
`panel_type_id` it shows that panel's own name and manufacturer designation
(`panel_id`); otherwise a plain `"{width}x{height} {palette_id} {n}-color"`
summary of the screen's own fields.

The catalog ships with the package (currently Waveshare 7.5"/7.3" and two
Seeed 7.3"/7.5" panels) and is extended per data root by an optional
`data/panel_types.json` (`<project>/.epaper/panel_types.json` in extension mode).
Entries are merged by `id`, the root file wins, so it can both add panels that
aren't shipped and correct one that is:

```json
[
  {
    "id": "my-panel", "name": "My 5.83\" panel", "vendor": "Waveshare",
    "width": 648, "height": 480, "palette_id": "bw",
    "color_background": "#ffffff", "color_primary": "#000000", "color_accent": "#000000",
    "panel_id": "GDEW0583T7"
  }
]
```

`panel_id` — the panel's own official designation from its manufacturer's
datasheet, e.g. `GDEH075Z9` (not a GxEPD2 class name, and not this entry's own
`id`, which is a vendor+size slug) — is informational only; nicepaper renders
a PNG and never talks to a panel driver. It is shown under the panel-type list
so a panel can be found by the name its datasheet or firmware knows it under.
The same physical panel is often sold under different vendor names (e.g.
Waveshare and Seeed both rebrand Good Display panels) — those get separate
catalog entries (different `id`, different `vendor`/`name`) that share the
same `panel_id`.

Palettes work the same way: an optional `data/palettes.json` adds to (or
overrides) the shipped ones. Unlike `panel_types.json`, editing it changes what
gets served — a screen references a palette by id rather than containing it —
so a change there re-renders every screen using it.

### Auto-generated Room Calendar templates

For every distinct `(width, height, palette_id)` combination in the
panel-type catalog, a screen is synthesized on demand — a full-canvas
`RoomCalendar` widget, sized and paletted for that panel, id
`__roomcalendar_<width>x<height>_<palette_id>` (e.g.
`__roomcalendar_800x480_bw`). Not a file in `data/screens/` — built fresh
from `panel_types.json` every time it's requested, so it can never drift out
of sync with the catalog. The simplified UI's Templates section lists these
alongside real screens (read-only preview only); a device can be pointed at
one directly, the same as any other screen id, and will show whichever room
it is bound to. Since a template is shared across every device that
resolution/palette applies to, `/…/screens/<id>/image.png` renders and
caches differently for each requesting device (by its device binding's
`room_id`) rather than once for the id alone.

## Display bindings

An optional `data/device_bindings.json` file maps a display's name to the
screen it renders, the room it hangs in, and (optionally) its actual panel
type, e.g. `{"hallway": {"screen_id": "epaper_43bw", "room_id": "a-101",
"panel_type_id": "waveshare_7in5_v2"}}`. A display can then be addressed by
a stable name instead of the screen file name, and several displays can
share one screen. `panel_type_id` only restricts which screens the
management UI's Screen select offers (matching resolution/palette) — it is
never checked against `screen_id` at render time, so a mismatch set some
other way still renders. (In nice4iot extension mode, assigning a screen,
room or panel type to a device writes this file automatically — see
[Architecture](architecture.md).)

An older `data/aliases.json` (the bare `{"hallway": "epaper_43bw"}` format) is
migrated to `device_bindings.json` automatically on first use.

## Update schedules

A schedule file in `data/schedules/` is a plain JSON list of weekly rules
(weekdays, months, times of day) that determine when a screen expires and is
re-rendered. Screens reference one by `update_schedule_id` (default:
`"default"`, so most setups need a `default.json`). The management UI edits a
schedule as one card per weekly rule with weekday checkboxes ("Only on these
weekdays"), a month multiselect ("Only in these months"), and time chips; a
"+" next to the times adds every time in a range (start, end, interval —
every 5/15/30 minutes, hour, or two hours) in one go instead of one chip at a
time. The simplified UI has the same editor, under Preferences > Schedule,
fixed to `default.json` — since screens default to it, that's the one
schedule that governs every display unless a screen overrides it.

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
  `RoomCalendar` widget (or use one of the auto-generated templates instead —
  see [Auto-generated Room Calendar templates](#auto-generated-room-calendar-templates)).
  Bind a device to it and assign that device a room with a booking system to
  see it render.
- `examples/screens/weather.json` — all three `Weather*` widgets (current
  conditions, forecast strip, and a combined temperature+precipitation chart)
  for Berlin; adjust `latitude`/`longitude` for your location.
- `examples/screens/homeassistant.json` — `HomeAssistant` widgets as arc and bar
  gauges plus text values (an attribute of a `climate` entity and a
  `binary_sensor`). Replace the entity ids with your own and configure the
  Home Assistant URL/token first.
- `examples/device_bindings.json` — binds the display name `hallway` to the
  `roomcalendar` screen, see [Display bindings](#display-bindings).
- `examples/organizer_names.json` — example entries for `organizer_names_file`,
  used to extract an organizer's name from an event summary when the iCal feed
  has no `ORGANIZER` field. Also editable in the simplified UI, under
  Preferences > Organizer names.

Copy the ones you need into the matching `data/` subdirectory (see
[Development](development.md)); they are plain screen/schedule files, so they
also work as a starting point to edit in the management UI.
