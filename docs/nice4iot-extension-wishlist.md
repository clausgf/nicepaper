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

## Done

- **Latest device telemetry: RSSI and battery** — nice4iot's `DeviceRuntime`
  now caches the last system-telemetry push's `wifi_rssi`/`battery_V` as its
  `rssi`/`battery_voltage` properties; `display/backend._device_runtime`
  reaches in via `app.core.device.backend.read_runtime` (still no sanctioned
  getter, so still an in-process reach-in, just no longer blocked on missing
  data).
- **Per-device alarm count** — `Device.active_alarms` (a live query against
  the alarm backend) is used directly; still no sanctioned extension-API
  accessor.
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
