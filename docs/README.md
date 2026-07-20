# Documentation

[← Project README](../README.md)

## Using nicepaper

- **[Screens, widgets & schedules](screens.md)** — the JSON configuration
  formats: screens and their widgets (`Text`, `Date`, `RoomCalendar`,
  `Weather*`), color models, display aliases, and update schedules, with the
  ready-to-copy `examples/` files.
- **[Configuration](configuration.md)** — process-level settings (`Config` /
  environment variables): locale, timezone, update intervals, accent color.

## Running and deploying

- **[Development](development.md)** — install from source, run the standalone
  server, run the tests, regenerate the low-bandwidth codec.
- **[Standalone vs. nice4iot extension & architecture](architecture.md)** —
  the project layout and how the same code serves both the standalone dev
  server and the nice4iot extension.
- **[Security policy](../SECURITY.md)** — the intended security boundaries and
  how to report a vulnerability.

## Design notes

- **[LoRaWAN client-side rendering](design-lorawan.md)** — early design notes
  for sending compact widget *data* to battery/LoRaWAN displays that render
  locally, instead of a rasterized PNG.
