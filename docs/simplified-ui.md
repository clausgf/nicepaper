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
`bookingsystem/simplified_ui.py` and `display/simplified_ui.py` (the top-level
Displays section and its shared grid); room storage is `room/backend.py`.
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

- **Rooms** — list + Add Room; a room opens a detail view with three tabs:
  Occupancy (status), Settings (number, name, building, floor, type, photo,
  booking system, room-specific iCal URL), and Displays (the devices bound
  to the room, see below).
- **Templates** — scaffolding for now; will become the screen editor.
- **Displays** — the flat, project-wide list; list only, no Add (assigning a
  display to a room happens in the room's own Displays tab, or the device's
  E-Paper card).
- **Settings › Booking systems** — list + Add; per-system config (iCal URL +
  refresh today; Exchange and others later).

Switching is **client-side state on the `Shell`**, not URL routing:
`shell.navigate(id, **params)` sets the active view and refreshes the
sidebar and content. It is *not* deep-linkable — see the note below.

**Rooms** are wired to real storage: `room/backend.py` keeps one JSON file per
room (`RoomModel`, named by its stable surrogate id, see `room/models.py`).
The section is a niceview `DrillDownWrapper` over `rooms_adapter()` (a niceview
`JsonDirectoryAdapter`) — list, Add and Delete are niceview's; the module only
supplies the row (titled by `RoomModel.room_label`, a computed
`"{room_number} ({room_name})"`) and a three-tab detail (Occupancy, Settings,
Displays). The Settings form autosaves through the adapter, its field
labels/widgets/hints come from each `RoomModel` field's `Annotated` `FieldInfo`
(the UI supplies only the layout).

The room's **Displays** tab (`room/simplified_ui.py`'s `_displays_panel`) leads
with a compact room summary (label + type, and, smaller, building/floor), then
its own niceview `DrillDownWrapper` (not the shared grid below) over
`RoomDisplaysAdapter`, one row per device bound to the room — Title device
name, Subtitle screen. Each row's detail is editable and deletable: Device is
a select over every project device (`display.backend.project_device_names`),
reassigning the row to a different device via `RoomDisplaysAdapter.rename()`
(moves the room/screen assignment, unbinding the old device) wired through
niceview's `set_key` -- the same rename pattern the file editors already use
for their Name field; Screen is a select over the project's screen files. Add
is the wrapper's own standard button, driving a small dialog that picks from
`display.backend.assignable_devices()` (devices not already in this room) since
there is nothing to type; Delete unassigns the device from the room (the
device and its screen stay).

**Booking systems** (Settings › Booking systems) are wired the same way:
`bookingsystem/backend.py` stores one JSON file per system
(`BookingSystemModel` — id, name, type, description), a `DrillDownWrapper` over
`booking_systems_adapter()` (a niceview `JsonDirectoryAdapter`) is the UI, and a room's Booking system field is a
select of the configured systems. A booking system is the connection/type
(iCal today); the room supplies its own resource (the iCal URL).

The top-level **Displays** section is a niceview `EditGridWrapper`
(`display/simplified_ui.py`'s `render_displays_grid`) over `display/backend.py`,
flat and unfiltered (every display in the project), with no Add — a display is
a nice4iot device, assigned to a room via the room's own Displays tab above or
the device's E-Paper card. Each row joins a nice4iot device (name, online) with
its binding (screen) and bound room (building/floor/number); the Screen column
is inline-editable, Remove unassigns the device. RSSI, battery and alarm
columns are present but empty — nice4iot exposes no per-device source yet
(see [extension wishlist](nice4iot-extension-wishlist.md)).

## Notes for the nice4iot extension interface

The header consumes nice4iot's user menu through the public
`app.extensions.render_user_menu()` (added to the extension API for this
page). One further nice4iot improvement would help but does not block it:

- **Deep-linkable sub-paths.** nice4iot routes only the extension page's
   *exact* base URL to the extension (`home_page`'s regex ends in `/?$`), so
   a sub-path like `.../ext/epaper/rooms` would 404 on reload. That is why
   navigation here is client-side state, not `ui.sub_pages`. Letting the
   extension-page match include sub-paths (and passing the remainder to
   `render_fn`) would let sections become bookmarkable.
