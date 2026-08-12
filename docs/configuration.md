# Configuration

[← Documentation](README.md)

`GlobalConfig` (`extensions/epaper/models/global_config.py`) holds the settings
that are the same for every screen — defaults, locale, color models, the
default font/colors, update intervals, ... It is a plain pydantic model that is
**JSON-persisted** to `data/global_config.json` and edited through the global
settings card in the UI, *not* an environment-variable/`BaseSettings` config.
At startup `load_global_config()` loads that file in place (creating it with the
defaults if missing).

Edit these settings in the UI:

- **Standalone:** the **Global** tab → *E-Paper Global Settings*.
- **nice4iot:** the global **E-Paper** card.

or by editing `data/global_config.json` directly. Per-screen/per-widget settings
(size, position, per-widget font, ...) live in the screen/schedule JSON files
instead (see [Screens, widgets & schedules](screens.md)); `GlobalConfig` is only
for things that don't vary per screen.

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
- `wind_speed_unit` — unit `WeatherNow` and the `WeatherChart` wind series show
  wind speed/gusts in: `kmh` (default), `ms`, `mph` or `kn` (knots). Open-Meteo
  is always fetched in km/h and converted locally, so changing this takes effect
  without a refetch.
- `ical_update_interval_s`, `ical_max_days` — iCal feed polling/lookahead for
  the `RoomCalendar` widget.
- `latitude`, `longitude` — the default forecast location, used by every
  `Weather*` widget that sets no coordinates of its own (defaults to 52.52 /
  13.405, Berlin). Most installations show the same place on every screen, so
  this is usually the only place a location needs to be set. A widget
  overrides it by setting **both** of its own coordinates; see
  [Screens, widgets & schedules](screens.md).
- `weather_update_interval_s` — Open-Meteo polling interval for the `Weather*`
  widgets.
- `weather_retry_min_s`, `weather_retry_max_s` — after a failed Open-Meteo
  fetch, weather backs off starting at `weather_retry_min_s` and doubling per
  consecutive failure up to `weather_retry_max_s`, so an outage isn't hammered.
  During the backoff the last-known data is still shown (graceful degradation).
- `weather_stale_notice` — the `WeatherNow` marker shown while serving cached
  data during an outage; `{time}` is the last successful update. Empty to hide.
- `weather_error`, `ical_error`, `image_error`, `homeassistant_error` — messages
  drawn when weather / calendar / image / Home Assistant data can't be loaded.
  (All the default message/label strings are English; edit them here for another
  language.)
- `color_background`, `color_primary`, `color_accent` — the **default**
  background, text/drawing and accent color (accent defaults to red, the only
  accent the `bwr` palette has; it is used for the chart widgets' primary
  series and the gauge fill). A screen, and within a screen a single widget,
  can override each of them — see
  [Screens, widgets & schedules](screens.md#displays-palettes-and-colors).

## Home Assistant

The `HomeAssistant` widget (see [Screens, widgets & schedules](screens.md)) needs
two settings before it can show anything:

- `homeassistant_url` — base URL of the instance, e.g.
  `http://homeassistant.local:8123`. Empty (the default) disables the widget.
- `homeassistant_token` — a **long-lived access token**, created in Home
  Assistant under *your profile → Security → Long-lived access tokens*. It is
  sent as `Authorization: Bearer …` and is stored in plain text in the config
  file, so prefer a token belonging to a dedicated, least-privileged user — see
  [SECURITY.md](../SECURITY.md).

Optional:

- `homeassistant_update_interval_s` — how long a fetched state is reused before
  Home Assistant is asked again (default 300 s). Entity states are cached per
  entity, so several widgets showing the same entity cause one request.
- `homeassistant_retry_min_s`, `homeassistant_retry_max_s` — the same
  doubling backoff as weather, so an unreachable instance isn't hammered once
  per widget per render.
- `homeassistant_stale_notice` — marker shown while a cached value is served
  during an outage (`{time}` is the last successful update). Empty to hide.

No Home Assistant *add-on* or custom component is needed on the HA side; the
REST API is built in, and nicepaper only reads entity states.

## Display and palette catalogs

The panel presets and the e-paper palettes are **not** in `global_config.json`.
They ship with the package (`extensions/epaper/resources/displays.json`,
`color_models.json`), so an entry added in a new nicepaper release actually
reaches an existing installation — a catalog persisted in the config file would
freeze at whatever that file contained when it was first written. Each is
extended per data root by an optional file of the same name in the root
(`data/displays.json`, `data/color_models.json`), merged by `id` with the root
file winning. See
[Screens, widgets & schedules](screens.md#display-presets) for the format.

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
