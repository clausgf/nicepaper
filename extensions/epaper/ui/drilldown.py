"""
The file-level chrome both editors sit in: a DrillDownWrapper over a
directory of JSON files, with this project's list-row styling and the
inline rename field.

Screen- and schedule-specific behaviour stays in screen/ui.py /
schedule/ui.py; this module knows only about files.
"""
from pathlib import Path
from typing import Awaitable, Callable, Optional, Union

from nicegui import ui
from babel.dates import format_datetime, get_timezone
from niceview import DirectoryAdapter, DrillDownWrapper, FileEntry

from extensions.epaper.global_config.backend import app_config
from extensions.epaper.util import check_filename

# Slide-in-from-left/right for list<->detail switches: screen/ui.py's
# widget list<->detail, and niceview's own DrillDownWrapper uses an
# equivalent mechanism internally. These switches are all @ui.refreshable
# functions, which destroy and recreate their elements on every refresh
# rather than toggling a CSS class -- so a CSS *animation* (not
# *transition*) plays automatically on every recreation, with no JS/state
# wiring beyond picking left vs. right by navigation direction.
# shared=True lets this be registered once here at import time, before any
# page/client exists.
_SLIDE_CSS = '''
    @keyframes slide-in-right { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
    @keyframes slide-in-left  { from { transform: translateX(-100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
    .slide-in-right { animation: slide-in-right 0.25s ease-out; }
    .slide-in-left  { animation: slide-in-left  0.25s ease-out; }
'''
ui.add_css(_SLIDE_CSS, shared=True)


def slide_class(direction: str) -> str:
    """CSS class for a slide-in-from-left/right animation, keyed by
    navigation direction ('right' when drilling into a detail view,
    'left' when going back to a list)."""
    return 'slide-in-left' if direction == 'left' else 'slide-in-right'


def _entry_caption(item: FileEntry) -> str:
    """'<formatted mtime>, <size>' caption for a DirectoryAdapter FileEntry row."""
    dt_format = app_config.date_format + ' ' + app_config.time_format
    mtime_str = format_datetime(item.mtime, format=dt_format, tzinfo=get_timezone(app_config.timezone), locale=app_config.locale)
    if item.size < 1024:
        size_str = f'{item.size} B'
    elif item.size < 1024**2:
        size_str = f'{item.size/1024:.1f} kiB'
    else:
        size_str = f'{item.size/1024**2:.1f} MiB'
    return f'{mtime_str}, {size_str}'


def directory_drilldown(dir_path: Path, default_content: Union[str, Callable[[], str]],
                        title: str, render_content: Callable[[str, Callable[[], None]], None],
                        row_warning: Optional[Callable[[str], Optional[str]]] = None,
                        confirm_add: Optional[Callable[[], Awaitable[bool]]] = None) -> DrillDownWrapper:
    """
    Shared DrillDownWrapper wiring for a directory of JSON files, used
    identically by screen.ui.screens_wrapper() and
    schedule.ui.schedules_wrapper(): the "no custom dialogs" Add/Rename
    style from niceview's DirectoryAdapter example (examples/13_directory_
    drilldown.py) -- Add creates an "untitled-NN" file and opens it
    directly; Rename is an inline "Name" field, wired to
    DirectoryAdapter.rename() on blur -- plus this project's bordered-list
    row styling (icon + filename + mtime/size caption).

    render_content(filename, render_name_field) renders the actual per-file
    editor body (e.g. screen_editor_content(paths, filename,
    image_base_url) with paths/image_base_url already bound by the caller);
    this function only owns the file-level list<->editor chrome around it.

    Where the "Name" field goes is the content's decision, so it is handed
    down as render_name_field() rather than rendered here: a schedule wants
    it on top, a screen wants it in its Screen Settings, next to the other
    screen-level settings. The rename itself stays here -- it needs the
    adapter and the wrapper's set_key, neither of which the content knows
    about. A content that never calls it simply has no rename.

    row_warning(key) is an optional, purely presentational hook: given a
    file's key (name without .json) it returns a message to show as a
    warning icon + tooltip on that list row, or None for no warning. Used by
    the screens list to flag a screen whose update_schedule_id points at a
    missing schedule file; this function stays generic and knows nothing
    about screen semantics.

    confirm_add() is an optional async hook that runs before a file is
    created and answers whether to go ahead -- e.g. by awaiting a dialog,
    as the screens list does to ask which display the new screen is for.
    Without it, Add creates the file straight away, the no-dialog style
    above. It is awaited inside the Add click (niceview 0.15.0 made
    on_add awaitable for exactly this).
    """
    directory = DirectoryAdapter(dir_path, default_content=default_content)

    def render_list_container(render_rows) -> None:
        with ui.list().style('width: 100%').props('bordered separator'):
            render_rows()

    def render_row(key: str, item: FileEntry, select) -> None:
        with ui.item(on_click=lambda: select()):
            with ui.item_section().props('avatar'):
                ui.icon('description')
            with ui.item_section():
                ui.item_label(item.name)
                ui.item_label(_entry_caption(item)).props('caption').classes('italic')
            warning = row_warning(key) if row_warning else None
            if warning:
                with ui.item_section().props('side'):
                    ui.icon('warning', color='warning').tooltip(warning)

    def render_detail(adapter: DirectoryAdapter, key: str, set_key) -> None:
        def render_name_field() -> ui.input:
            def do_rename() -> None:
                new_name = name_input.value
                if not check_filename(f'{new_name}.json'):
                    ui.notify(f'Invalid file name: "{new_name}".', type='negative')
                    return
                try:
                    set_key(adapter.rename(key, new_name))
                except ValueError as e:
                    ui.notify(str(e), type='negative')

            name_input = ui.input('Name', value=key).classes('w-full').props('outlined dense')
            name_input.on('blur', do_rename)
            return name_input

        render_content(f'{key}.json', render_name_field)

    async def handle_add() -> None:
        if confirm_add is not None and not await confirm_add():
            return
        entry = directory.create()
        wrapper.open(entry.name)

    wrapper = DrillDownWrapper.from_adapter(
        FileEntry, directory,
        title=title, item_title_field='name', item_subtitle_fields=[],
        render_list_item=render_row,
        render_list_container=render_list_container,
        render_detail=render_detail,
        on_add=handle_add,
    )
    return wrapper
