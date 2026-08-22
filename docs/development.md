# Development

[← Documentation](README.md)

The project is managed with [uv](https://docs.astral.sh/uv/). The standalone
server (`main.py`) is for development and debugging only; a real deployment
runs nicepaper as a [nice4iot](https://github.com/clausgf/nice4iot) extension
(see [Architecture](architecture.md)).

## Install from source

1. Clone the repository and install the dependencies:

   ```bash
   uv sync
   ```

   The schedule editor's card UI is built on
   [niceview](https://github.com/clausgf/niceview), pinned in `uv.lock`
   as a git dependency (pre-1.0, no PyPI release yet) — `uv sync` needs
   network access to GitHub the first time. Run
   `uv lock --upgrade-package niceview && uv sync` to pick up upstream
   changes.

2. Create the runtime data directories and copy the example configuration to
   get a working screen right away:

   ```bash
   mkdir -p data/screens data/schedules data/images data/ical
   cp examples/schedules/default.json data/schedules/
   cp examples/screens/simple.json data/screens/
   ```

   `examples/screens/roomcalendar.json` shows the `RoomCalendar` widget; edit
   its `ical_url` (and `examples/device_bindings.json`,
   `examples/organizer_names.json` if needed) before copying it in — see
   [Screens, widgets & schedules](screens.md).

## Run the standalone server

```bash
uv run uvicorn main:app --reload
```

- Management UI: <http://127.0.0.1:8000/ui>
- API docs: <http://127.0.0.1:8000/docs>
- Display image: `http://127.0.0.1:8000/api/screen/<id>/image.png`
  (quantized to the screen's own palette; `?raw=true` for the RGB render)

`<id>` is the name of a JSON file in `data/screens` without the extension, or
a display name bound to a screen in `data/device_bindings.json`.

## Tests and linting

All tests live in `tests/`; acceptance tests that exercise the HTTP API
end-to-end are in `tests/test_acceptance.py`, the rest are unit tests. CI runs
the same two commands:

```bash
uv run ruff check
uv run pytest
```

## Adding a widget type

A widget type is declared in exactly three places, all keyed by the same
`widget_type` string:

1. **`screen/models.py`** — the model: a `WidgetModel` subclass with
   `widget_type: Literal["Foo"] = "Foo"`, added to the `AnyWidget` union and to
   the `Literal[...]` on the base class.
2. **`core/widgets/`** — the drawing class (a `Widget` subclass with
   `async def draw(ctx)`), registered in `WIDGET_CLASSES` in that package's
   `__init__.py`.
3. **`ui/widget_types.py`** — one `WIDGET_TYPES` entry: icon, title, the one-line
   summary for the widget list, the defaults a new instance starts with, and the
   *Content* section of its form as a niceview layout. The *Layout* and
   *Appearance* sections come from the shared `_layout()`.

A form whose fields depend on the widget's own values (as the Image widget's
url/file and the Home Assistant widget's gauge/value do) makes `content` a
callable of `(widget, paths)` and names the deciding field in `refresh_on`.
Anything that is not a field at all — a button, a warning — goes in `extra`.

`tests/test_ui.py` renders every registered type's form, so a layout naming a
field that doesn't exist fails there rather than in the browser.

## Regenerating the low-bandwidth codec

`extensions/epaper/wire/huffman_de.py` holds a fixed German Huffman codebook
(part of the work-in-progress LoRaWAN rendering channel — see
[design notes](design-lorawan.md)). Since the device firmware is C,
`firmware/huffman_de.h` is a generated, self-contained C header with the same
codebook baked in plus a decode function. Regenerate it after editing the
codebook's `_WEIGHTS`:

```bash
uv run python -m extensions.epaper.wire.huffman_de
```

## Roadmap / open points

### Per-widget colors in the editor

`WidgetModel` has `color_primary`/`color_accent`, and rendering honours them
(each falling back to the screen's color independently, like `font_name`/
`font_size`), but the widget detail form doesn't render them yet — they can
only be set in the screen JSON. Adding them means naming both fields in the
*Appearance* section of `ui/widget_types.py`'s `_layout()`, next to the font
row, plus a `ui.color_input` entry each in its `_field_infos()` — once, for
every widget type.

### Getting the GxEPD2 class to the firmware

A panel type carries the matching GxEPD2 display class
(`gxepd2_class`, e.g. `GxEPD2_750_T7`) purely as a hint in the UI. A device
firmware still has to be built with the right class hard-coded. Open question
whether nicepaper should expose it — e.g. on a per-device endpoint next to the
image URL — so a firmware could check it against what it was built with and
warn on a mismatch.

### API keys for the display API

`/api` is currently protected by external middleware in front of the app. If
that check should move into the app, enforce it as a FastAPI dependency on the
`/api` router (`X-Api-Key` header). Proposed key management: a file
`data/api_keys.json` mapping a label per display to the SHA-256 hex hash of its
key, e.g. `{"display-r101": "<sha256-hex>"}`. Plain SHA-256 is sufficient here
(keys are high-entropy random strings, so brute-forcing the hash is hopeless,
and bcrypt would waste ~100 ms on every image request). Generate a key and its
hash with:

```bash
python3 -c "import secrets, hashlib; k = secrets.token_urlsafe(32); print(k, hashlib.sha256(k.encode()).hexdigest())"
```

Revocation = delete the line; one key per display so keys can be revoked
individually.

### LoRaWAN client-side rendering

A second, very low-bandwidth rendering channel for battery/LoRaWAN displays is
in early design — see the [design notes](design-lorawan.md).
