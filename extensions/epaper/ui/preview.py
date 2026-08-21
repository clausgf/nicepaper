"""
The screen preview: the rendered image, framed by a pixel ruler, with the
toolbar below it (URL, outline toggle, auto-refresh, reload).

Knows nothing about screens, files or the editor -- it takes a URL and a
size. Split out of screen/ui.py, where it was the largest thing that
had nothing to do with editing.
"""
import math

from nicegui import ui

# Pixel ruler around the preview image. Grey is given as a translucent
# mid-grey rather than a theme color: it reads the same on the light and
# the dark Quasar background, so the frame needs no dark-mode variant.
# The tick marks are ::after pseudo-elements so a tick stays one element
# built from Python (a label positioned at a percentage), with the line
# itself defined once here.
#
# The child selectors are `> *`, not `> span`: NiceGUI decides the tag for
# ui.html/ui.label (both render a div), so selecting by tag silently
# matches nothing -- which drops position:absolute and stacks every tick
# in normal flow instead of spreading it along the ruler.
_RULER_CSS = '''
    .ep-preview { display: grid; grid-template-columns: 2.5rem 1fr 2.5rem;
                  grid-template-rows: 1rem auto 1rem; width: 100%; }
    .ep-canvas { position: relative; border: 1px solid rgba(128,128,128,0.55);
                 grid-column: 2; grid-row: 2; }
    .ep-ruler { position: relative; color: rgba(128,128,128,0.95);
                font-size: 0.65rem; line-height: 1; user-select: none; }
    .ep-ruler > * { position: absolute; white-space: nowrap; }
    .ep-ruler > *::after { content: ''; position: absolute; background: currentColor; }
    .ep-ruler-top    { grid-column: 2; grid-row: 1; }
    .ep-ruler-bottom { grid-column: 2; grid-row: 3; }
    .ep-ruler-left   { grid-column: 1; grid-row: 2; }
    .ep-ruler-right  { grid-column: 3; grid-row: 2; }
    .ep-ruler-top > *, .ep-ruler-bottom > * { transform: translateX(-50%); }
    .ep-ruler-left > *, .ep-ruler-right > * { transform: translateY(-50%); }
    .ep-ruler-top > *    { bottom: 4px; }
    .ep-ruler-bottom > * { top: 4px; }
    .ep-ruler-left > *   { right: 5px; }
    .ep-ruler-right > *  { left: 5px; }
    .ep-ruler-top > *::after    { left: 50%; bottom: -4px; width: 1px; height: 3px; }
    .ep-ruler-bottom > *::after { left: 50%; top: -4px; width: 1px; height: 3px; }
    .ep-ruler-left > *::after   { top: 50%; right: -5px; height: 1px; width: 3px; }
    .ep-ruler-right > *::after  { top: 50%; left: -5px; height: 1px; width: 3px; }
    .ep-readout { position: absolute; top: 4px; right: 4px; padding: 1px 5px;
                  font-size: 0.7rem; line-height: 1.3; font-variant-numeric: tabular-nums;
                  background: rgba(0,0,0,0.65); color: #fff; border-radius: 3px;
                  pointer-events: none; opacity: 0; transition: opacity 0.1s; z-index: 1; }
'''
ui.add_css(_RULER_CSS, shared=True)

# How far the frame scales up. 3xl is 48rem, Tailwind's md breakpoint --
# not 'max-w-screen-md', which Tailwind 4 (NiceGUI 3.15 ships 4.1.13)
# dropped, and not 'max-w-md', which is the 28rem step of the container
# scale rather than a breakpoint. A preview is for judging a layout, not
# for reading it at 1:1, and unbounded it took the whole content column.
_MAX_WIDTH = 'max-w-3xl'


def ruler_ticks(extent: int, divisions: int = 8) -> list[int]:
    """Tick values along `extent` screen pixels: 0, step, 2*step, ... on a
    1/2/5 x 10^k step aiming for roughly `divisions` of them, so the labels
    read as round figures (100, 250, ...) rather than whatever an even
    split produces -- the same reasoning as the charts' "nice number" axis
    labels, just in CSS rather than PIL.

    The far edge is appended too (it's the number a user actually wants
    when placing something flush right/bottom), but only when it wouldn't
    crowd the last regular tick."""
    if extent <= 0:
        return [0]
    raw = extent / max(1, divisions)
    magnitude = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    # max(1, ...): below ~8 px wide the ideal step rounds to 0, and a 0 step
    # is a ValueError from range() -- i.e. a crashing editor for a screen
    # someone mistyped the width of
    step = max(1, next(int(m * magnitude) for m in (1, 2, 5, 10) if raw <= m * magnitude))

    ticks = list(range(0, extent, step))
    if extent - ticks[-1] >= step / 2:
        ticks.append(extent)
    return ticks


