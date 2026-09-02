# Changelog

## 0.35.0 — 2026-09-02

### Fixed

- **A device's "Last delivered" snapshot could be overwritten by the UI's own
  live preview** — the simplified UI's "Current" tab (`display/preview.py`)
  fetches through a device's own alias URL for correct room-aware rendering,
  which looked exactly like the device's real poll to the image endpoint (a
  real `200 OK` through the same device-bound id) — so merely opening a
  device's detail page could silently record *that* fetch as the device's
  latest delivery, making an offline/stale device show a fresh "Delivered
  just now". New `?preview=true` query flag opts a fetch out of snapshot
  recording; the Current tab now sends it.
- **One crashing widget no longer takes the whole screen down** — a widget
  raising while drawing (a bug, not a datasource outage — those already
  degrade gracefully) used to propagate to an unhandled 500 from the image
  endpoint. `Screen._create_image()` now catches per-widget, logs it, and
  draws the widget's own box with a new configurable `widget_error` text
  (Global Settings) instead, so every other widget still renders.
- **A device's room/screen binding could look identical to "never assigned"
  once the room/screen was deleted** — dangling bindings are kept visible on
  purpose (not silently rewritten), but the simplified UI's Displays views
  showed the same blank room label / bare screen id either way.
  `display.backend.display_rows()` now sets `room_label` to `"Room deleted
  ⚠"` and a new `screen_label` field to `"{id} ⚠"` when dangling, without
  touching the raw `screen_id` the Screen field itself reads/writes.
- **`RoomModel.booking_ical_url`'s field description said "added to the
  booking system's base URL"**, but the actual behavior (and
  `room/backend.py`'s own docstring) is a full override, not append. Fixed
  the description, relabeled the field "Booking System URL override" (was
  "iCal URL"), and clarified the hint.

### Added

- **Datasource health visibility in the simplified UI** — previously only
  nice4iot's Dashboard tab and standalone's Project tab showed
  weather/Home Assistant/iCal/image outages (`ui/cards.py`'s
  `dashboard_card()`); the simplified UI showed none of it. New
  `ui.cards.datasource_health_rows()` (refactored out of `dashboard_card()`,
  no behavior change there) now also renders on the Rooms landing view via
  `only_failing=True` — silent unless something is actually down.
- **A warning when a room/booking-system file fails to parse and is silently
  dropped from its list** — previously logged only, with zero in-app trace.
  New `ui.cards.unreadable_items_banner()` plus
  `room.backend.count_unreadable_rooms()` /
  `bookingsystem.backend.count_unreadable_booking_systems()`, wired into
  both UIs' Rooms/Booking systems lists. (Screens' own list is filename-based,
  not content-validated, so nothing is silently hidden there — no banner
  needed.)
- **nice4iot's own device card gets the Current/Last-delivered preview** the
  simplified UI's Displays views already had (`display/preview.py`'s
  `render_device_preview()`, reused verbatim) — previously only a plain
  read-only "Image URL" text field, no way to see what a device actually
  last fetched without leaving nice4iot.
- **"Rooms & Displays App" link** in nice4iot's "E-Paper" project-settings
  card (previously no link there at all) and standalone's Global tab (was
  labeled "Simplified UI", now the same user-facing name) — shared content
  via `ui.cards.simplified_ui_link_fields()`.
- **`register_extension_group('E-Paper', icon='tv')`** — nice4iot's
  project-sidebar group for Rooms/Screens/Schedules/Booking systems now
  shows "E-Paper" with a screen icon instead of the default bare-module-name
  fallback ("epaper", generic icon).
- Room detail's Occupancy tab is now the default (was Settings).

## 0.34.0 — 2026-09-02

### Added

- **Organizer names editor in the non-simplified UI** — previously only
  reachable from the simplified UI's Preferences (`organizer/simplified_ui.py`).
  New `organizer/ui.py`'s `organizer_names_fields()`/`organizer_names_card()`
  give it a home in nice4iot's Project Settings sidebar (its own "Organizer
  names" card next to "E-Paper", `register_project_card('settings', ...)`,
  foldable and expanded by default like every other settings section) and a
  second card on standalone's Settings page.

- **Room photos** — a room can now have one photo, shown on its detail page's
  Occupancy tab (bottom, below the status/upcoming list), Settings tab
  (with upload/remove), and Displays tab (below the room summary, above the
  device list). Stored as a plain file in the new `EpaperPaths.room_photo_dir`
  (`<room_id>.<ext>`, extension-owned, deliberately not the project directory
  the `Image` widget reads from) via new `room/photo.py`
  (`room_photo_path()`/`save_room_photo()`/`delete_room_photo()`), rendered
  capped to `height=192px`/`fit=cover` so it can't dominate a tab on a phone.
  Replaces `RoomModel.photo` (a free-text project-directory filename that
  nothing ever rendered), removed from the model and its Settings form layout.

## 0.33.0 — 2026-09-01

### Added

- **`image.png` endpoint takes a `force` query parameter** —
  `GET /screen/{id}/image.png?force=true` (and the nice4iot-extension
  equivalent) re-renders unconditionally instead of only when the config
  mtime or `expires_at` say it's due, updating the real cache so a display
  polling afterwards gets this render too. `Screen.update_if_needed()`
  gained a matching `force` parameter.

- **Panel-type selects show `panel_id` too** — every "Panel type" `ui.select`
  (screen editor, device Settings card, simplified UI's Displays and Room
  Displays tab) used to label options with the catalog entry's own `name`
  only, e.g. `Waveshare 7.5" V2/V3 (800x480 b/w)`, dropping `panel_id` (the
  manufacturer's own designation, e.g. `GDEW075T7`) entirely -- so two
  catalog entries for the same rebranded hardware looked unrelated. New
  `catalog.backend.panel_type_label()` builds `"{panel_id} {name}"`
  (falling back to plain `name` without one), used by all four call sites.

- **Room Displays tab's list rows show the configured panel, flagging a
  mismatch with what the firmware reports** — `RoomDisplayRow` gained
  `panel_label` (`"{panel_id} {name}"` via `catalog.backend.
  panel_type_label()`, or `"—"` without a panel type set), computed in
  `display.backend.display_rows()` and suffixed with a `⚠` when
  `panel_mismatch_hint()` has something to flag. `room/simplified_ui.py`'s
  `_displays_panel()` added it to the row subtitle -- plain text, no custom
  `render_list_item` needed.

- **Reload booking data on demand, bypassing the iCal cache** —
  `get_from_ical()`/`get_room_events()` gained a `force` parameter that
  skips the cache's freshness check and failure backoff. Two new entry
  points: a reload icon button on a room's Occupancy tab
  (`room/simplified_ui.py`), and a "Reload all rooms" button on a booking
  system's detail page (`bookingsystem/ui.py`) that re-fetches every room
  using that system at once.

### Fixed

- **Displays detail's "Current" preview now shows a genuinely fresh
  render** — `display/preview.py`'s `render_device_preview()` used to
  point the Current tab at a plain, unrefreshed `image.png` URL, so it
  could show a stale image (e.g. after a change a widget reads live but
  that doesn't touch the screen's config mtime, such as room data).
  It now requests `image.png?force=true&_t=<timestamp>` on every render,
  forcing a fresh server render and bypassing the browser cache — no
  polling or refresh button, since this is a one-shot "current state on
  page load" view, not a live-updating one like the screen editor's.

## 0.32.2 — 2026-09-01

### Changed

- **E-Paper dashboard card's telemetry age now matches nice4iot's device
  status card style** — "as of 18 min ago" became "as of 01.09.26 08:04:38
  (18min ago)". New `util.humanize_datetime_age()` deferred-imports
  nice4iot's own `app.util.render_datetime_age()` for parity (local
  timezone included), falling back to a UTC-based rendering outside
  nice4iot/in tests.

### Fixed

- **Panel type mismatch hint in the device Settings card now updates live**
  — changing the Panel type select in `devicebinding/ui.py`'s
  `device_config_card()` used to leave the "Firmware reports panel ..."
  hint showing the old (or no) mismatch until the page was reloaded, unlike
  the simplified UI's already-refreshable equivalent. The card's
  Panel type/Screen/Room selects and the hint are now wrapped in a local
  `@ui.refreshable` body that `on_panel_type_change` refreshes, mirroring
  `room/simplified_ui.py`'s pattern.

## 0.32.1 — 2026-08-31

### Added

