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

Code: `extensions/epaper/ui/simplified_ui/` — `layout.py` (frame + nav),
`common.py` (view helpers), and one module per section (`rooms.py`,
`displays.py`, `booking.py`); room storage is `core/room.py`.
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
  Belegung (occupancy/status), Einstellungen (number, name, building,
  floor, type, photo, booking system, room-specific iCal URL), and
  Anzeigen (the displays in the room).
- **Displays** — list + Add Display.
- **Einstellungen › Buchungssysteme** — list + Add; per-system config
  (iCal URL + refresh today; Exchange and others later).

Switching is **client-side state on the `Shell`**, not URL routing:
`shell.navigate(id, **params)` sets the active view and refreshes the
sidebar and content. It is *not* deep-linkable — see the note below.

**Rooms** are wired to real storage: `core/room.py` keeps one JSON file per
room (`RoomModel`, named by its stable surrogate id, see `models/room.py`).
The section is a niceview `DrillDownWrapper` over `RoomsAdapter` — list, Add
and Delete are niceview's; the module only supplies the row and a three-tab
detail (Occupancy, Settings, Displays). The Settings form autosaves through
the adapter, its field labels/widgets/hints come from each `RoomModel` field's
`Annotated` `FieldInfo` (the UI supplies only the layout), and the Displays tab
lists the devices bound to the room via `core/devicebinding.devices_in_room`
(the assignment itself is made in a device's E-Paper card).

**Booking systems** (Settings › Booking systems) are wired the same way:
`core/bookingsystem.py` stores one JSON file per system
(`BookingSystemModel` — id, name, type, description), a `DrillDownWrapper` over
`BookingSystemsAdapter` is the UI, and a room's Booking system field is a
select of the configured systems. A booking system is the connection/type
(iCal today); the room supplies its own resource (the iCal URL).

**Displays** are a niceview `EditGridWrapper` (`ui/simplified_ui/displays_grid.py`)
over `core/roomdisplay.py`, reused by the room's Displays tab (filtered to the
room) and the top-level Displays section (all displays). Each row joins a
nice4iot device (name, online) with its binding (screen) and bound room
(building/floor/number); the Screen column is inline-editable, Remove unassigns
the device, and inside a room Add assigns an existing device. RSSI, battery and
alarm columns are present but empty — nice4iot exposes no per-device source yet
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
