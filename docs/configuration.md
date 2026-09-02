# Configuration

[← Documentation](README.md)

`GlobalConfig` (`extensions/epaper/global_config/models.py`) holds the settings
that are the same for every screen *and every project* — defaults, locale,
the default font, update intervals, ... It is a plain
pydantic model that is **JSON-persisted** to `data/global_config.json` and
edited through the global settings card in the UI, *not* an
environment-variable/`BaseSettings` config. At startup `load_global_config()`
(`global_config/backend.py`) loads that file into the shared `app_config`
singleton in place (creating it with the defaults if missing).

Edit these settings in the UI:

- **Standalone:** the **Global** tab → *E-Paper Global Settings*.
- **nice4iot:** the global **E-Paper** card.

or by editing `data/global_config.json` directly. Settings that instead
identify one *site* — the Home Assistant instance, the default weather
location — live in `ProjectConfig` instead (see
[Project settings](#project-settings) below), since different projects can be
different sites. Per-screen/per-widget settings (size, position, colors,
per-widget font, ...) live in the screen/schedule JSON files instead (see
[Screens, widgets & schedules](screens.md)); `GlobalConfig` is only for things
that don't vary per screen or per project.

## Commonly adjusted settings

Field names below are the `data/global_config.json` keys (the card shows the
same settings with humanized labels):

- `locale`, `timezone`, `date_format`, `time_format` — defaults used where a
  screen/widget doesn't set its own. `locale` additionally selects the language
  of the `WeatherNow` texts and `WeatherChart` axis titles (its first two
  letters, e.g. `de_DE.utf8` → German, otherwise English): the weather
  descriptions, the `Wind`/`Gusts` labels, the compass points and the metric
  titles.
- `font_name`, `font_size` — the default font for widgets that don't set their
  own. A widget may override either aspect on its own (see
  [Screens, widgets & schedules](screens.md)).
- `widget_error` — text drawn in a widget's own box in place of it, when that
  widget raises an unexpected error while rendering (a bug, not a datasource
  outage — those already degrade gracefully with their own `*_error`/
  `*_stale_notice` below). Keeps the rest of the screen rendering instead of
  the whole image failing.
- `wind_speed_unit` — unit `WeatherNow` and the `WeatherChart` wind series show
  wind speed/gusts in: `kmh` (default), `ms`, `mph` or `kn` (knots). Open-Meteo
  is always fetched in km/h and converted locally, so changing this takes effect
  without a refetch.
- `weather_update_interval_s` — Open-Meteo polling interval for the `Weather*`
  widgets.
- `weather_retry_min_s`, `weather_retry_max_s` — after a failed Open-Meteo
  fetch, weather backs off starting at `weather_retry_min_s` and doubling per
  consecutive failure up to `weather_retry_max_s`, so an outage isn't hammered.
  During the backoff the last-known data is still shown (graceful degradation).
- `weather_stale_notice` — the `WeatherNow` marker shown while serving cached
  data during an outage; `{time}` is the last successful update. Empty to hide.
- `weather_error`, `ical_error`, `image_error` — messages drawn when weather /
  calendar / image data can't be loaded (`homeassistant_error` is documented
  under Home Assistant below, it supports placeholders the others don't).
  (All the default message/label strings are English; edit them here for another
  language.)
- `ical_retry_min_s`, `ical_retry_max_s` — after a failed iCal fetch, the
  feed backs off the same way weather does (doubling per consecutive
  failure), showing the last-known events during the outage instead of
  hammering the feed on every render.
- `image_retry_min_s`, `image_retry_max_s` — the same backoff for a failed
  `Image` widget load. Only matters for a source that fails: a `cache_once`
  image that already loaded once is never retried, and a `reload_each_time`
  image is retried on every render only while it keeps working.

## Project settings

`ProjectConfig` (`extensions/epaper/project_config/models.py`) holds the
settings that identify one *site* rather than the whole installation: the
Home Assistant instance and the default weather location. It is per-project
(per data root), **JSON-persisted** to `project_config.json` next to
`screens/`, `rooms/`, etc., and read fresh on every access — there is no
shared singleton like `app_config`, since two projects can have different
values.

Edit these settings in the UI:

- **Standalone:** the **Settings** tab.
- **nice4iot:** the project's **Settings** tab.

or by editing `<project>/project_config.json` (`data/project_config.json`
standalone) directly. The file is optional — a project with none has every
field at its default.

- `latitude`, `longitude` — the default forecast location, used by every
  `Weather*` widget in this project that sets no coordinates of its own
  (defaults to 52.52 / 13.405, Berlin). A widget overrides it by setting
  **both** of its own coordinates; see
  [Screens, widgets & schedules](screens.md).
- `homeassistant_url` — base URL of the instance, e.g.
  `http://homeassistant.local:8123`. Empty (the default) disables the widget
  for this project.
- `homeassistant_token` — a **long-lived access token**, created in Home
  Assistant under *your profile → Security → Long-lived access tokens*. It is
  sent as `Authorization: Bearer …` and is stored in plain text in the config
  file, so prefer a token belonging to a dedicated, least-privileged user — see
  [SECURITY.md](../SECURITY.md).

## Home Assistant

The `HomeAssistant` widget (see [Screens, widgets & schedules](screens.md))
needs `homeassistant_url`/`homeassistant_token` (see
[Project settings](#project-settings) above) before it can show anything.
The rest of its settings stay in `GlobalConfig`, since they are operational
knobs rather than something that varies per site:

- `homeassistant_update_interval_s` — how long a fetched state is reused before
  Home Assistant is asked again (default 300 s). Entity states are cached per
  entity, so several widgets showing the same entity cause one request.
- `homeassistant_retry_min_s`, `homeassistant_retry_max_s` — the same
  doubling backoff as weather, so an unreachable instance isn't hammered once
  per widget per render.
- `homeassistant_stale_notice` — marker shown while a cached value is served
  during an outage (`{time}` is the last successful update). Empty to hide.
- `homeassistant_error` — text drawn when nothing at all is known about the
  entity; `{code}` is a short failure reason (`401`, `timeout`, `conn`, ...),
  `{entity_id}` the entity id. The full error (HTTP status, exception detail)
  goes to the log and the dashboard health tooltip instead — the widget box is
  too small for it.

No Home Assistant *add-on* or custom component is needed on the HA side; the
REST API is built in, and nicepaper only reads entity states.

## Panel-type and palette catalogs

The panel types and the e-paper palettes are **not** in `global_config.json`.
They ship with the package (`extensions/epaper/resources/panel_types.json`,
`palettes.json`), so an entry added in a new nicepaper release actually
reaches an existing installation — a catalog persisted in the config file would
freeze at whatever that file contained when it was first written. Each is
extended per data root by an optional file of the same name in the root
(`data/panel_types.json`, `data/palettes.json`), merged by `id` with the root
file winning. See
[Screens, widgets & schedules](screens.md#panel-types) for the format.

The palettes used to live here as `epaper_color_models`. An old config file that
still has that key loads fine — pydantic ignores it — and drops it on the next
save.

## Resource paths (environment variables)

The only settings taken from the environment are the package-resource
locations, resolved fresh on every start (`_ResourcePaths`, a
`pydantic-settings` `BaseSettings` in `config.py`): `FONT_PATH` and `ICON_PATH`
override where fonts/icons are loaded from, for advanced deployments. These are
deliberately not part of `GlobalConfig` (installation-specific derived paths,
not user settings).

## Authentication

There is no built-in authentication (the previous htpasswd/reverse-proxy
provider setup was removed — nice4iot integration, if pursued, handles auth on
its own). Put the UI behind an authenticating reverse proxy if it shouldn't be
reachable by anyone who can reach the host. See [SECURITY.md](../SECURITY.md)
for the full security model.

Displays whose firmware can't do TLS are served by exposing *only* the image
endpoint over plain HTTP in that same reverse proxy, restricted to the LAN the
displays are on — there is deliberately no second listener inside nicepaper for
this. A ready-to-adapt Caddy configuration is in
[SECURITY.md](../SECURITY.md#serving-display-images-over-plain-http).