- **Panel type reconciliation reaches the simplified UI** — the Displays
  detail (both `display/simplified_ui.py`'s project-wide list and
  `room/simplified_ui.py`'s per-room list) now has an editable Panel type
  select and the same firmware-mismatch hint the nice4iot cards show,
  instead of only restricting the Screen choices with no way to see or set
  the panel type itself. Changing it live-refreshes the Screen options.
  `RoomDisplayRow` gained `panel_type_id` (now the second editable field
  alongside `screen_id`), `reported_panel`/`reported_panels` (read-only,
  from telemetry). `panel_mismatch_hint()` moved from `devicebinding/ui.py`
  (renamed from `_panel_mismatch_hint`) to `display/backend.py` so both the
  nice4iot cards and the simplified UI can share it without a UI-to-UI
  import.

### Changed

- **`RoomDisplaysAdapter.update()` also persists `panel_type_id`**
  (previously only `screen_id`) -- safe because the adapter always receives
  the full row (read, then edited, then saved), never a partially
  reconstructed one.

## 0.32.0 — 2026-08-31

### Added

- **Device dashboard card** — a new `register_device_card('dashboard', ...)`
  card on nice4iot's device Dashboard tab, styled like its built-in Device
  status card's "System" snapshot section. Shows esp32paper's latest
  `kind='epaper'` telemetry push (`display/backend.py: device_epaper_telemetry()`,
  a new (metrics, labels, reported_at) accessor generalizing
  `device_epaper_labels()`): panel, supported panels, image status (colored
  negative when not 200/304), and its age. Also shows the same panel-type
  mismatch hint the Settings card has (`devicebinding/ui.py`'s
  `panel_mismatch_hint()`, factored out of `device_config_card()` so both
  cards share it).

## 0.31.0 — 2026-08-31

### Added

- **Firmware-reported panel reconciliation** — esp32paper reports its active/
  supported panel ids (`panel`/`panels`, matching `PanelTypeModel.panel_id`)
  on a `kind='epaper'` telemetry push. `register()` now calls nice4iot's
  `register_telemetry_cache_kind('epaper')` so the latest push is cached
  O(1)-readable in the device runtime sidecar (needs nice4iot with
  `app.extensions.register_telemetry_cache_kind`, unreleased as of this
  writing). New `display/backend.py: device_epaper_labels()` reads it
  ({} outside nice4iot, same degrade-to-empty pattern as `_device_runtime()`).
  The device settings card (`devicebinding/ui.py`) shows a warning when the
  selected panel type doesn't match what the firmware reports, or when none
  is selected but the catalog has (or lacks) a matching entry — informational
  only, nothing is changed automatically.

### Changed

- **`devicebinding.ui.device_config_card()` takes a new required
  `project_name` parameter** (between `paths` and `device_name`) to read the
  above. Both call sites (`extensions/epaper/__init__.py`,
  `ui/standalone.py`) updated; standalone passes `'standalone'`, matching
  the existing convention elsewhere in that module.
- **`resources/panel_types.json` corrected to match esp32paper's current
  panel ids** (`panel_id`, the manufacturer designation the firmware itself
  reports): `waveshare_7in5b_v2` was `GDEW075Z08`, now `GDEY075Z08`;
  `waveshare_7in3f` was `GDEY073D46` (colliding with `gooddisplay_7in3_acep`,
  a distinct panel/driver), now its own `ACeP730`.

## 0.30.0 — 2026-08-31

### Added

- **`GlobalConfig.wakeup_margin_s`** (default 15, General section) — added to
  a served image's `Cache-Control: max-age` on top of the time until its
  `expires_at` (e.g. a room calendar's next appointment start/end). Real
  device wakeups jitter around their intended time; biasing `max-age` later
  makes a display wake at or after the intended update time rather than
  before it, avoiding an early poll that finds the image still valid and has
  to sleep and retry.

### Changed

- Settings project card title changed from "Settings" to "E-Paper".

### Removed

- Unused `OpenSans-*-webfont.woff` font resources (not referenced anywhere;
  widgets use the Ubuntu/FontAwesome fonts).

## 0.29.1 — 2026-08-31

### Changed

- `extensions/epaper/__init__.py` now registers the Settings card and the
  device card as `register_project_card('settings', ...)`/
  `register_device_card('settings', ...)`, matching nice4iot's own rename
  of that `CardSection` value from `'general'` to `'settings'`. Needs
  nice4iot >= 0.37.10; the old `'general'` value raises `ValueError` on
  startup against that version.

## 0.29.0 — 2026-08-31

### Added

- **`Box` and `Line` widgets** — plain shapes for framing/dividing a layout,
  no external dependencies. `Box`: a rectangle with `color_primary`/
  `line_width` for the border (`line_width: 0` for none), `color_background`
  (with `init_background`) for the fill, and an optional `corner_radius` for
  rounded corners -- fill and border draw as one shape so a rounded box
  never gets a square-cornered fill peeking past the border.
  `size_width`/`size_height` are required (both, no auto-size). `Line`:
  draws from its position to position+size (`size_height` empty = horizontal,
  `size_width` empty = vertical, both set = diagonal), with `line_width` and
  `line_style` (`solid`/`dashed`/`dotted`).
- `examples/screens/simple.json` now also shows a `Box` frame and a `Line`
  divider.

### Changed

- **`WeatherChartWidgetModel.line_style` split into `line_style_primary` and
  `line_style_secondary`** — the secondary trace's line style used to be
  hardcoded to `dashed`; it's independently configurable now (still
  defaulting to `dashed`, so an existing screen renders unchanged). A screen
  file with the old `line_style` key silently loses that setting (falls back
  to `line_style_primary`'s default, `solid`) instead of erroring.
- **`HomeAssistantWidgetModel.display`/`gauge_style` merged into one field**:
  `display` is now `"value"` / `"arc"` / `"bar"` directly (was `"value"` /
  `"gauge"` + a separate `gauge_style: "arc"|"bar"`). A screen file using the
  old two-field form loses `gauge_style` silently (pydantic drops unknown
  keys) and falls back to the `arc` gauge if `display` was `"gauge"` --
  re-save the widget in the editor to pick the shape again.
- **`HomeAssistantWidgetModel.alignment` removed** — the `value` display
  always draws top-left now. A screen file with a custom `alignment` for a
  `HomeAssistant` widget loses it silently.
- `HomeAssistantWidgetModel.color_fill` is always editable in the Appearance
  row now, not only when `display` was `"gauge"`.
- `TextWidgetModel.text`/`HomeAssistantWidgetModel.entity_id` are no longer
  required -- both default (`"Text"`/`"sensor.example"`) so a screen file
  that omits them loads instead of failing validation.
- **`ScreenModel.palette_id` defaults to `"bw"`** (was `None`/unquantized) --
  a screen with no `palette_id` key is now served quantized, matching what
  the editor already showed by default. Set it to `""` (or an unknown id)
  for the old unquantized-RGB behavior. An explicit `null` now falls back to
  the default instead of failing to load (same fix as 0.28.1 gave
  `color_primary`/`color_background`).
- Widget list rows now lead with position/size -- `(x,y)`, or `(x,y,w,h)`
  once a fixed size is set -- before the type-specific summary.
  `WeatherForecast`/`WeatherChart` summaries now include `hours={forecast_hours}`.
  `HomeAssistant`'s summary no longer prints a literal `None` when no label
  is configured.
- Screen editor: drilling into a widget now only swaps the Widgets card;
  Screen Settings stays visible above it instead of being replaced too.
- `GlobalConfig`/`ProjectConfig` field labels unified to sentence case,
  matching niceview's own auto-generated labels; a field only carries an
  explicit `title` where auto-generation would get it wrong (branding like
  `iCal`, or a `homeassistant_*`/`roomcalendar_*` field name that can't be
  split into words) or would repeat its section heading.

## 0.28.1 — 2026-08-31

### Fixed

- **0.28.0 broke loading any screen file that had `color_primary`/
  `color_background` explicitly `null`** (from a screen saved before 0.28,
  where `null` meant "inherit from the screen/global default") -- both are
  concrete `str` fields now, and pydantic rejects `null` against a `str`
  field with a hard validation error instead of falling back to the
  field's default, unlike a genuinely *missing* key. The 0.28.0
  CHANGELOG entry claimed this would gracefully resolve to the default;
  it did not -- the whole screen file failed to parse. `WidgetModel`/
  `ScreenModel` now have a `field_validator(mode='before')` that treats an
  explicit `null` for these fields the same as the key being absent.

## 0.28.0 — 2026-08-31

### Changed

- Project Dashboard card: the iCal health row now lists before Weather
  (was Weather, HA, iCal, Image). No behavior change.
- **Screen/widget colors no longer go through a Widget → Screen → Global
  lookup chain — every screen and widget now carries its own concrete color
  fields with plain defaults, edited directly in the editor.**
  - `GlobalConfig` loses `color_background`/`color_primary`/`color_accent`
    entirely (nothing reads them any more).
  - `ScreenModel` keeps only `color_background: str = "#ffffff"` (the
    canvas's actual fill color, not a fallback tier) and drops
    `color_primary`/`color_accent`/`resolved_colors()`.
  - `WidgetModel` gains `color_background: str = "#ffffff"` (drawn behind
    the widget's own content, only when `init_background` is set) and turns
    `color_primary` into a concrete `str = "#000000"` (was `Optional[str] =
    None`, falling back to the screen). `resolved_colors()` is gone;
    `resolved_font()` is untouched, font still falls back to the
    screen/global default. `init_background`'s default flips from `True` to
    `False` ("transparent" — draws nothing behind the widget, letting the
    screen background or an earlier, overlapping widget show through), since
    there is no longer a screen-color fallback to make `True` a safe
    default on a non-white screen.
  - **`color_accent` is gone from the base `WidgetModel`** -- it only ever
    meant something to two widget types, so each now names its own color
    for what it's actually for: `WeatherChartWidgetModel.color_primary_series`/
    `color_secondary_series` (both default black, like most panels already
    render), and `HomeAssistantWidgetModel.color_fill` (the gauge's filled
    part, black by default). `core.charting.draw_chart()` and
    `core.gauge.draw_gauge()` take the corresponding colors as explicit
    `primary_color`/`secondary_color`/`fill_color` parameters instead of
    reading `ctx.color_accent`, which `DrawingContext` no longer has at all.
  - `PanelTypeModel` (the panel-type preset catalog) loses `color_primary`/
    `color_accent` for the same reason -- only `color_background` remains,
    applied to `ScreenModel.color_background`. A preset no longer sets a
    panel-appropriate accent automatically (e.g. red for `bwr`/`c7`/`e6`,
    black for `bw`); set `color_primary_series`/`color_secondary_series`/
    `color_fill` by hand on the few widgets that use them.
  - The compact color swatch in the widget editor (`ui/compact_fields.py`'s
    `compact_color_field()`) drops the "resolved value vs. inherited
    default, with a menu entry to clear back to it" machinery that only
    made sense for optional, fallback-based fields -- it now just shows and
    sets a concrete color.
  - **Breaking, no migration**: an old screen/panel-type file with
    `color_accent` (screen or panel-type level) loads fine (pydantic
    ignores unknown fields) but the value is gone -- re-set the equivalent
    per-widget field (`color_primary_series`/`color_secondary_series`/
    `color_fill`) by hand where it mattered. A widget's `color_primary:
    null` (meaning "inherit") now resolves to the field's own default
    (`#000000`) instead of the screen's color the next time the screen is
    read, since resolution no longer happens at all.

### Fixed

- **A clipped widget (`clipping: true`) with `init_background: false` now
  correctly shows what was already drawn underneath it** instead of always
  resetting to a flat background fill. `screen/backend.py`'s clipping path
  built its isolated sub-image with `Image.new(color=background)`
  regardless of the widget's own `init_background`, discarding whatever an
  earlier, overlapping widget had drawn at that position; a non-clipped
  widget never had this problem since it draws straight onto the shared,
  already-populated canvas. The sub-image is now seeded from a crop of the
  actual current canvas at the widget's box (padding any part that falls
  outside the canvas with the background color, since `Image.crop()` pads
  out-of-bounds pixels with black). `init_background: true` is unaffected
  and still resets the box as before.

## 0.27.0 — 2026-08-31

### Added

- **The project Dashboard card now shows iCal and Image datasource health
  too**, next to the existing weather/Home Assistant lines: one row per
  failing/stale calendar feed or image source (`ui/cards.py`'s
  `dashboard_card()` gained `ical_statuses`/`image_statuses` params). This
  needed both datasources to actually track fetch outcomes, which they
  didn't before:
  - **`core/datasources/ical.py`**: `get_from_ical()` now returns an
    `IcalStatus` (fail_count, exponential backoff via `retry_after`, last
    error, like weather/Home Assistant) instead of a bare list, and never
    raises -- a failing feed now shows its last-known events during an
    outage (graceful degradation) and backs off instead of being re-fetched
    on every single render, which is what it did before (no backoff
    existed at all). New `ical_retry_min_s`/`ical_retry_max_s` in
    `GlobalConfig`. `room/backend.py`'s `get_room_events()` adapts the new
    `IcalStatus` back to the raise-on-total-failure contract its own callers
    (the `RoomCalendar` widget, the simplified UI's Occupancy panel) already
    expected, so neither needed to change. New `read_all_ical_statuses()`.
  - **`core/datasources/image.py`**: `get_image()` keeps its existing
    `Optional[Image.Image]` return type, but now tracks fetch/decode
    failures the same way in a small JSON sidecar next to the cached bytes
    (`ImageStatus`), with the same backoff (new
    `image_retry_min_s`/`image_retry_max_s`) -- previously a broken
    `reload_each_time` source (or one that never loaded successfully) was
    retried on every render. New `read_all_image_statuses()`.
  - Standalone's own Project tab now also passes weather/Home Assistant
    statuses to `dashboard_card()`, which it never did (only the nice4iot
    project card did) -- fixed for consistency while touching this code.

### Changed

- **Home Assistant URL/token and the default weather location moved from
  `GlobalConfig` to a new per-project `ProjectConfig`** (`project_config/`):
  a project stands for one site (one building, one Home Assistant instance),
  so sharing one HA credential and one weather location across every project
  on a nice4iot install was a real limitation. `homeassistant_url`,
  `homeassistant_token`, `latitude` and `longitude` are removed from
  `GlobalConfig`; the update-interval/backoff/error-text settings around them
  stay global, since those are operational knobs, not site properties.
  `ProjectConfig` is persisted to `project_config.json` next to a project's
  `screens/`/`rooms/`/... (`EpaperPaths.project_config_file`), read fresh via
  `get_project_config(paths)` rather than cached in a singleton like
  `app_config`, since two projects can have different values. Edited via a
  new "Settings" tab (nice4iot project tab, standalone tab, and simplified-UI
  Preferences > Project settings). **Breaking, no migration**: an existing
  `global_config.json`/`.epaper_global_config.json` that still has these keys
  loads fine (pydantic ignores unknown fields) but drops them on the next
  save — re-enter the Home Assistant URL/token and the weather location under
  the new Settings tab after upgrading, matching how `epaper_color_models`
  was handled when it moved out of `GlobalConfig` (0.15.0).
- `core.datasources.homeassistant.get_entity()`/`is_configured()` take
  `url`/`token` as explicit arguments instead of reading `app_config`,
  matching how the weather datasource already takes `latitude`/`longitude`
  explicitly. `WidgetType.summary` (`ui/widget_types.py`) now takes
  `(widget, paths)` instead of just `(widget)`, since a weather widget's
  summary needs the project's default location.
- **Weather cache cleanup**: `read_all_weather_statuses()` now deletes cache
  files older than twice `weather_update_interval_s` before reading, so a
  location no widget uses anymore (e.g. after editing a screen's
  coordinates) doesn't linger on the project Dashboard forever.
- **Simplified UI: full-height layout.** `build_page()`'s content column and
  `ui.sub_pages` now stretch to `h-full` instead of shrinking to their
  content, and the Organizer names textarea grows to fill the remaining
  height (`flex-grow`) instead of a fixed size — both read better on a tall
  viewport.

## 0.26.12 — 2026-08-30

### Changed

- `ScreenModel` field order: `panel_type_id` now precedes `width`/`height`,
  matching the editor's field order. No behavior change.

## 0.26.11 — 2026-08-30

### Changed

- **Home Assistant fetch errors are classified** (`core/datasources/homeassistant.py`):
  exceptions from a states fetch are now turned into a short `error_code`
  (`401`, `timeout`, `conn`, `bad-resp`, ...) plus a detailed `error` message,
  instead of a bare `str(exception)` that was empty/unhelpful for timeouts and
  malformed responses. The log line now also includes the request URL.
  `EntityStatus` gained an `error_code` field.
- **`homeassistant_error` is now a template**: `{code}` (the new short failure
  reason) and `{entity_id}` can be used in the `HomeAssistant` widget's error
  text, so the screen shows *why* an entity failed (e.g. `HA error (401)`),
  not just a generic message. Default changed from `"Error fetching Home
  Assistant data"` to `"HA error ({code})"`.

## 0.26.10 — 2026-08-28

### Changed

- `niceview` bumped 0.26.5 → 0.27.0 (latest commit): `ModelGrid`/`ModelGridInlineEdit` no
  longer crash on a `timedelta` field and render `bool` columns as a real checkbox
  (`cellDataType='boolean'`) instead of the text `true`/`false` — relevant to
  `bookingsystem`'s `update_interval`/`max_days_ahead` (`timedelta`) and any `bool` column
  shown in a grid. `Meta.field_infos` and a new `Meta.default_profile` now also apply to
  `ModelGrid`/`ModelList`, not just `ModelForm`. No code changes needed on our side.

## 0.26.9 — 2026-08-27

### Changed

- **Booking system `header`/`category_colors` editors are now inline**
  (`bookingsystem/ui.py`): every row is a live input pair (Header/Value, or
  Category/color swatch) that autosaves on change, instead of a static list
  plus an "Add" dialog. Persist errors (`ConflictError`, `StorageError`)
  surface via `ui.notify` instead of raising.
- **Rooms grid swaps its `booking_ical_url` column for `notes`**
  (`room/ui.py`): the iCal URL isn't useful at a glance in the grid; the
  per-room notes text (also shown on the physical display) is.
- **Panel catalog drops the `waveshare_4in2` (400×300 b/w) entry**
  (`resources/panel_types.json`): no longer stocked/tracked. A screen still
  referencing it keeps working — `panel_type_id` degrades gracefully to a
  dangling reference, same as any removed/unknown preset.
- `niceview` bumped 0.26.5 (unchanged pin) → 0.26.5 (latest commit, docs-only
  `CLAUDE.md` fix — no functional change).

## 0.26.8 — 2026-08-27

### Changed

- **`PanelTypeModel.gxepd2_class` renamed to `panel_id`** (`catalog/models.py`,
  `resources/panel_types.json`): firmware is moving from GxEPD2 (Arduino
  library) class names (e.g. `GxEPD2_750c_Z08`) to the panel's own official
  manufacturer designation (e.g. `GDEH075Z9`) — this field tracks whatever a
  panel is identified by elsewhere, so its value convention changes with it,
  same purpose as before. `panel_id` is deliberately distinct from a catalog
  entry's own `id` (a vendor+size slug, one per vendor SKU): the same
  physical panel is often sold under different vendor names (Waveshare and
  Seeed both rebrand Good Display panels), so those get separate `id`s that
  now share one `panel_id` — already true for two pairs in the shipped
  catalog (`GDEW075T7`, `GDEP073E01`). Hard rename, no alias, matching this
  catalog's own established convention (see the `displays.json` →
  `panel_types.json` rename below). The 8 shipped entries' values are
  inferred from their previous GxEPD2 class names, not yet cross-checked
  against datasheets for every entry — worth a second look before relying on
  them for a specific order.

## 0.26.7 — 2026-08-27

### Added

- **Rooms list is now searchable**: the Rooms grid gained a free-text search box
  (filtering across all columns as you type), via `niceview` 0.26.4's new
  `EditGridWrapper(search=True)`.
- `niceview` bumped 0.26.3 → 0.26.5 (search box above, plus `ModelGrid`
  `html_fields` for icon/HTML cells — not used by nicepaper itself yet).

### Changed

- **Displays list status dot now reflects active/provisioning state, not just
  online/offline** (`display/simplified_ui.py`, `display/backend.py`,
  `display/models.py`): `RoomDisplayRow` gained `is_active`/
  `is_provisioning_approved`, and the status dot (front of each list item, and
  the detail view) is now one of four states — green "online" (active,
  provisioned, seen recently), orange "offline" (active, provisioned, not seen
  recently), purple "pending" (active, not yet provisioning-approved), or grey
  "inactive" — each with a tooltip, mirroring nice4iot's own project Devices
  grid status dot (`app/core/device/ui.py`, `app/core/device/backend.py`'s
  `device_status_key()`) for a consistent status vocabulary across both UIs.
- **Fixed the WiFi/battery icon visibly jumping left/right between rows**
  (`display/simplified_ui.py`): `_wifi_icon`/`_battery_icon` used names
  (`signal_wifi_zero_bar`/`four_bar`, word-form `battery_*_bar`) that turned
  out not to exist as ligatures in nicegui's bundled Material Icons font at
  all — confirmed by rendering every candidate against the actual font (a
  temporary debug overlay on a live page, screenshotted) rather than by
  further guessing. WiFi is now a 3-state icon (no-data / weak / good,
  `signal_wifi_off` / `signal_wifi_bad` / `wifi`) and battery uses the
  numeric `battery_N_bar` names — both confirmed to render, and to share
  consistent glyph bearings within their own group, in that same probe.

## 0.26.6 — 2026-08-26

### Fixed

- **A NaN/inf battery or RSSI reading silently broke the Displays list**: a
  non-finite `battery_voltage` crashed `_battery_icon`'s bar-index math
  (`int(nan)` raises `ValueError`), dropping just that row's battery icon
  (the WiFi icon rendered just before it stayed, matching the reported
  symptom of a display row with a WiFi icon but no battery icon); a
  non-finite `rssi` would have crashed `round()` in `display/backend.py`,
  taking out the *entire* list. `display_rows()` now treats a non-finite
  reading as no reading at all (`None`), same as a genuinely absent one.

### Added

- **Displays list: WiFi/battery icons now show a tooltip** with the exact
  RSSI (dBm) / battery voltage (V), matching the text already shown next to
  them in the Display detail view (`display/simplified_ui.py`, new
  `_rssi_text`/`_battery_text` helpers shared by both views).

### Changed

- **RoomCalendar widget: room notes render in a larger font** (16pt → 24pt,
  `core/widgets/roomcalendar.py`), for better readability on the panel.

## 0.26.5 — 2026-08-26

### Changed

- **Organizer names (Settings › Organizer names) are now edited directly**
  in a `w-full` textarea, saved on blur — no more read-only list plus a
  separate Edit dialog/button (`organizer/simplified_ui.py`).
- **Fixed a mislabeled panel-type preset**: `waveshare_7in3f` carried the
  Good Display ACeP board's GxEPD2 class (`GxEPD2_730c_GDEY073D46`) instead
  of Waveshare's own (`GxEPD2_730c_ACeP_730`). Corrected it and added a new
  `gooddisplay_7in3_acep` preset for the Good Display board
  (`resources/panel_types.json`).

### Added

- **Info-level logging for organizer-name extraction**
  (`core/datasources/ical.py`): logs how many organizer names were loaded
  from `organizer_names_file`, and per event whether an organizer came from
  the feed's own `ORGANIZER` field (extraction skipped), was matched from
  the summary, or matched nothing — to diagnose why a configured name isn't
  taking effect.

## 0.26.4 — 2026-08-26

### Added

- **Displays now show firmware version, RSSI, battery voltage and alarm
  count from real nice4iot data**, no longer stubbed to `None`:
  `display/backend.py`'s `_device_runtime` reads nice4iot's `DeviceRuntime`
  (its `rssi`/`battery_voltage` properties over the last system-telemetry
  push) and `alarm_count`/`firmware_version` come straight off the device
  object (`active_alarms`, `firmware_version`) — see the updated
  `docs/nice4iot-extension-wishlist.md`. The room's own Displays tab
  (`room/simplified_ui.py`) now also shows firmware version in each
  device row's subtitle, alongside the screen.

## 0.26.3 — 2026-08-26

### Changed

- **Rooms project tab grid (`room/ui.py`) now auto-sizes its columns and
  shows a focused set**: room number, name, type, capacity and booking
  system, instead of every `RoomModel` field. `room_number`/`room_name`/
  `room_type` get shorter table headers ("Number"/"Name"/"Type") via
  `niceview.Field(table_label=...)` in `room/models.py`.

## 0.26.2 — 2026-08-26

### Fixed

- **Simplified UI page content wasn't stretching to the full width of its
  column.** `layout.py`'s `ui.sub_pages(...)` didn't inherit the `w-full`
  of its parent `ui.column()`, leaving routed page content narrower than
  the header/sidebar area. Added `.classes('w-full')` directly to the
  `sub_pages` element.

## 0.26.1 — 2026-08-25

### Fixed

- **Top-level Displays list was missing its drill-down chevron.** Every
  other list in the app gets one for free from niceview's `ModelList`
  default row rendering, but `display/simplified_ui.py`'s Displays list
  uses a fully custom row (status dot + WiFi/battery icons) via
  `render_list_item`, which niceview never adds a chevron to on its own.
  Added by hand, matching niceview's own icon/style. (`render_list_container`
  is unrelated to this — it only wraps the rows in a styled `ui.list()`.)

## 0.26.0 — 2026-08-25

### Changed

- **Booking system category colors are now restricted to the 6-color
  display's own colors** (black, white, yellow, red, blue, green — the
  `e6` Spectra palette), in both UIs at once (`bookingsystem/ui.py` is
  already shared): the "Add category color" dialog offers those 6 swatches
  instead of an unrestricted color wheel, since a booking system isn't
  tied to one screen/panel and there's no single "closest" color that
  would suit every room using it.
- **A category color a panel can't show exactly now falls back to plain
  black**, not a nearest-Euclidean-distance guess (`core/widgets/roomcalendar.py`'s
  `_event_category_color()` — e.g. a `bw`/`bwr` panel has no blue/green).
  Previously a color like yellow could silently render as red on a `bwr`
  panel; it renders black now, matching what the new picker's own choices
  guarantee (an exact palette member, or an intentional fallback).

## 0.25.0 — 2026-08-25

### Added

- **Display Detail shows the rendered screen.** Both Display Detail views
  (a room's Displays tab and the top-level Displays list) now have
  Current/Last delivered tabs (`display/preview.py`'s new
  `render_device_preview()`): Current is a live preview of the screen as it
  renders right now; Last delivered is the actual PNG a real `200 OK`
  response (not a `304 Not Modified`) most recently served to that
  device's own alias URL, plus when, so a device that stopped polling or
  missed an update is visible here instead of only inferred from "Online".
- **New API route: `GET /screen/{id}/last_delivered.png`** (standalone) /
  `GET /{project_name}/screens/{id}/last_delivered.png` (extension), `id`
  being a device name. 404 until that device has fetched at least once.
  Every real 200 response to a device's own alias URL (not `?raw=true`, and
  only when `id` resolves through an actual device binding — a bare screen
  id, as the editor's own preview uses, is not recorded) now copies the
  served PNG plus a timestamp into a new per-device snapshot store
  (`devicebinding/snapshot.py`, `paths.device_snapshot_dir`).

## 0.24.0 — 2026-08-25

### Changed

- **`WeatherChart.primary_metric` can now be empty too**, like
  `secondary_metric` already could — either metric may be cleared in the
  editor (both fields are now `clearable`) to omit its trace entirely, so a
  single-metric chart is just the other one left unset. Clearing both draws
  nothing. `core/charting.py`'s `draw_chart()` no longer assumes a primary
  series always exists: a secondary-only chart now drives its own gridlines
  instead of crashing (previously `axis_range('primary')` on an empty
  series list would raise).

### Added

- **Chart axis titles carry a style swatch of their own trace** — a short
  line/bar sample drawn the same way (`line_style`, or a filled block for
  a bar metric) as the series it labels, next to the title text, so the
  primary and secondary traces stay visually distinguishable in the legend
  even on a black/white/red panel where color alone can't tell them apart
  (`core/charting.py`'s `_draw_style_swatch`).

## 0.23.0 — 2026-08-25

### Changed

- **Adapt to nice4iot's project-tab sidebar** (still unreleased in the
  nice4iot repo at the time of this change): nice4iot moved its project
  page's tab strip to a left sidebar and gave `register_project_tab` an
  optional `icon=` (Material icon name, default `'extension'`) for the
  sidebar row. `extensions/epaper/__init__.py`'s four project tabs (Rooms,
  Screens, Schedules, Booking systems) now pass fitting icons
  (`meeting_room`, `wallpaper`, `schedule`, `event`) instead of the
  generic default. `register_project_tab`'s `render_fn` signature and
  calling convention are unchanged, so this needed no other code changes.

## 0.22.0 — 2026-08-25

### Added

- **Compact color and font controls in the widget editor.** Every widget
  type except `Image` now exposes `color_primary`/`color_accent` (already
  model fields, never surfaced in the editor before) alongside
  `font_name`/`font_size`, all four as small square swatch/icon buttons
  instead of full-width rows (`ui/compact_fields.py`, new). The color swatch
  opens a menu restricted to the screen's own palette colors
  (`catalog.backend.get_palette`) — only colors the panel can actually
  display — plus a "Default" entry to clear the override; a screen with no
  palette set falls back to a plain, unrestricted color picker. The font
  icon opens a dialog with a Font Name select and a Size field.
- **`WeatherChart` widget: `line_style`** (`solid`/`dashed`/`dotted`,
  default `solid`) for the primary series when it renders as a line —
  `core/charting.py`'s `ChartSeries` gained the same field, and
  `_draw_polyline()` now takes a style instead of a bare dashed flag. The
  secondary series keeps its existing fixed dashed style.

## 0.21.0 — 2026-08-25

### Added

- **The simplified UI is now deep-linkable.** Every sidebar section (Rooms,
  Templates, Displays, and each Preferences submenu item) has its own
  bookmarkable URL — `/rooms`, `/templates`, `/displays`, `/settings/schedule`,
  `/settings/booking`, `/settings/global`, `/settings/organizer` (relative to
  the page's own base URL) — built with `nicegui.ui.sub_pages`
  (`ui/simplified_ui/layout.py`, rewritten from client-side state switching).
  `/rooms/{room_id}` opens a room's detail directly on load (one-directional:
  clicking a different room afterward doesn't change the URL, since
  niceview's `DrillDownWrapper` has no public hook for that). Needs a
  matching nice4iot change (routing an extension page's whole subtree to it,
  not just its exact base URL) that was still unreleased at the time this was
  built — see `docs/nice4iot-extension-wishlist.md`.
- `nicegui` dependency now pinned to `>=2.22.0` (`ui.sub_pages`/`PageArguments`).

## 0.20.0 — 2026-08-25

### Added

- **Booking systems as a nice4iot project tab.** `bookingsystem/ui.py` (new)
  hosts the list/detail/header-editor/category-color-editor UI, registered
  via `register_project_tab('Booking systems', ...)` and the standalone
  `/booking-systems` route; `bookingsystem/simplified_ui.py`'s Preferences >
  Booking systems view now just wraps the same `booking_systems_wrapper()`.
- **Preferences > Global settings** in the simplified UI
  (`global_config/simplified_ui.py`): the same fields as nice4iot's "E-Paper"
  global settings card, embedded for convenience. The setting is still
  project-independent — editing it here changes it for every project.
- **Preferences > Organizer names** in the simplified UI
  (`organizer/simplified_ui.py`, `organizer/backend.py`): `organizer_names_file`
  (previously admin-only, hand-placed on disk) is now readable and editable
  from the UI — a list plus an Edit dialog (one name per line).
- **`GlobalConfig.date_format`/`time_format`/`roomcalendar_date_format_long`/
  `roomcalendar_date_format_short`/`roomcalendar_time_format`** are now
  `ui.select` with a curated list of common CLDR date/time patterns
  (`global_config/ui.py`), still editable to any custom pattern
  (`with_input=True`).

### Removed

- **`GlobalConfig.ical_update_interval_s`/`ical_max_days`** — dead since
  0.19.0 made `RoomCalendar` room-driven (it now always gets
  `update_interval`/`max_days_ahead` from the room's `BookingSystemModel`);
  no code read the global settings anymore.

## 0.19.0 — 2026-08-22

### Added

- **Room Occupancy in the simplified UI.** The room detail's Occupancy tab
  (`room/simplified_ui.py`) is no longer a placeholder: a status card (Free,
  or Occupied with an "until" time and, below, when the next meeting today
  starts) plus an Upcoming list of every event, both from the room's booking
  system's iCal feed (`room/backend.py`'s new `get_room_events()` — a room's
  `booking_ical_url`, if set, else the booking system's own `url`). Shows a
  plain message instead of a card when the room has no booking system
  configured, or the configured one has no URL.
- **The iCal datasource is now compatible with a `BookingSystemModel`'s own
  config**, not just a raw URL: `core/datasources/ical.py`'s `get_from_ical()`
  takes `update_interval_s`/`max_days` as parameters (was read from the
  global `ical_update_interval_s`/`ical_max_days` settings) plus optional
  `username`/`password` (HTTP Basic Auth) and `headers`. The `RoomCalendar`
  widget now goes through this too, via the room it renders — see below.
- **Booking system detail: HTTP headers are now a proper list editor**, not a
  JSON textarea — a two-column list (header, value) with a delete icon per
  row, and an "Add" button matching DrillDownWrapper's own toolbar style
  (dense round). `bookingsystem/simplified_ui.py`'s `_header_editor`.
- **Booking system: category → color mapping**, for `RoomCalendar` card
  colors. `BookingSystemModel.category_colors` (`Dict[str, str]`, an iCal
  `CATEGORIES` entry → a hex color), edited the same way as `header` — a
  swatch list with a delete icon per row and an Add dialog with a color
  picker (`bookingsystem/simplified_ui.py`'s `_category_color_editor`).
- **`RoomCalendar` is now room-driven, not hand-typed per screen.** The
  widget renders whichever room the requesting *device* is bound to
  (`DrawingContext.room`, resolved from the device binding by
  `screen/backend.py`'s render pipeline) instead of fixed
  `room_number`/`room_name`/`ical_url` fields on the widget itself — so one
  screen can serve every room's door sign. Room number/name and the
  calendar (via `room/backend.py`'s `get_room_events()`) come from the
  device's bound `RoomModel`; the room's `notes` (multiline) are drawn under
  the date. A card's color comes from the event's iCal `CATEGORIES` matched
  against its booking system's `category_colors`, snapped to the nearest
  color in the screen's palette (`catalog/backend.py`'s
  `nearest_palette_color()`, excluding white) so it renders as a flat,
  undithered color rather than whatever the final whole-image quantize
  would make of an arbitrary hex. Rendered with no room bound (e.g. the
  Templates preview below) shows placeholder room data instead of erroring.
- **Auto-generated Room Calendar templates.** One screen per distinct
  `(width, height, palette_id)` in the panel-type catalog is synthesized on
  demand (`screen/backend.py`'s `synthetic_roomcalendar_screens()`, id
  `__roomcalendar_<w>x<h>_<palette>`) — a full-canvas `RoomCalendar` widget,
  not a file on disk. Any device can be assigned one directly; the render
  pipeline resolves its own bound room the same way as for a hand-built
  screen. Because the same template now has to render differently per
  device, the screen render/image cache is keyed by `(root, screen id,
  room id)` instead of just `(root, screen id)` — see
  `get_screen_by_id()`/`ImageCache`.
- **Templates section.** The simplified UI's Templates (`screen/
  simplified_ui.py`) is no longer a placeholder: every screen in
  `paths.screen_dir` (shared storage with the non-simplified editor) plus
  the auto-generated Room Calendar templates above, each as a card with a
  live thumbnail; clicking one opens a larger preview (the same ruler/
  refresh view the full editor uses, `ui/preview.py`'s
  `screen_image_view()`). Read-only — no Add/Edit/Delete here.
- **Device panel type, to restrict its Screen choices.** A device binding
  can now record its actual panel (`DeviceBinding.panel_type_id`, from the
  panel-type catalog) — purely to filter the Screen select to matching
  resolution/palette (`screen/backend.py`'s `screens_matching_panel_type()`,
  `display/backend.py`'s `available_screen_ids()`); nothing validates
  `screen_id` against it afterwards, and an already-assigned mismatched
  screen stays visible rather than being dropped. Wired into nice4iot's
  device card (`devicebinding/ui.py`, a new "Panel type" select next to
  Screen) and the simplified UI's two Screen selects (filtered
  automatically once a device has a panel type set, no picker of their
  own).

### Changed (breaking: stored data)

- `BookingSystemModel.header` is now `Dict[str, str]` (was a JSON-text
  `str`, edited as a raw textarea). A `field_validator` migrates an
  old-format string on load (`json.loads`, `""` → `{}`), so existing booking
  system files keep working; saving through the new editor rewrites the
  field as a plain JSON object.
- `RoomCalendarWidgetModel` no longer has `room_number`/`room_name`/
  `ical_url` fields (see "room-driven" above) — the room comes from the
  rendering device's binding instead. A screen file that still has them
  loads unchanged (pydantic drops unknown fields by default); the widget
  just ignores them from then on. `examples/screens/roomcalendar.json`
  updated to match.

### Changed

- **niceview 0.26.3 (was 0.26.2).** Fixes `DrillDownWrapper` replaying its
  slide-in animation on every data change, not just real navigation — the
  simplified UI's Room detail no longer re-slides in on every autosaved
  field edit, only on Back/Open.

## 0.18.3 — 2026-08-22

### Added

- **Preferences > Schedule in the simplified UI.** A new section
  (`schedule/simplified_ui.py`) edits "default", the schedule every screen
  uses unless it overrides `update_schedule_id` — the same weekly-rule
  editor as the non-simplified Schedules tab (`schedule/ui.py`), just fixed
  to one file (auto-created empty on first visit), no list/rename/delete.
- **"Add times in a range" dialog.** A dense "+" button next to a weekly
  rule's Times field (both editors, since they share
  `schedule_editor_content`) opens a dialog for a start time, end time and
  interval (every 5/15/30 minutes, every hour — the default — or every 2
  hours) and adds every time in that range in one go, merged with the
  existing times. `schedule/backend.py`'s new `times_in_range()` does the
  HH:MM math; `TIME_RANGE_INTERVALS` holds the interval choices.

### Changed

- The weekly rule editor's weekday/month fields are now labelled "Only on
  these weekdays" / "Only in these months" (was "By weekdays"/"By months")
  — both default to "every" (see `WeeklyScheduleModel`), so what unchecking
  an entry does needed to be in the label itself: `checkbox_group` has no
  hint slot, and a hover tooltip wouldn't show on a touch device either.

## 0.18.2 — 2026-08-22

### Changed

- **Top-level Displays is now a drill-down list, not a grid.** The
  project-wide Displays section (`display/simplified_ui.py`'s
  `render_displays`) is now a niceview `DrillDownWrapper` over
  `RoomDisplaysAdapter`, matching the room-scoped Displays tab: each row
  shows an online/offline status dot, device name, room + screen, and
  WiFi/battery icons; the detail adds the room's building/floor/number, last
  seen, numeric RSSI/battery, an editable Screen select, and an "Open in
  nice4iot" link for experts. No Add or Delete, same as before. `RSSI`/
  `battery_voltage`/`last_seen_at`/`room_label`/`building`/`floor`/
  `room_number` are populated on `RoomDisplayRow` for both the room-scoped
  and top-level views (`RSSI`/`battery_voltage` stay `None` — no per-device
  source in nice4iot yet). Replaces the old `EditGridWrapper`-based grid.
- Moved `humanize_age()` (`ui/cards.py` → `util.py`) so it's shared by the
  new "last seen" line and the datasource health rows that already used it.

### Fixed

- **A device binding's Screen select crashed with no screens in the
  project.** An empty options list crashes the select widget regardless of
  `clearable`; both display details (room-scoped and top-level) now fall
  back to a plain hinted field when the project has no screens yet, same
  rule `booking_system_field_infos()` already used for booking systems.

## 0.18.1 — 2026-08-22

### Fixed

- **`confirm_dialog(ok_color=...)` → `ok_role=...`.** niceview's confirm
  dialog renamed this parameter a while ago; the two call sites still using
  the old name (schedule/ui.py's "Delete rule", screen/ui.py's "Delete
  widget") would have raised `TypeError` the moment either was clicked —
  found by introducing mypy (below), not by manual testing.
- **A cleared global accent color with no screen/widget override could reach
  the renderer as `None`.** `GlobalConfig.color_accent` is optional
  (clearable in Settings); `Screen.colors` now falls back to the global
  primary color in that case, same as any other "nothing configured"
  fallback, instead of only when *some* level is set.
- A screen's Displays-tab-less `_room_summary` no longer assumes `read_room()`
  found a room — it can return `None` if the room was deleted meanwhile; the
  tab now shows "Room not found" instead of crashing.

### Added

- **mypy, added to the toolchain.** `uv run mypy extensions` joins `ruff
  check`/`pytest` in CI and the commit workflow (see `CLAUDE.md`). Configured
  with the `pydantic.mypy` plugin (pydantic v2's own mypy plugin, without
  it most `Field(default_factory=...)`/discriminated-union usage reads as
  errors) and one narrow override: `core/widgets/*` disables
  `attr-defined`/`misc`/`index`/`arg-type`, since every widget's `draw()`
  deliberately accesses `self.config` as its own concrete subclass while it's
  statically typed as the `WidgetModel` base — `widget_type` already
  guarantees the real type at construction, so this is a load-bearing
  pattern, not sloppiness a type checker should flag. Fixing the ~90 findings
  outside that pattern turned up the two real bugs above, plus assorted
  narrower return-type/Optional-propagation corrections (`schedule/backend.py`'s
  `get_next_update`/`get_schedule_by_id`, `core/imagecache.py`'s `metadata`
  attribute, `core/drawingcontext.py`'s font/icon caches, a few others) and
  three call sites where niceview's/nicegui's own type stubs are narrower
  than what they actually accept (documented inline with `# type: ignore`).

## 0.18.0 — 2026-08-22

### Added

- **Templates section in the simplified UI.** A new top-level "Templates"
  nav item (right after Rooms) for screens — scaffolding only for now
  (`screen/simplified_ui.py`'s `render_templates`); the actual editor content
  follows later, in the same module.
- **Room Displays tab redesigned as its own drill-down list.** The room's
  Displays tab (`room/simplified_ui.py`) now leads with a compact room
  summary (`room_label · room type`, and, smaller, building/floor) followed
  by a niceview `DrillDownWrapper` list of the devices bound to the room
  (Title device name, Subtitle screen) instead of the shared grid. Each row's
  detail is editable and deletable: **Device** is a select over every project
  device (`display.backend.project_device_names`, all devices regardless of
  current room — unlike `assignable_devices()`), reassigning the row via the
  new `RoomDisplaysAdapter.rename()` (moves the room/screen assignment to the
  newly picked device, unbinding the old one) wired through niceview's
  `set_key`, the same rename pattern the file editors already use for their
  Name field; **Screen** is a select over the project's screen files. Add is
  the wrapper's own standard button, driving a device picker
  (`assignable_devices`) since there is nothing to type. The flat, top-level
  Displays section (`display/simplified_ui.py`) is unchanged (still the
  shared `render_displays_grid`).
- **`RoomModel.room_label`.** `"{room_number} ({room_name})"` when both are
  set, else whichever one isn't empty — a single compact human label,
  replacing the ad-hoc `f'{room_name} ({room_number})'` the device card's
  Room select used to build inline (and fixing its order to number-first).
  Also now the Rooms list's `item_title_field` (dropping `room_number` from
  the subtitle, redundant with the label).
- **`Screen.panel_label`.** A compact human label for a screen's panel: the
  applied panel type's own name + GxEPD2 class when `panel_type_id` is set
  and still resolves in the catalog; otherwise a plain
  `"{width}x{height} {palette_id} {n}-color"` summary of the screen's own
  fields. `panel_type_id` is now automatically cleared back to `None` as soon
  as a field the preset filled in (width, height, palette_id, or any of the
  three colors) is edited directly, so a resolved panel type can always be
  trusted to actually describe the screen's current fields
  (`screen/ui.py`'s `on_field_change` / `_diverges_from_panel_type`).

### Changed

- **niceview 0.26.1 (was 0.22.1).** Track niceview's own latest release
  (previously pinned to whatever nice4iot happened to pull in). 0.26.1 is
  purely additive for us (`DrillDownWrapper` gains `title_field`/
  `subtitle_fields` as aliases of `item_title_field`/`item_subtitle_fields`,
  and `Meta.include`/`exclude` now also apply to grids/lists) — no code
  changes needed. Adapts to niceview 0.23.0's wrapper API along the way:
  `DrillDownWrapper`'s `list_title` is gone — the list title/description now
  come from each model's `Meta` (`Meta.title_plural`/`Meta.description`),
  added to `RoomModel` and `BookingSystemModel`; `directory_drilldown` passes
  `title=` instead.
- **Rooms/booking-systems collection adapters use niceview's
  `JsonDirectoryAdapter`.** The hand-written `RoomsAdapter`/
  `BookingSystemsAdapter` classes are removed in favour of
  `room.backend.rooms_adapter()` / `bookingsystem.backend.booking_systems_
  adapter()`, thin factories over niceview 0.25.0's `JsonDirectoryAdapter`
  (one JSON per item in a directory, keyed by the model's `id`). CRUD is now
  strict (`create()` refuses an existing key, `update()` an absent one),
  which the DrillDownWrapper/ModelForm add-then-autosave flow already
  satisfies.
- **`display/`, `devicebinding/`, `global_config/`, `catalog/` feature
  packages (internal), continuing the nice4iot-style split.**
  - `display/`: `models/roomdisplay.py` → `display/models.py`,
    `core/roomdisplay.py` → `display/backend.py`,
    `ui/simplified_ui/{displays,displays_grid}.py` merge into
    `display/simplified_ui.py`.
  - `devicebinding/`: `models/devicebinding.py` → `devicebinding/models.py`,
    `core/devicebinding.py` → `devicebinding/backend.py`; the per-device
    settings card splits out of `ui/cards.py` into `devicebinding/ui.py`
    (`device_config_card`) — the dashboard summary card stays in
    `ui/cards.py`.
  - `global_config/`: `models/global_config.py` → `global_config/models.py`;
    the `app_config` singleton and `load_global_config`/`save_global_config`
    move from `config.py` into `global_config/backend.py` (their natural
    owner); `ui/global_settings.py` → `global_config/ui.py`. `config.py` now
    holds only the installation-specific, non-user-editable resource paths
    (`resource_paths`), matching nice4iot's own `app/config.py` shape.
  - `catalog/`: `models/display.py` → `catalog/models.py` (`Palette`,
    `PanelTypeModel`), `catalog.py` → `catalog/backend.py`. Bundled as one
    package rather than split by model, since both are read-only reference
    catalogs (no CRUD, no editor of their own — selection happens inside
    `screen/ui.py`'s form) sharing the same package-resource-plus-per-root-
    overlay loading mechanism; unlike the other feature packages there is no
    `ui.py`.
  - `models/` is now empty and removed. Import paths only, no behavior
    change beyond what's called out separately below.
- **Dead code removed from `display/simplified_ui.py`.** `render_displays_
  grid`'s `room_id` parameter and the `_assign_dialog` it drove were only
  ever reachable from the room's Displays tab, which now has its own
  drill-down UI (see above) — the grid's only remaining caller
  (`render_displays`) always passed `room_id=None`. The grid is now
  unconditionally the flat, unfiltered, no-Add view it already was in
  practice.

### Changed (breaking: stored data)

- **`DisplayModel` → `PanelTypeModel`, resource `displays.json` →
  `panel_types.json`.** "Display" was overloaded (the panel hardware vs. a
  device showing a screen in a room); the panel-hardware preset is now a
  *panel type*. Catalog API: `get_displays`/`get_display` →
  `get_panel_types`/`get_panel_type`; `EpaperPaths.display_file` →
  `panel_types_file`. The per-root overlay file is now `panel_types.json`.
- **`ColorModel` → `Palette`, resource `color_models.json` →
  `palettes.json`.** Distinguishes the palette object from the id fields
  referencing it (see below). Catalog API: `get_color_models`/
  `get_color_model` → `get_palettes`/`get_palette`; `color_models_mtime` →
  `palettes_mtime`; `EpaperPaths.color_model_file` → `palettes_file`. The
  `Screen.color_model` property (the resolved object) is now `Screen.palette`.
- **Id-reference fields renamed to distinguish the id from the object.**
  `ScreenModel.color_model` → `palette_id`; `ScreenModel.display_id` →
  `panel_type_id`; `PanelTypeModel.color_model` → `palette_id`.
- **Hard rename (no aliases).** Existing screen JSON files and per-root
  `displays.json`/`color_models.json`/overlays using the old keys/filenames
  are **not** migrated: the old keys are ignored (fields fall back to their
  defaults) and old overlay files are no longer read. Rename
  `displays.json`/`color_models.json` to `panel_types.json`/`palettes.json`
  and the keys `color_model`→`palette_id`, `display_id`→`panel_type_id` in
  stored screens. Shipped `examples/` are already updated.

## 0.17.1 — 2026-08-21

### Added

- **Rooms tab on nice4iot's project page.** A new "Rooms" project tab (before
  Screens) and a standalone Rooms page expose the rooms editor outside the
  simplified UI: a niceview `EditGridWrapper` over `rooms_adapter()`
  (`room/ui.py`'s `rooms_wrapper`, the editor counterpart to
  `screen/ui.py`/`schedule/ui.py`), rows edited in the grid's dialog. The
  `RoomModel.booking_system_id` column is a niceview `modelselect` resolved
  through the booking-systems repository, so it shows the system name
  (`BookingSystemModel.__str__`) rather than the raw id. A device's room is
  still assigned in its E-Paper device card (unchanged). The displays grid
  (`render_displays_grid`) now takes `paths`/`project_name` instead of a
  simplified-UI `Shell`, so both UIs share it.

### Changed

- **niceview 0.26.0 (was 0.22.1).** Track the version nice4iot pulls in.
  Adapts to niceview 0.23.0's wrapper API: `DrillDownWrapper`'s `list_title` is
  gone — the list title/description now come from each model's `Meta`
  (`Meta.title_plural`/`Meta.description`), added to `RoomModel` and
  `BookingSystemModel`; `directory_drilldown` passes `title=` instead. RoomModel's
  `notes` field is renamed to `description` (old room files drop the old key on
  next save). The `booking_ical_url`/room `Meta.layout` and booking-system fields
  (username/password/header/update_interval/max_days_ahead) ride along.

- **Rooms/booking-systems collection adapters use niceview's
  `JsonDirectoryAdapter`.** The hand-written `RoomsAdapter`/`BookingSystemsAdapter`
  classes are removed in favour of `room.backend.rooms_adapter()` /
  `bookingsystem.backend.booking_systems_adapter()`, thin factories over
  niceview 0.25.0's `JsonDirectoryAdapter` (one JSON per item in a directory,
  keyed by the model's `id`). Behaviour is the same for the UIs; CRUD is now
  strict (`create()` refuses an existing key, `update()` an absent one), which
  the DrillDownWrapper/ModelForm add-then-autosave flow already satisfies.

- **Feature-oriented module layout (screen, schedule, room, bookingsystem).**
  Following nice4iot's `core/forwarding` pattern, each of these four features
  now lives in its own package directly under `extensions/epaper/` with
  `models.py`, `backend.py` and the fitting UI file (`ui.py` editor for
  screen/schedule, `simplified_ui.py` section for room/bookingsystem) instead
  of being split across `models/`, `core/` and `ui/`. Shared infrastructure
  (rendering, datasources, widgets, `roomdisplay`, `devicebinding`, the
  simplified-UI frame) stays in place for now. Internal import paths only — no
  REST/public API or behavior change; the HTTP endpoints are unchanged.

## 0.17.0 — 2026-08-20

### Added

- **Simplified UI: page frame and navigation.** A new room-focused,
  e-paper-only extension page (`extensions/epaper/ui/simplified_ui/`,
  `register_project_page`) with its own chrome: a header (hamburger + brand
  + nice4iot user menu), a two-level sidebar in a responsive left drawer
  (inline from `lg`, an overlay below), and in-place view switching. Sections:
  Rooms (list + per-room detail with occupancy/settings/displays), Displays,
  and Einstellungen › Buchungssysteme (iCal config). The section views are
  scaffolding over demo data — the frame and navigation are the deliverable;
  the Room/Display/BookingSystem models and storage follow. As an extension,
  the header uses nice4iot's public `app.extensions.render_user_menu()`;
  standalone has no user session and omits the menu. See docs/simplified-ui.md,
  which also notes one optional nice4iot improvement (deep-linkable sub-paths).
- **Standalone link to the simplified UI.** The standalone app serves it as
  a full page at `/ui/simplified`, linked from an "Open" card at the top of
  the Global tab (`ui/standalone.py`).
- **Rooms are wired in the simplified UI.** The Rooms section is a niceview
  `DrillDownWrapper` over the rooms directory (`core/room.py`'s `RoomsAdapter`),
  so the list, Add and Delete are niceview's; the module only supplies the row
  and a three-tab detail (Occupancy, Settings — the `RoomModel` form,
  autosaving through the adapter — and Displays, the devices bound to the room
  from `devices_in_room`). Rooms are created with a fresh id and file; renaming
  edits `room_name`/`room_number` only. Displays and Booking systems remain
  scaffolding.
- **Displays are wired in the simplified UI.** A niceview `EditGridWrapper`
  (`ui/simplified_ui/displays_grid.py`) over `core/roomdisplay.py` lists the
  e-paper displays, reused by the room's Displays tab (filtered to the room) and
  the top-level Displays section (all). Each row joins a nice4iot device (name,
  online from `last_seen_at`) with its binding (Screen, inline-editable) and its
  bound room (building/floor/number); Remove unassigns a device, and in a room
  Add assigns an existing one. RSSI/battery/alarm columns exist but stay empty —
  nice4iot has no readable per-device source yet, tracked in
  docs/nice4iot-extension-wishlist.md (also: sanctioned device listing, online
  accessor). Device data is fetched via nice4iot's device backend in-process and
  degrades to empty in standalone.
- **Booking systems are wired in the simplified UI.** Settings › Booking
  systems is a niceview `DrillDownWrapper` over `core/bookingsystem.py`'s
  `BookingSystemsAdapter` (list, Add, Delete, and a `BookingSystemModel` form).
  A booking system is the connection/type (`models/bookingsystem.py`: id, name,
  type — iCal today — description), stored one JSON file per system in
  `EpaperPaths.booking_dir` (`data/booking/`); type-specific settings and
  Exchange follow behind the `type` switch. A room's **Booking system** field is
  now a select of the configured systems (options from storage, keeping a
  deleted system visible), referencing them by id. Displays remain scaffolding.
- **Room model** (`models/room.py`, `RoomModel`): a room's identity and
  booking source — number, name, building, floor, type (meeting, conference,
  lecture, seminar, office, lab, other), capacity, photo, notes, booking
  system, room-specific iCal URL — stored one JSON file per room in
  `EpaperPaths.room_dir` (`data/rooms/`). A room has a stable surrogate `id`
  (generated once, never changed, and the file name) so it can be renamed
  freely without breaking the device bindings that reference it — no human
  field is a safe key. The form's field metadata (labels, the room-type select,
  hints) rides each field's `Annotated` niceview `FieldInfo`, so the UI supplies
  only the layout. Presentation is deliberately *not* on the room — it stays in
  the per-device screen; nor are the room's displays a field (that is the
  device binding below).

### Changed

- **niceview 0.22.1** (the simplified UI's DrillDownWrapper/EditGridWrapper/
  ModelForm and the model-level FieldInfo build on it).
- **Device bindings replace `aliases.json`.** A nice4iot device's E-Paper
  configuration is now a typed record — `DeviceBinding{room_id?, screen_id?}`
  (`models/devicebinding.py`) — stored in `data/device_bindings.json`
  (`dict[device_name, DeviceBinding]`), so a device carries both the screen it
  renders *and* the room it hangs in, navigable from either side. An existing
  `aliases.json` (the bare `{name: screen_id}` map) is migrated automatically
  on first read. **API:** `core/screen.get_aliases()/set_alias()` are removed
  and `_resolve_alias()` is renamed `core/devicebinding.resolve_screen_id()`;
  the new module also exposes `get_device_binding()/set_device_binding()` and
  the reverse lookup `devices_in_room()` — all **synchronous** (the store is a
  tiny file, read like the editor's JsonAdapter), so `device_config_card` is
  now sync too. The device settings card gains a **Room** field alongside the
  existing Screen field. `EpaperPaths.alias_file`
  is replaced by `EpaperPaths.device_bindings_file`; `EpaperPaths.room_dir` is
  new. `examples/aliases.json` becomes `examples/device_bindings.json`.

## 0.16.0 — 2026-08-18

### Fixed

- **An Image widget set to a file crashed its own form** in a project that had
  no image files yet. The file select was built from the project directory,
  niceview rejects a select without options with a `ValueError`, and that took
  the whole widget form down. It now falls back to a plain field saying there
  are no image files yet. Found by the new test that renders every widget
  type's form (`tests/test_ui.py`); nothing had exercised a widget form before.

### Changed

- **The editor is split by concern instead of by "editor".** `ui/panels.py`
  (a grab bag of drilldown, dashboard, device card and global settings) and
  the 816-line `ui/screen_editor.py` are gone; in their place, one module per
  thing: `drilldown.py` (file list ↔ editor chrome), `preview.py` (image,
  pixel ruler, toolbar), `widget_types.py` (everything type-specific about a
  widget), `screen_editor.py` (the screen itself), `global_settings.py`,
  `cards.py`, and `forms.py` for the vocabulary they share. The largest module
  is now 415 lines instead of 816.
- **A widget type is declared in three places instead of six.** The editor
  used to spread the same eight type names over three parallel dicts
  (`WIDGET_MODELS`/`WIDGET_ICONS`/`WIDGET_TITLES`) and three if-chains
  (`_default_widget`, `_widget_label`, the per-type half of the detail form),
  so adding a type meant finding all of them and keeping them in step. They
  are now one `WIDGET_TYPES` entry each in `ui/widget_types.py`, next to the
  model and the drawing class. `core/widgets/WIDGET_CLASSES` replaces the
  `getattr(widgets, widget_type + "Widget")` lookup in `core/screen.py`: the
  naming convention was invisible from either end, and a typo resolved to
  None at render time rather than being a missing key. Documented in
  docs/development.md, "Adding a widget type".
- **Every form in the extension is now a layout plus field_infos**: the widget
  forms, the global settings and the schedule rules follow the Screen Settings
  from earlier in this release. Field styling is set once per form
  (`ui/forms.py`'s `FORM_STYLE`) rather than repeated per call site — the
  `props='outlined dense'` that appeared 44 times is gone, as is `_render_row()`
  with it (its last caller went with the change; say the word if you want it
  back). Two side effects worth knowing: fields in a row now share the width
  evenly (`flex-1`) instead of growing from their content, and the Image
  widget's "Reload now" button sits below the reload checkbox rather than
  beside it, since a layout renders fields and `extra` renders what is not one.
- **The screen's name is edited in its Screen Settings**, next to the size,
  palette and colors — the name is a setting of the screen, not chrome
  around it. The field itself still belongs to
  `panels.directory_drilldown()`, which owns the rename (it needs the
  `DirectoryAdapter` and the wrapper's key), but is now handed to the
  content as `render_content(filename, render_name_field)` instead of being
  rendered above it. A schedule has no settings panel to put it in and
  keeps it on top, where it was. **API change:** the `render_content`
  callback of `directory_drilldown()` takes a second argument, and
  `screen_editor_content()` / `schedule_editor_content()` take an optional
  `render_name_field` as their last parameter.
- **The Screen Settings are a niceview form layout** (`layout=` +
  `field_infos=`) instead of hand-placed `render_field()` calls. Same
  fields, same headings, same spacing — `'## Title'` from niceview 0.18.0
  is a section heading without a card, and the `':classes'` entries keep
  the panel's `gap-2`. `base_props='outlined dense'` and
  `default_classes='w-full'` replace the per-field repetition, and fields
  in a row now share the width evenly (`flex-1`) rather than growing from
  their content (`flex-grow`). `exclude=['widgets']` is gone: a layout
  defines which fields are rendered, so the field set is stated once, and
  an unknown or duplicated name is a `ValueError` naming its position
  instead of a field silently missing from the form.
- **The preview image stops scaling up at 48rem** (`max-w-3xl`, Tailwind's
  md breakpoint). It is there to judge a layout, not to read it at 1:1, and
  on a wide window it took the whole content column. Scaling down is
  unchanged, ruler and pixel readout included — both are placed in
  percentages.
- niceview 0.16.0 → 0.22.0. The chrome buttons — Add/Delete/Back in the
  Screens and Schedules title rows, which niceview's `DrillDownWrapper`
  draws, not nicepaper — now bring no look of their own: `ChromeStyle.
  button_props` ships empty, so what was `dense flat` since 0.16.0 is a
  plain Quasar button until the *application* says otherwise. As a
  nice4iot extension nicepaper is not that application and still sets no
  chrome style of its own; standalone mode is, and sets none either, so
  its title-row buttons currently look like Quasar's defaults.
  Two smaller changes ride along and are visible in both modes: chrome
  buttons are only joined in a `ui.button_group` when more than one of
  them is on screen (0.16.1) — for a `DrillDownWrapper` that is never,
  since Add belongs to the list view and Delete to the detail view — and
  an icon-only chrome button is round unless it sits in such a group
  (0.16.2, `ChromeStyle.icon_button_props`, also empty by default).
  0.18.1 makes `clearable` reach `ui.color_input` (and `ui.input`,
  `ui.number`, `ui.textarea`, the date/time widgets), where NiceGUI has no
  such argument and the flag used to be dropped silently — which is what
  the Screen Settings' three color fields ask for.
  0.19.0–0.22.0 are otherwise additive for what nicepaper uses: form
  actions (`FormAction`, a `'@name'` button in a layout, `chrome_actions=`
  in every wrapper's title row), a `place` axis and replaceable `ChromeText`
  and dialog/notification chrome, an application-wide `FieldStyle`, and
  `BoundFieldAdapter` — none of which nicepaper sets or calls yet, so they
  change nothing here. One default does reach us: since 0.22.0 a `ModelList`
  renders at full width (`w-full`), so the Screens and Schedules lists fill
  their column instead of shrinking to the longest name.

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
