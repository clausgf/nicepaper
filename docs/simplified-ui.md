# Simplified UI

[← Documentation](README.md)

A room-focused, e-paper-only alternative to the standalone/nice4iot editors.
It is the extension's **standalone project page** (`register_project_page`,
see [architecture](architecture.md)), reached at
`/ui/project/<project>/ext/epaper`. nice4iot renders no chrome around it, so
the page owns its whole frame.

**Reaching it.** As a nice4iot extension, open it from the project page.
In the **standalone** app it is a full page of its own at `/ui/simplified`,
linked from the **Global** tab (an "Open" card above the settings card);
`standalone.py` registers the route and renders the single fixed root under
the name `standalone`.

Code: `extensions/epaper/ui/simplified_ui/` holds the shared frame —
`layout.py` (frame + nav) and `common.py` (view helpers). Each feature ships its
own section renderer in its package: `room/simplified_ui.py`,
`screen/simplified_ui.py` (Templates, scaffolding for now),
`bookingsystem/simplified_ui.py` (a thin wrapper around `bookingsystem/ui.py`,
shared with the nice4iot "Booking systems" project tab), `schedule/simplified_ui.py`
(Preferences > Schedule), `global_config/simplified_ui.py` (Preferences >
Global settings), `project_config/simplified_ui.py` (Preferences > Project
settings), `organizer/simplified_ui.py` (Preferences > Organizer names)
and `display/simplified_ui.py` (the top-level Displays section); room storage
is `room/backend.py`.
`render(project_name, paths=None)` is the entry point — the extension derives
`paths` from the project, standalone passes its fixed paths in.

## Layout

- **Header** — hamburger (only below the drawer breakpoint), brand, and, as
  an extension, nice4iot's own user menu on the right
  (`app.extensions.render_user_menu()`). Standalone has no user session, so
  the menu is omitted there.
- **Sidebar** — a two-level tree (sections, some with subsections) in a
  left drawer. Shown inline from `lg` (≥1024 px) and collapsed to a
  toggled overlay below it (`DRAWER_BREAKPOINT` in `layout.py`).
- **Content** — switches views in place (see *Navigation* below).

## Navigation

The sidebar tree is a list of `NavItem`s. A **leaf** carries a `render`
(it is a view); a **group** carries `children` and no render (clicking
only folds it). Current sections:

- **Rooms** — the landing view (`/` aliases `/rooms`): list + Add Room, led by
  a quiet datasource-outage summary (nothing when weather/Home
  Assistant/iCal/image are all healthy, one line per failing one otherwise —
  `ui.cards.datasource_health_rows(only_failing=True)`, the same health lines
  nice4iot's Dashboard tab/standalone's Project tab always show in full) and a
  warning if any room file failed to parse and was silently dropped from the
  list (`ui.cards.unreadable_items_banner()`). A room opens a detail view with
  three tabs, Occupancy shown first: Occupancy (status, plus the room's photo
  at the bottom), Settings (number, name, building, floor, type, capacity,
  notes, description, booking system, Booking System URL override, plus the
  photo upload/remove), and Displays (a room summary, the photo, then the devices
  bound to the room, see below).
