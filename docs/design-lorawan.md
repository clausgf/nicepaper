# LoRaWAN client-side rendering — design notes

Status: early design discussion, nothing implemented yet. This document
captures the ideas discussed so far so they aren't lost; it is not a
finished spec. Firmware/rendering code will be hand-written together,
device by device, when this is actually built (see "Not a code
generator" below).

## Motivation

epaper-nice currently renders screens server-side to PNG and serves them
over HTTP (`/api/screen/{id}/image.png`). That model assumes a display
with enough network budget to fetch a raster image on every refresh.

Some planned displays are battery-powered with rare refresh and are
expected to communicate over LoRaWAN instead of Wi-Fi/HTTP. LoRaWAN
payloads are tiny (roughly 51–242 bytes depending on spreading factor in
EU868) and duty-cycle limited — transferring a rendered image is not a
question of optimizing it down, it is categorically impossible. For
these displays, rendering has to happen on the device itself, driven by
a local e-paper library (target: [GxEPD2](https://github.com/ZinggJM/GxEPD2)
on ESP32/Arduino), with only small, compact data sent over the air.

## Scope: RoomCalendar only, for now

Only the `RoomCalendar` widget is in scope initially. It has a narrow,
well-understood dynamic surface (a handful of upcoming appointments) and
a fixed layout, which makes it tractable. Other widget types (weather,
generic text/date) are not part of this design.

## Not a generic code generator

The original idea was a code generator that turns a screen JSON into
GxEPD2 rendering code automatically, mirroring the server-side widget
system. We moved away from that: a LoRaWAN room-calendar device is
specific enough (one physical room, one fixed screen size, one set of
static labels) that a general-purpose generator would be solving a
harder problem than the one that actually exists. Instead, each device's
firmware will be **hand-authored** (with AI assistance) when it's built,
using the ideas below as a guide rather than automatically generated
from `ScreenModel`/`RoomCalendarWidgetModel` JSON.

## What's static vs. dynamic

Looking at the current server-side implementation
(`extensions/epaper/core/widgets/roomcalendar.py`) clarifies what
actually needs to travel over the air:

**Static, baked into firmware at build time (no code generator, just
written once per device):**
- Screen size, widget geometry (card positions/sizes, `x_inset`,
  `h_card`, `h_card_gap`, `max_num_cards` computed from height) — all of
  this is fixed per physical screen today already (`WidgetModel.size`
  etc.), so it becomes plain constants in firmware, not something that
  needs to be interpreted at runtime.
- `room_number` / `room_name` — a given device only ever displays one
  room.
- Static config strings (`app_config.no_appointments`,
  `next_appointment`, `current_appointment`, `further_appointments`,
  `ical_error`) — currently editable via the Global settings card;
  baking them in means a firmware rebuild is needed if they change,
  which is an acceptable tradeoff for a battery/LoRaWAN device.
- The two icon glyphs actually used (FontAwesome glyphs U+F007 person,
  U+F017 clock, both 16pt) — small enough to embed as fixed monochrome
  bitmaps rather than a font.
- Fonts — Ubuntu-Regular/Bold/Italic at the specific sizes used, run once
  through Adafruit's `fontconvert` to produce GFX font headers. One-time
  asset step, not something regenerated per device.

**Dynamic, needs to come from the server (over LoRaWAN):**
- The upcoming event list for this room: per event, `dtstart`, `dtend`,
  `summary`, `organizer`, plus a stable identifier (iCal `UID`) so the
  device can match updates against what it already has.

**Computed locally on the device, not transmitted at all:**
- "Is this event current or next" and "which further events to show" —
  see below.

## Client-side pieces

Splitting the firmware into three independent pieces keeps each one
small:

1. **Event store** — a small persistent list of upcoming events
   (`dtstart`, `dtend`, `summary`, `organizer`, `uid`), updated via
   incremental add/remove/update messages from the server (see
   "Server-side diffing"). No iCal parsing on the device — it only ever
   receives already-resolved, already-decided event records.

2. **Slot assignment ("rotation")** — given the event store and the
   device's own current time, decide locally which event is "current"
   (started, not yet ended), which is "next", and which further events
   to show in the remaining card slots. This is the same classification
   `roomcalendar.py`'s `draw()` currently does server-side
   (`events[0].dtstart > now` → next vs. current), but it's a small,
   self-contained function — much simpler than the iCal parsing/
   timezone/multi-day-event handling that stays server-side (see
   `ba037fe`'s multi-day fix — that complexity should never need
   porting to firmware).

   Because the device knows the start/end times of everything in its
   local store, it can also **compute its own next wake time** as the
   soonest upcoming `dtstart`/`dtend` boundary, instead of polling on a
   fixed interval. Rotation then costs no network traffic at all — only
   actual calendar *changes* trigger a message from the server. This
   matters more for battery life than payload size does.

3. **Rendering** — the GxEPD2/Adafruit_GFX drawing code, taking the
   slot-assignment output (current/next/further, each with its text
   fields) plus the static layout/labels, and drawing exactly what
   `draw_card()`/`draw()` draw today. The one piece of logic worth
   porting carefully is the ellipsis/text-fit algorithm
   (`DrawingContext._ellipsis`/`_multiline_text`, used via
   `draw_text(..., ellipsis='...')`): iteratively measure text width and
   truncate. `Adafruit_GFX::getTextBounds()` gives the same kind of
   metrics needed to reimplement it 1:1.

   Color handling is actually *simpler* on-device than server-side:
   no dithering/quantization needed (that's a `imagecache.py` concern
   for raster output only) — just draw directly with GxEPD2's native
   color constants for the panel's palette.

## Time sync

A separate LoRaWAN channel handles time sync, needed anyway for general
device/system management (independent of epaper-nice). The device uses
that channel's clock for its local "now", so `now` does not need to be
part of the calendar payload at all.

## Server-side: event diffing

To only send new appointments and changes (not the full list every
time), the server needs to remember, per device, what it last told that
device, and compute a delta (add / remove / update) keyed by the iCal
`UID` on each fetch. This is new infrastructure, but comparable in shape
to the existing per-root caches in `EpaperPaths` (ical/weather dirs) —
a persistent small JSON/state file per device recording "last known
event set", rather than the current fully-stateless render-on-request
model.

## Payload encoding

Given the tight LoRaWAN payload budget, the dominant cost is free-text
fields (`summary`, `organizer`). This is exactly what the German Huffman
codebook (already prepared earlier, held for a future LoRaWAN channel)
is for. Start/end times can be encoded compactly as small integers
(e.g. day-offset + minute-of-day, a few bytes) rather than full
timestamps.

## TTN integration (MQTT)

nice4iot (the extension host) already talks MQTT — relevant for wiring
LoRaWAN uplinks/downlinks through The Things Network (TTN).

**How nice4iot's MQTT currently works** (`app/mqtt/backend.py`,
`app/mqtt/models.py` in the nice4iot repo): a single shared broker
connection (`MqttGlobalConfig`: server/port/username/password/client_id,
one connection for the whole nice4iot instance). Two routing mechanisms
sit on top of it:
- Built-in per-project device topics: `project.mqtt_topic_base` with
  `{project}`/`{device}` placeholders, routing `.../telemetry/<kind>`,
  `.../upload/<filename>`, `.../log` suffixes to built-in handlers.
- Extension topics: `register_topic_handler(suffix, handler, qos)`
  matches `ext/<extension_name>/<project>/<suffix>`; extensions publish
  via `mqtt_publish(topic, payload, qos, retain)` or the file-specific
  `publish_file(...)`.

**How TTN's MQTT integration works:** TTN (The Things Stack) exposes a
regional MQTT broker per *application*
(e.g. `<region>.cloud.thethings.network:8883`), authenticated with the
application ID as username and an API key as password. Topics are fixed
by TTN, not customizable:
- Uplink: `v3/<app-id>@<tenant-id>/devices/<device-id>/up` — JSON
  envelope containing `end_device_ids.device_id`,
  `uplink_message.f_port`, `uplink_message.frm_payload` (base64-encoded
  raw bytes), plus radio metadata (RSSI/SNR).
- Downlink: publish JSON to
  `v3/<app-id>@<tenant-id>/devices/<device-id>/down/push` (or
  `down/replace`), body `{"downlinks": [{"f_port": .., "frm_payload":
  "<base64>", "priority": "NORMAL"}]}`.
- Various ack/nack/sent/failed/join event topics alongside `up`/`down`.

These topic shapes don't fit nice4iot's `{project}/{device}/suffix`
convention (TTN's `up`/`down/push` suffixes aren't `telemetry/...` or
`ext/<name>/...`), and nice4iot supports only one broker connection
instance-wide — pointing that single connection directly at TTN would
also cut off any other, non-LoRaWAN devices using the local broker.

**Recommended approach: a small bridge, not a core nice4iot change.**
Run a separate lightweight process that:
1. Connects to TTN's MQTT broker (application ID + API key), subscribes
   to `v3/+/devices/+/up`.
2. Unwraps the TTN JSON envelope, base64-decodes `frm_payload`, and
   republishes the raw bytes onto nice4iot's *local* broker under the
   epaper extension's own topic, e.g.
   `ext/epaper/<project>/<device>/up` — matching
   `register_topic_handler()`'s existing pattern, so the extension-side
   code only ever needs to know nice4iot's normal extension MQTT API,
   never TTN's envelope format.
3. Subscribes to a matching local downlink topic (e.g.
   `ext/epaper/<project>/<device>/down`, published via the extension's
   own `mqtt_publish()`), and republishes to TTN's
   `v3/.../down/push` with the required JSON wrapper.

This keeps nice4iot's core MQTT routing and single-broker assumption
untouched, and keeps all TTN-specific framing (JSON envelope, base64,
`f_port`) isolated in the bridge rather than leaking into the epaper
extension.

**Alternative (more invasive, not recommended for now):** point
nice4iot's one global MQTT connection directly at TTN's broker and
extend `_route_topic`/`register_topic_handler` to also understand TTN's
fixed topic shape. Would require multi-broker support to keep any local
(non-LoRaWAN) MQTT devices working alongside it — a bigger change to
nice4iot's core for a benefit (avoiding a small bridge process) that
seems marginal.

TTN also offers a per-device/per-application "payload formatter"
(JavaScript, runs on TTN's side) that could decode raw bytes into JSON
before they even reach the uplink envelope. Not planned to be used here
— decoding stays server-side in Python, consistent with keeping the
Huffman codebook and event-diffing logic in one place.

## Open questions

- Device provisioning on TTN (OTAA join, DevEUI/AppEUI/AppKey
  management) — out of scope for this document, a separate concern from
  rendering/payload design.
- Exact wire format for the event-diff payload (per-field encoding,
  Huffman table version handling, max events per message).
- Whether config strings baked into firmware should ever be
  updatable remotely, or if a reflash is always acceptable for this
  device class.
- Bridge deployment: separate process/container, or a small addition
  to how epaper-nice itself is deployed.
