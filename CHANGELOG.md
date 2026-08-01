# Changelog

## Unreleased

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