- **Templates** — read-only: every screen (shared storage with the
  non-simplified editor) plus the auto-generated Room Calendar templates
  (see [screens.md](screens.md#auto-generated-room-calendar-templates)),
  each a card with a live thumbnail; clicking one opens a larger preview.
  No Add/Edit/Delete here — that's still the non-simplified editor
  (`screen/ui.py`'s `screens_wrapper`) or the standalone editor.
- **Displays** — the flat, project-wide drill-down list of every device; no
  Add or Delete (assigning a display to a room happens in the room's own
  Displays tab, or the device's E-Paper card). A device's room/screen
  assignment can outlive the room/screen itself (deleting either leaves
  dangling references visible on purpose, not silently rewritten) — the row
  and detail flag this rather than looking indistinguishable from "never
  assigned": `"Room deleted ⚠"` in place of the room label, `"{screen_id} ⚠"`
  in place of the screen subtitle (`display.backend.display_rows()`'s
  `room_label`/`screen_label`).
- **Settings › Schedule** — the weekly-rule editor for "default", the one
  schedule every screen uses unless it overrides `update_schedule_id` (see
  [screens.md](screens.md#update-schedules)); no list/rename/delete chrome,
  since there is only ever one schedule to manage here.
- **Settings › Booking systems** — list + Add; per-system config (iCal URL +
  refresh today; Exchange and others later), led by a warning if any booking
  system file failed to parse and was silently dropped from the list
  (`ui.cards.unreadable_items_banner()`). Also reachable as a nice4iot
  project tab ("Booking systems"), sharing the same `bookingsystem/ui.py`
  wrapper.
- **Settings › Organizer names** — a directly editable textarea for
  `organizer_names_file` (one name per line, saved on blur), previously
  admin-only/hand-placed on disk. Also reachable in the non-simplified UI:
  its own "Organizer names" card next to "E-Paper" in nice4iot's Project
  Settings sidebar group, and a second card on standalone's Settings page
  (`organizer/ui.py`'s `organizer_names_fields()`, shared content).
- **Settings › Project settings** — Home Assistant URL/token and the default
  weather location for *this* project only (`ProjectConfig`), the same fields
  as nice4iot's "Settings" project tab.
- **Settings › Global settings** — the same project-independent fields as
  nice4iot's "E-Paper" global settings card, embedded for convenience;
  editing here changes the setting for every project.

Switching is **real, bookmarkable URL routing** (`ui/simplified_ui/layout.py`,
`nicegui.ui.sub_pages`): each section has its own path relative to the page's
own base URL — `/rooms`, `/templates`, `/displays`, `/settings/schedule`,
`/settings/booking`, `/settings/organizer`, `/settings/project`,
`/settings/global` (`/` aliases `/rooms`, the landing view) — plus
`/rooms/{room_id}` to open a room's
detail directly. Clicking a sidebar row calls `ui.navigate.to()`, same as
nice4iot's own internal navigation; the active row is recomputed from the
browser's current path on every navigation (`sub_pages_router.on_path_changed`).
This needs nice4iot to route the extension page's whole subtree to it, not
just its exact base URL — see the note below. One asymmetry: opening
`/rooms/{room_id}` directly (fresh load or reload) shows that room, but
clicking a different room from the list afterward does not push a new URL —
that goes through niceview's `DrillDownWrapper`, which has no public
navigation-changed hook to sync from.

**Rooms** are wired to real storage: `room/backend.py` keeps one JSON file per
room (`RoomModel`, named by its stable surrogate id, see `room/models.py`).
The section is a niceview `DrillDownWrapper` over `rooms_adapter()` (a niceview
`JsonDirectoryAdapter`) — list, Add and Delete are niceview's; the module only
supplies the row (titled by `RoomModel.room_label`, a computed
`"{room_number} ({room_name})"`) and a three-tab detail (Occupancy, Settings,
Displays). The Settings form autosaves through the adapter, its field
labels/widgets/hints come from each `RoomModel` field's `Annotated` `FieldInfo`
(the UI supplies only the layout).

The room's **Occupancy** tab (`room/simplified_ui.py`'s `_occupancy_panel`) shows
a status card (Free, or Occupied with an "until" time and, below, when the next
meeting today starts) and an Upcoming list of every event, both from
`room/backend.py`'s `get_room_events()` -- the room's booking system's iCal
feed (see [screens.md](screens.md#update-schedules) for the datasource itself).
Raises a plain message (no booking system configured, or one with no URL) that
the panel shows instead of a card, rather than an empty "no events" that would
look the same either way. The fetch is a network call, so the panel renders a
loading state first and refreshes once it lands (`nicegui.background_tasks`,
not a bare `asyncio.create_task`, so the refresh reaches the right client).
A reload icon button re-fetches with `get_room_events(force=True)`, bypassing
the iCal cache's own TTL/backoff — for a booking made after the last fetch
that shouldn't have to wait out `update_interval` to show up. Below all of
that, the room's photo (see below), so it never pushes the live status down.

**Room photos** are a plain file per room, not a `RoomModel` field — one
image at most in `EpaperPaths.room_photo_dir` (`<room_id>.<ext>`, extension-
owned storage, deliberately not the project directory the `Image` widget
reads from), managed by `room/photo.py` and rendered by `room/simplified_ui.py`'s
`_room_photo_view()`: capped to `height=192px` with `fit=cover` so it can't
grow to dominate a tab on a phone, and rendered as nothing at all when the
room has none. The Settings tab is the only place it's editable — a
`ui.upload` (`accept=image/*`, so mobile browsers offer camera or library)
that replaces any previous photo (even under a different extension) plus a
"Remove photo" button shown once one exists.

The room's **Displays** tab (`room/simplified_ui.py`'s `_displays_panel`) leads
with a compact room summary (label + type, and, smaller, building/floor),
then the room's photo, then its own niceview `DrillDownWrapper` (not the
shared grid below) over
`RoomDisplaysAdapter`, one row per device bound to the room — Title device
name, Subtitle screen/panel/firmware. The panel part is `RoomDisplayRow.
panel_label` (`display.backend.display_rows()`): the configured panel type
as `"{panel_id} {name}"` (`catalog.backend.panel_type_label()`), `"—"`
without one, suffixed with a plain `⚠` when it doesn't match what the
firmware itself last reported (`display.backend.panel_mismatch_hint()`) --
plain text computed once per row, so the mismatch is visible in the list
without opening the detail (which still shows the fuller text hint, see
below). The screen part is `screen_label`, not the raw `screen_id` --
identical text unless the screen was deleted after assignment, when it's
suffixed `⚠` the same way (`screen_id` itself stays the raw value the Screen
field reads/writes). Each row's detail is editable and deletable: Device is
a select over every project device (`display.backend.project_device_names`),
reassigning the row to a different device via `RoomDisplaysAdapter.rename()`
(moves the room/screen assignment, unbinding the old device) wired through
niceview's `set_key` -- the same rename pattern the file editors already use
for their Name field; Screen is a select over the project's screens (real
files plus the auto-generated Room Calendar templates), narrowed to the
device's own panel type when nice4iot's device card has one set for it
(`display.backend.available_screen_ids`) — a mismatched existing assignment
stays visible rather than being dropped. Add
is the wrapper's own standard button, driving a small dialog that picks from
`display.backend.assignable_devices()` (devices not already in this room) since
there is nothing to type; Delete unassigns the device from the room (the
device and its screen stay). Below the Screen select, `display/preview.py`'s
`render_device_preview()` adds Current/Last delivered tabs — the screen as it
renders right now, and the actual PNG + timestamp the device's own alias URL
last served with a real `200 OK` (not a `304`, tracked by
`devicebinding/snapshot.py`, `GET .../last_delivered.png`) — so a stale or
never-polling device is visible here, not just assumed from "Online". The
Last delivered tab also shows when the device is next expected to poll
again (`humanize_eta()`), in red past that point (plus a grace window,
`display.backend.OVERDUE_GRACE`) — see
[screens.md](screens.md#displays-palettes-and-colors) for how that time is
computed.

**Booking systems** (Settings › Booking systems) are wired the same way:
`bookingsystem/backend.py` stores one JSON file per system
(`BookingSystemModel` — id, name, type, description), a `DrillDownWrapper` over
`booking_systems_adapter()` (a niceview `JsonDirectoryAdapter`) is the UI, and a room's Booking system field is a
select of the configured systems. A booking system is the connection/type
(iCal today); the room supplies its own resource (the iCal URL).

A booking system's detail has a custom `render_detail`
(`bookingsystem/ui.py`, shared by both UIs — see above): the
`BookingSystemModel` form (its own `Meta.layout`, which omits `header`)
plus two hand-built editors for the fields that layout omits — `header`
(`Dict[str, str]`, extra HTTP headers sent with every feed request) and
`category_colors` (`Dict[str, str]`, an iCal `CATEGORIES` entry mapped to a
card color for the `RoomCalendar` widget) — both inline-editable lists
(every row a live input pair, autosaving on change, no dialog) with a
delete icon per row and an "Add" button matching DrillDownWrapper's own
toolbar style (dense round), plus a "Reload all rooms" button
(`_reload_rooms_action`) that re-fetches every room using this system with
`get_room_events(force=True)` in one go — the system-wide equivalent of a
room's own Occupancy reload button, for when several rooms share one feed.
`category_colors`' color picker restricts
itself to the 6-color display's own colors (the `e6` Spectra palette
— black, white, yellow, red, blue, green): a booking system isn't tied to
one screen/panel, so there's no single "closest" color that would be right
for every room using it; a panel that doesn't have the chosen color exactly
falls back to black at render time instead (`core/widgets/roomcalendar.py`).

The top-level **Displays** section (`display/simplified_ui.py`'s
`render_displays`) is a niceview `DrillDownWrapper` over
`RoomDisplaysAdapter(paths, project_name)` (no `room_id` — every device in the
project, bound to a room or not), so technically less versed people can point
a device at a screen without opening nice4iot's own device UI. No Add or
Delete — a display is a nice4iot device, assigned to a room via the room's own
Displays tab above or the device's E-Paper card. Each row shows an
online/offline status dot, the device name, room + screen as subtitle, and
WiFi/battery icons, plus a red warning icon when the device is overdue to
poll again (`RoomDisplayRow.overdue`); the detail adds the room's
building/floor/number, last seen, a matching "Next update" line, numeric
RSSI/battery, an editable Screen select (narrowed to the device's panel type
when one is set, same as the room's own Displays tab above), and an "Open in
nice4iot" link for experts (`device_url`). RSSI and
battery have no per-device source in nice4iot yet, so their icons/values
stay at "no data" — see [extension wishlist](nice4iot-extension-wishlist.md).
A device's panel type itself is set on nice4iot's own device card
(`devicebinding/ui.py`), not here — this select only reads it. Same
Current/Last delivered preview tabs as the room-scoped detail above
(`render_device_preview()`, shared by both).

## Notes for the nice4iot extension interface

The header consumes nice4iot's user menu through the public
`app.extensions.render_user_menu()` (added to the extension API for this
page). Deep-linkable sub-paths (above) need a matching nice4iot change:
routing the extension page's whole subtree to `render_fn`, not just its
exact base URL, so `.../ext/epaper/rooms` doesn't 404 on reload — see
nice4iot's own `docs/extensions.md`, "Deep links within a standalone page".
