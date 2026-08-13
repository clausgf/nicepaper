# Changelog

## Unreleased

## 0.15.2 — 2026-08-13

### Fixed

- **The global settings card came up empty**, in nice4iot's E-Paper card and in
  the standalone Global tab alike. `global_config_fields()` still excluded
  `epaper_color_models`, which 0.15.0 removed from `GlobalConfig`, and
  `ModelForm` rejects an unknown field name with a `ValueError` — so building
  the form raised before it rendered anything. The card is now built without an
  exclude list, and a test renders it and checks every `GlobalConfig` field has
  a widget.

### Changed

- niceview 0.14.1 → 0.16.0. Two things follow from it:
  - `DrillDownWrapper`'s `on_add` is awaitable (0.15.0). The new-screen dialog
    is now awaited inside the Add click like any other dialog, so
    `panels.directory_drilldown()`'s `confirm_add` hook changed shape: it is an
    `async` callable returning whether to go ahead, instead of one that was
    handed a `create` callback to invoke itself. That detour only existed
    because the coroutine used to be dropped unawaited.
  - The Screens and Schedules title rows look slightly different (0.16.0): the
    buttons are joined in a button group at the right edge and carry tooltips.
    That comes from niceview's new shared chrome style; nicepaper does not set
    one of its own. `set_chrome_style()` is application-wide, and as a
    nice4iot extension nicepaper shares that application — and the per-widget
    `chrome_style=` would not help either, since the file lists render their
    own rows (computed mtime/size caption, conditional warning icon) rather
    than niceview's.
- Screen-settings fields react through `ModelForm`'s own `on_change` (niceview
  passes the field name and its new value) instead of `element.on(
  'update:model-value', ...)`. This drops both raw listeners and with them the
  assumption that NiceGUI's internal listener runs before ours — and the
  `GenericEventArguments` vs `ValueChangeEventArguments` confusion that broke
  preset selection in 0.15.0.

## 0.15.1 — 2026-08-12

### Fixed

- Picking a display preset in the screen settings did nothing: the select's
  handler read `e.value` off the `GenericEventArguments` that an `.on()`
  handler receives, which carries the raw payload in `.args` and has no
  `.value`. The resulting `AttributeError` was caught and logged server-side,
  so the browser showed no error and the fields below simply stayed as they
  were. The handler now takes the new id from the element itself, and a
  regression test drives the actual select rather than only the function
  behind it — which was green throughout.

## 0.15.0 — 2026-08-12

### Added

- **Display presets.** A screen can be set up by picking a panel from a
  searchable **Display** list in its settings instead of typing size, palette
  and colors by hand. The catalog ships with the package
  (`extensions/epaper/resources/displays.json`: Waveshare 4.2", 7.5" b/w and
  b/w/r, 7.3" ACeP and Spectra 6, Seeed XIAO 7.5") and is extended per data
  root by an optional `data/displays.json`, merged by `id` with the root file
  winning. Each entry carries `width`/`height`, `color_model`, the three colors
  and an informational `gxepd2_class` (shown as a hint below the list; nothing
  reads it at render time). A preset is a template applied once — the screen's
  own fields stay the source of truth, so editing or removing a preset never
  changes an existing screen. `ScreenModel.display_id` only records which one
  was applied last.
- Adding a screen now offers to pick the display it is for, and the new screen
  starts from that preset. Both display lists offer **No preset** as an
  explicit choice, and it is the default: a new screen starts blank at 800x480
  exactly as before unless a panel is picked, and picking "No preset" for an
  existing screen only drops the `display_id` record without touching its
  values. `panels.directory_drilldown()` gained an optional `confirm_add` hook
  for the dialog; the schedules list passes none and keeps creating files
  straight away.
- New `bwy` palette (black/yellow on white), matching the B/W+Y panels
  OpenDisplay lists.
- New global settings `latitude`/`longitude` (default 52.52 / 13.405): the
  default forecast location for every `Weather*` widget that sets none of its
  own. `WeatherWidgetModel.latitude`/`longitude` therefore became **optional**
  — leaving both empty (or 0, which is what a cleared number field stores)
  uses the default. The fallback is all-or-nothing: setting only one
  coordinate keeps the other at 0 instead of completing it from the global
  setting. One consequence: the exact point 0/0 can no longer be addressed.
  New weather widgets are created without coordinates and so follow the
  default, rather than starting at 0/0 in the Atlantic as they used to.