def _ruler_frame(url: str, width: int, height: int) -> ui.image:
    """The image inside the ruler grid; returns the ui.image so the caller
    can still force_reload() it. It scales down freely below _MAX_WIDTH,
    ruler included -- the ticks sit at percentages."""
    with ui.element('div').classes(f'ep-preview {_MAX_WIDTH}'):
        for side, extent in (('top', width), ('bottom', width), ('left', height), ('right', height)):
            with ui.element('div').classes(f'ep-ruler ep-ruler-{side}'):
                horizontal = side in ('top', 'bottom')
                for value in ruler_ticks(extent):
                    offset = f'{value / extent * 100:.4f}%'
                    ui.html(str(value)).style(f'{"left" if horizontal else "top"}: {offset}')

        with ui.element('div').classes('ep-canvas') as canvas:
            # the screen's aspect ratio as QImg's own `ratio`, not a CSS
            # aspect-ratio on the box: QImg reserves its height from that
            # prop before the image loads, so the side rulers line up
            # immediately and stay lined up across reloads -- while a CSS
            # ratio on the wrapper would fight QImg's own sizing (which
            # is what left the canvas empty the first time round)
            img = ui.image(url).classes('q-pa-none w-full').props(f'ratio={width / height}')
            ui.element('div').classes('ep-readout')

    # client-side only (js_handler without a Python handler emits nothing),
    # so moving the mouse doesn't send one websocket message per pixel.
    # Coordinates come from the element's own bounding box, which already
    # accounts for whatever width the browser scaled the image to.
    canvas.on('mousemove', js_handler=f'''(e) => {{
        const box = e.currentTarget.getBoundingClientRect();
        const readout = e.currentTarget.querySelector('.ep-readout');
        const clamp = (v, max) => Math.max(0, Math.min(max, v));
        const x = clamp(Math.round((e.clientX - box.left) / box.width * {width}), {width});
        const y = clamp(Math.round((e.clientY - box.top) / box.height * {height}), {height});
        readout.textContent = x + ', ' + y;
        readout.style.opacity = 1;
    }}''')
    canvas.on('mouseleave', js_handler='''(e) => {
        e.currentTarget.querySelector('.ep-readout').style.opacity = 0;
    }''')
    return img


def screen_image_view(url: str, width: int = 0, height: int = 0) -> None:
    """The rendered screen, framed by a pixel ruler.

    Widgets are positioned by typing numbers into position_x/position_y,
    so the preview is only useful if it can be read back as coordinates:
    the frame carries labelled ticks on all four sides, and moving the
    mouse over the image shows the exact pixel under the cursor.

    Ticks are placed at percentages and the canvas keeps the screen's
    aspect ratio, so the ruler stays correct at whatever width the browser
    scales the image to -- nothing here depends on the rendered size, and
    the served image itself is untouched.
    """
    if width > 0 and height > 0:
        img = _ruler_frame(url, width, height)
    else:
        # no geometry known (shouldn't happen from the editor) -- still
        # show the image rather than nothing
        img = ui.image(url).classes(f'q-pa-none {_MAX_WIDTH}')

    with ui.row().classes('w-full items-center no-wrap gap-1 q-pa-none'):
        # the URL takes whatever is left over and ellipsises; min-width:0 is
        # what lets a flex child shrink below its content width at all, and
        # without it the controls would be pushed off the row instead
        ui.label(f'URL: {url}').classes('italic ellipsis flex-grow') \
            .style('min-width: 0').tooltip(url)

        def toggle_boxes(e) -> None:
            # the label keeps showing the plain URL: it is there to be copied
            # into a display's configuration, and the outlines are an editor
            # view no display should ever request
            img.set_source(f'{url}?boxes=true' if e.value else url)

        ui.switch(value=False, on_change=toggle_boxes).props('dense size=sm') \
            .tooltip('Outline every widget (preview only, never sent to a display)')
        auto_refresh = ui.switch(value=True).props('dense size=sm').tooltip('Auto-Refresh')
        ui.timer(3.0, lambda: img.force_reload() if auto_refresh.value else None)
        ui.button(icon='refresh').props('dense flat size=sm') \
            .tooltip('Reload the preview now') \
            .on('click', lambda img=img: img.force_reload())
