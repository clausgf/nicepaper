# Configuration

[← Documentation](README.md)

`extensions/epaper/config.py`'s `Config` (a pydantic-settings `BaseSettings`)
holds settings that are the same for every screen/root — defaults, locale,
color models, the shared font/icon resource paths, ... This is *process*
configuration, not persisted anywhere: `app_config = Config()` is built once
at import time from its field defaults, optionally overridden by matching
environment variables (case-insensitive, e.g. `STORAGE_SECRET`), and there is
no `.env` file loading configured.

Per-screen/per-widget settings (size, position, fonts, ...) live in the
screen/schedule JSON files instead (see [Screens, widgets &
schedules](screens.md)) — `Config` is only for things that don't vary per
screen.

## Commonly overridden variables

- `STORAGE_SECRET` — secret for NiceGUI browser session storage.
- `LOCALE`, `TIMEZONE`, `DATE_FORMAT`, `TIME_FORMAT` — defaults used where a
  screen/widget doesn't set its own.
- `ICAL_UPDATE_INTERVAL_S`, `ICAL_MAX_DAYS` — iCal feed polling/lookahead for
  the `RoomCalendar` widget.
- `WEATHER_UPDATE_INTERVAL_S` — Open-Meteo polling interval for the `Weather*`
  widgets.
- `COLOR_ACCENT` — RGB color the chart widgets use for their primary data
  series (defaults to red, the only accent the `bwr` color model has).

See the `Config` class itself for the full list (every field is overridable
the same way); complex fields (`epaper_color_models`, tuples) need their
environment-variable value JSON-encoded, per pydantic-settings' rules.

## Authentication

There is no built-in authentication (the previous htpasswd/reverse-proxy
provider setup was removed — nice4iot integration, if pursued, handles auth on
its own). Put the UI behind an authenticating reverse proxy if it shouldn't be
reachable by anyone who can reach the host. See [SECURITY.md](../SECURITY.md)
for the full security model.