- New `ScreenModel` fields `color_model`, `color_background`, `color_primary`
  and `color_accent`: a screen is bound to one panel, so its palette and colors
  are screen settings. Each is optional and falls back to the global default.
- New `WidgetModel` fields `color_primary` and `color_accent`, each falling
  back to the screen's color independently (the same per-aspect override
  `font_name`/`font_size` use). Not in the editor form yet — see
  [docs/development.md](docs/development.md).
- Palettes can be added or overridden per data root through an optional
  `data/color_models.json`. Editing it re-renders every screen using it (a
  screen references a palette by id rather than containing it).

### Removed

- **`WidgetModel.show_bounding_box`.** Outlines are now a preview-only view
  (the toggle above), so the flag no longer has a job: its only effect was to
  bake an outline into the image a display fetches. An existing screen file
  that still contains the key loads fine — it is ignored — and drops it on the
  next save. A screen that relied on it to draw a permanent frame around a
  widget has to draw that frame itself.

### Changed

- **Every `alignment` now defaults to `lt` instead of `lb`** — `Text`, `Date`
  and `HomeAssistant`. With `b` and no size, text is drawn *above*
  `position_y`, so the number being edited pointed at the bottom of the text
  rather than its top. **This moves existing text**: screen files do not store
  the default, so any such widget without an explicit `alignment` renders
  differently after the update — vertically offset by its own text height when
  auto-sized, or top- instead of bottom-aligned inside its box. Set
  `"alignment": "lb"` explicitly to keep the old placement. The default,
  pattern and description now live in one shared `_AlignmentField`, so the
  three can't drift apart again.
- **The `color_model` query parameter is gone.** `/api/screen/<id>/image.png`
  now serves the image quantized to the palette configured *on the screen*, so
  a display needs no palette knowledge of its own and can't request the wrong
  one. A screen without a `color_model` is served unquantized as before.
  Displays that passed `?color_model=` must have the palette set on their
  screen instead — the parameter is now ignored.
- The editor's Image Preview is a single image instead of one tab per palette:
  a screen has one palette now, so there is only one image a display would get.
  It is framed by a pixel ruler (thin border, labelled ticks on all four sides)
  and shows the pixel under the mouse pointer, so a position seen in the
  preview can be read off and typed into `position_x`/`position_y`. Ticks use
  round 1/2/5 x 10^k steps and are placed in percentages, so they stay correct
  however the browser scales the image; the readout is client-side only, so
  moving the mouse sends nothing to the server.
- New `?raw=true` parameter returns the unquantized RGB render, for debugging a
  color that dithers. A display never needs it.
- New outline toggle in the preview's toolbar (which now lets the URL take the
  remaining width): it outlines every widget at once. Backed by a new
  `?boxes=true` parameter that renders on demand and is returned with
  `Cache-Control: no-store` and no `ETag`, so the outlines can never reach a
  display or the cached image. A widget that sizes itself gets its anchor
  marked with a small corner, since it has no box to outline.
- The `ETag` is now the hash of the image that is actually served (plus the
  palette it was quantized with) instead of the hash of the RGB render. Two
  clients on different palettes used to receive the same `ETag` for different
  bytes, and a palette edited in place kept its old `ETag`.
- `epaper_color_models` was removed from `GlobalConfig` and the palettes moved
  to `extensions/epaper/resources/color_models.json`. `load_global_config()`
  copies persisted fields over the model defaults, so a catalog kept in that
  file froze at whatever an installation wrote once and never picked up
  palettes added in a later release. An existing `global_config.json` that
  still has the key loads fine and drops it on the next save.
- `GlobalConfig`'s three colors are now the *defaults*, applied where a screen
  (and within it, a widget) sets none.
- `ColorModel` moved from `extensions.epaper.models.global_config` to
  `extensions.epaper.models.display`, next to the new `DisplayModel`.
  `extensions.epaper.config` re-exports it as before.
- `Screen.get_image()`/`get_image_path()` take `raw: bool` instead of a
  `color_model`; `Screen.update_if_needed()` takes no argument. `ImageCache`
  now builds the metadata (including the version) in `put_data()`, since it
  owns which of the two images gets served.
