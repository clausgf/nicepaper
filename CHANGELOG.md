# Changelog

## Unreleased

### Added

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
