# nice4iot extension-interface wishlist

[← Documentation](README.md)

Things the E-Paper extension needs from nice4iot that its extension interface
(`app.extensions`) does not expose yet. Until they exist, the extension reaches
into nice4iot internals in-process (and degrades to empty outside nice4iot);
each item below says what it currently does instead.

## Devices

- **List a project's devices.** The displays grid (simplified UI) needs to
  enumerate a project's devices by name. There is no sanctioned getter; it
  calls `app.core.device.backend.get_devices(project)` directly (returns `[]`
  outside nice4iot). — *Wanted:* `app.extensions.get_devices(project)` (name +
  the fields below), so extensions stop importing device internals.
- **Online state / last seen.** The grid's "Online" column derives online from
  `Device.last_seen_at` + a threshold, computed in the extension
  (`display/backend._is_online`). — *Wanted:* a documented online/last-seen
  accessor (or `is_device_online` promoted to the extension API).
- **Latest device telemetry: RSSI and battery.** The grid has RSSI and Battery
  columns but **no data source**: `wifi_rssi`/`battery_V` are push-only
  telemetry (Prometheus/Influx), not stored readably per device (`DeviceRuntime`
  holds only `last_seen_at`/`firmware_*`). The columns stay empty. — *Wanted:*
  nice4iot records the last-reported `wifi_rssi`/`battery_V` in the runtime
  sidecar (like `last_seen_at`) and exposes them per device.
- **Per-device alarm count.** The grid has an "Alarms" column with no source
  yet. — *Wanted:* a per-device active-alarm count via the extension API.

## Done

- **User menu** — `app.extensions.render_user_menu()` now lets an extension's
  own page chrome host nice4iot's standard user menu.
- **Deep-linkable extension sub-paths** — nice4iot now routes an extension
  page's whole subtree to `render_fn`, not just its exact base URL (see its
  `docs/extensions.md`, "Deep links within a standalone page"), so the
  simplified UI builds its own nested `ui.sub_pages` for real, bookmarkable
  section URLs (`ui/simplified_ui/layout.py`) — see
  [simplified-ui.md](simplified-ui.md#navigation). At the time this was
  built, the nice4iot-side change was still unreleased (uncommitted in the
  nice4iot working tree); re-check against a released nice4iot before relying
  on this in production.