- [SECURITY.md](SECURITY.md) documents how to serve `image.png` over plain HTTP
  to displays whose firmware can't do TLS: a second, LAN-restricted listener in
  the reverse proxy (validated Caddy configuration included) rather than a
  second listener inside nicepaper, plus what that does and does not protect.

## 0.14.0 — 2026-08-07

### Added

- New `HomeAssistant` widget: shows one Home Assistant entity's state — or one
  of its attributes (`attribute`) — as a line of text or as a gauge
  (`display`). `label`/`unit` default to the entity's `friendly_name`/
  `unit_of_measurement`, `decimals` rounds numeric values, `show_label` toggles
  the label. Gauges are drawn locally with Pillow (new
  `extensions/epaper/core/gauge.py`) as a 240° dial or a horizontal bar
  (`gauge_style`) on the `min_value` … `max_value` scale; out-of-range values
  are clamped and non-numeric states (`on`, `unavailable`, …) leave the scale
  empty. Entity states are fetched through HA's REST API, cached per entity,
  and — like weather — back off exponentially on failure, keep showing the
  last-known value with a `homeassistant_stale_notice` marker, and surface the
  outage as a health line on the nice4iot Dashboard card.
- New global settings for it: `homeassistant_url`, `homeassistant_token`
  (a long-lived access token, masked in the card), plus
  `homeassistant_update_interval_s`, `homeassistant_retry_min_s`,
  `homeassistant_retry_max_s`, `homeassistant_error` and
  `homeassistant_stale_notice`. Empty URL/token disables the widget.
- `examples/screens/homeassistant.json` — arc/bar gauges and text values.

### Changed

- Updated niceview 0.10.0 → 0.14.1, which changes how every form behaves:
  - A field's model **description is now shown as a tooltip** (it used to fill
    the placeholder, i.e. it was effectively invisible). Fields whose value
    can't be guessed from the label — the two-letter `alignment` codes, the
    Babel/CLDR format patterns, the schedule times' timezone, the `{time}`
    placeholder of the stale-data notices — additionally carry a short
    permanent hint below the widget, since a tooltip needs a hover a touch
    device can't do.
  - **Required fields are marked with `*` and enforced in the form**, and an
    edited item is only committed once it validates as a whole. New widgets
    and new weekly schedule rules therefore start with non-empty placeholder
    values (`Text` → "Text", `RoomCalendar` → example room/URL,
    `HomeAssistant` → `sensor.example`, a new rule → 08:00); previously they
    started empty, which would now block every other edit in the same form
    until the empty field was filled in.
  - `wind_speed_unit`'s description no longer repeats where the *language*
    comes from — that belongs to `locale`.

### Fixed

- The global settings card now also exposes `weather_retry_min_s`,
  `weather_retry_max_s` and `weather_stale_notice`, which 0.13.0 added to the
  config file but never rendered — they were only editable by hand.
- The schedule editor states the timezone the wake times are in (the global
  `timezone` setting) instead of leaving it to be guessed.

## 0.13.1 — 2026-08-01

### Changed

- Updated niceview 0.9.1 → 0.10.0.

### Fixed

- Widget-list drag reordering works again. NiceGUI 3.15's sortable is a mixin
  (`make_sortable`), not a `ui.*` element, so its `nicegui-sortable` importmap
  entry was never registered eagerly and failed to resolve for the widget list
  (which is created dynamically after page load). We now import the sortable
  module at setup so the entry is in every page's importmap.

## 0.13.0 — 2026-07-24

### Added

- Weather fetches now back off on failure (exponential, `weather_retry_min_s` …
  `weather_retry_max_s`) instead of retrying on every render, and serve the
  last-known data during an outage (graceful degradation) with an "as of HH:MM"
  marker on `WeatherNow` (`weather_stale_notice`). The nice4iot project
  Dashboard's E-Paper card shows a per-location weather health line (fresh /
  stale / unavailable) with the last error and next retry in a tooltip.

### Changed

- Default message and label strings are now English (`weather_error`,
  `ical_error`, `image_error`, the room-calendar labels). Existing
  `global_config.json` files keep their configured values; only the built-in
  defaults changed. Set them in the global settings card for another language.
- Updated all locked dependencies (niceview 0.9.0 → 0.9.1, plus nicegui,
  fastapi, aiohttp, icalendar, ruff, …).

### Fixed

