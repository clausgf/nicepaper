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
- `weather_update_interval_s` — Open-Meteo polling interval for the `Weather*`
  widgets.
- `image_error` — message the `Image` widget renders when its image can't be
  loaded within the fetch timeout.
- `color_background`, `color_primary`, `color_accent` — screen background,
  default text/drawing color, and the color the chart widgets use for their
  primary series (accent defaults to red, the only accent the `bwr` color model
  has).

`epaper_color_models` also lives in the file (and round-trips through it) but is
not exposed in the card — a nested list of palettes is beyond what the form can
render.

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
