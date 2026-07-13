"""
Schedule editor content, split out of panels.py alongside screen_editor.py
(see that module's docstring for why) -- kept separate from it since a
schedule (List[WeeklyScheduleModel]) has nothing in its editing model in
common with a screen's widget tree beyond the shared file-list/rename/
delete plumbing in panels.py.
"""
import os
from typing import Callable

from nicegui import ui
from niceview.dataadapter import JsonListAdapter
from niceview.form import ModelForm
from niceview.util import confirm_dialog

from extensions.epaper.models.updateschedulemodel import WeeklyScheduleModel
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.ui.panels import _rename_file
from extensions.epaper.util import check_filename


def schedule_editor(paths: EpaperPaths, filename: str, on_back: Callable[[], None], on_deleted: Callable[[], None]):
    """
    Edit a schedule as a card per weekly rule (WeeklyScheduleModel), backed
    by a niceview JsonListAdapter over the schedule file. Each card is an
    autosaving ModelForm bound to one list item; fields are placed by hand
    (niceview has no generic "card grid" widget, nor should it: which
    fields go where is inherently an application layout decision, not
    something a form library can generalize).
    """
    if not filename or not check_filename(filename) or not filename.endswith('.json'):
        ui.notify(f'Invalid file name: "{filename}".', type='negative')
        on_deleted()
        return

    schedule_path = paths.schedule_dir / filename
    if not schedule_path.exists():
        ui.notify(f'File "{filename}" does not exist.', type='negative')
        on_deleted()
        return

    adapter = JsonListAdapter(WeeklyScheduleModel, schedule_path)

    with ui.row().classes('w-full items-center gap-2'):
        ui.button(icon='arrow_back').props('round dense color=primary').on_click(on_back)
        ui.label(filename.strip('.json')).classes('text-h6')
        ui.space()
        ui.button(icon='edit').props('round dense').on_click(lambda: rename_file())
        ui.button(icon='delete').props('round dense color=negative').on_click(lambda: delete_schedule_file())

    @ui.refreshable
    def rule_cards():
        rules = list(adapter.items())
        if not rules:
            ui.label('No weekly rules yet — add one below.').classes('italic')
        for key, _item in rules:
            form = ModelForm.from_adapter(WeeklyScheduleModel, adapter, key, autosave=True)
            with ui.card().classes('w-full q-mb-md'):
                with ui.row().classes('w-full items-center justify-between'):
                    ui.label('Weekly rule').classes('text-subtitle1')
                    ui.button(icon='delete').props('color=negative dense flat').on_click(
                        lambda _, k=key: delete_rule(k))
                # checkbox_group returns a composite CheckboxGroup, not a
                # ui.element itself -- style its .widget (the row/column) instead
                form.render_field('by_weekdays', widget_type='checkbox_group', props='inline dense').widget.classes('w-full')
                form.render_field('by_months', props='outlined dense').classes('w-full')
                # times: List[Annotated[str, pattern]] -> ui.input_chips, a real
                # ui.element (unlike checkbox_group/editgrid), so .classes() works
                form.render_field('times', props='outlined dense').classes('w-full')
                form.render_nonfield_errors()

    async def delete_rule(key: str):
        if not await confirm_dialog('Delete rule', 'Delete this weekly rule? This cannot be undone.',
                                     ok_label='Delete', ok_color='negative'):
            return
        adapter.delete(key)
        rule_cards.refresh()
        ui.notify('Rule deleted', type='positive')

    def add_rule():
        adapter.create(WeeklyScheduleModel(times=[]))
        rule_cards.refresh()

    rule_cards()
    ui.button('Add Rule', icon='add', on_click=lambda: add_rule()).props('color=primary')

    with ui.dialog().style('width: 400px') as rename_dialog, ui.card():
        ui.label('Rename file').classes('text-h6 center')
        new_name_input = ui.input('New name', value=os.path.splitext(filename)[0]).classes('w-full')
        with ui.row().classes('w-full place-content-end'):
            ui.space()
            ui.button('Cancel', on_click=lambda: rename_dialog.submit(None))
            ui.button('Rename', on_click=lambda: rename_dialog.submit(new_name_input.value))

    async def rename_file():
        new_name = await rename_dialog
        if not new_name:
            ui.notify('Canceled renaming.', type='negative')
            return
        success, message = _rename_file(paths.schedule_dir, schedule_path, new_name)
        ui.notify(message, type='positive' if success else 'negative')
        if success:
            on_deleted()

    with ui.dialog().style('width: 400px') as confirm_delete_file_dialog, ui.card():
        ui.label('Delete file').classes('text-h6 center')
        ui.label(f'Are you sure you want to delete "{filename}"?')
        with ui.row().classes('w-full place-content-end'):
            ui.space()
            ui.button('Cancel', on_click=lambda: confirm_delete_file_dialog.submit(False)).props('color=green')
            ui.button('Confirm', on_click=lambda: confirm_delete_file_dialog.submit(True)).props('color=red')

    async def delete_schedule_file():
        confirm = await confirm_delete_file_dialog
        if confirm:
            os.remove(schedule_path)
            ui.notify(f'File "{filename}" deleted.', type='positive')
            on_deleted()
        else:
            ui.notify(f'Canceled deleting "{filename}".', type='negative')