- Clearing a widget number field (e.g. `size_height`) after typing no longer
  leaves a stuck "Set width and height together …" validation error — fixed
  upstream in niceview 0.9.1 (a cleared `ui.number` now round-trips to empty
  instead of a stale value).

## 0.12.0 — 2026-07-23

### Added

- New `Image` widget: renders an image from a URL or a file in the project
  directory (`source_type`). Loaded once and cached by default, or re-fetched
  every render (`reload_each_time`); the editor has a *Reload now* button.
  Setting only width or only height scales keeping the aspect ratio, both scales
  to exactly that size, neither uses the natural size. On a load failure (fixed
  10 s timeout) it draws the configurable `image_error` message
  (global config, sensible default). No per-widget font.

## 0.11.0 — 2026-07-23

### Fixed

- Widget Appearance: overriding only the font name *or* only the font size now
  takes effect. Previously a font was all-or-nothing — a half-set font was
  silently dropped and the widget fell back to the full default font. Each
  aspect now falls back to the screen default independently, and both fields in
  the editor are clearable so either can be reverted on its own.

### Added

- `WeatherChart` now labels its Y axes above the plot with the metric name and
  unit — e.g. `Temperatur (°C)`, `Wind (km/h)` (primary left-aligned in the
  accent colour, secondary right-aligned), in the `locale` language. Wind's unit
  follows `wind_speed_unit`. The titles take a strip at the top, so the plot
  keeps its width.

## 0.10.0 — 2026-07-22

### Added

- `WeatherChart` gains a `wind` metric (hourly wind speed), selectable as the
  primary or secondary series like the existing temperature/precipitation/
  humidity/pressure metrics. The series is converted to the configured
  `wind_speed_unit`.
- `WeatherNow` now shows wind direction (localized 8-point compass) and gusts
  alongside the wind speed, and its description/wind text is localized: the
  language follows the existing `locale` setting (`de`/`en`, English fallback),
  covering the WMO descriptions, the `Wind`/`Gusts` labels and the compass
  points.
- New `wind_speed_unit` global-config field (`kmh`, `ms`, `mph`, `kn`) selecting
  the unit `WeatherNow` renders wind speed in. Open-Meteo is always fetched in
  km/h and converted locally, so changing the unit needs no refetch.
- Public-repository metadata: `LICENSE` (AGPL-3.0-or-later), `CONTRIBUTING.md`,
  `SECURITY.md`, a GitHub Actions CI workflow (ruff + pytest), and `license` /
  `license-files` / `authors` / `classifiers` fields in `pyproject.toml`.

### Changed

- A screen whose `update_schedule_id` points at a missing schedule file is now
  surfaced instead of failing silently: the screen editor shows the field as a
  dropdown of existing schedules with an inline warning for a dangling
  reference, the screen list marks such screens with a warning icon, and
  `get_schedule_by_id()` logs the dangling reference at `warning` level. An
  empty `update_schedule_id` (intentionally no schedule) stays silent.
- Widget editor: a half-set widget size (only width *or* only height) is now a
  validation error instead of being silently ignored — width and height only
  take effect together; leave both empty for automatic sizing.
- Widget list rows now show the type badge up front (after the icon), followed
  by the detail (coordinates for the weather widgets, plus the metric(s) for
  `WeatherChart`), with the delete button right-aligned.

### Changed (breaking)

- **Renamed the project from `epaper-nice` to `nicepaper`** and moved the
  repository from `gitlab.gwdg.de/epaper/epaper-nice` to
  [github.com/clausgf/nicepaper](https://github.com/clausgf/nicepaper).
  Consumers must update their dependency name and source URL, e.g. in
  nice4iot's `pyproject.toml`:

  ```toml
  [project.optional-dependencies]
  epaper = ["nicepaper"]          # was: epaper-nice

  [tool.uv.sources]
  nicepaper = { git = "https://github.com/clausgf/nicepaper.git" }
  ```

  and re-run `uv lock`.

  The **extension module path is unchanged**: the package still installs
  `extensions.epaper` and nice4iot's extra is still called `epaper`, so no
  imports, `register(app)` wiring or extension discovery are affected.

- Application title changed from "Epaper Doorsign Manager" to "Nicepaper"
  (FastAPI `info.title`, the standalone UI header and the README heading).
  The old name only described door signs, while the project also renders
  room calendars and weather screens.
