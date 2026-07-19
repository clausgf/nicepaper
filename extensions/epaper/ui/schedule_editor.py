"""
Schedule editor: a DirectoryAdapter-backed DrillDownWrapper (schedules_wrapper)
over paths.schedule_dir, plus the actual schedule content (one card per
weekly rule) rendered inside its detail view. Split out of panels.py
alongside screen_editor.py (see that module's docstring for why) -- kept
separate from it since a schedule (List[WeeklyScheduleModel]) has nothing
in its editing model in common with a screen's widget tree beyond the
shared file-list/rename/delete plumbing niceview's DrillDownWrapper now
owns for both.
"""
from nicegui import ui
from niceview import DrillDownWrapper, JsonListAdapter, ModelForm
from niceview.util import confirm_dialog

from extensions.epaper.models.updateschedulemodel import WeeklyScheduleModel
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.ui.panels import directory_drilldown
from extensions.epaper.util import check_filename


def schedule_editor_content(paths: EpaperPaths, filename: str) -> None:
    """
    Edit a schedule as a card per weekly rule (WeeklyScheduleModel), backed
    by a niceview JsonListAdapter over the schedule file. Each card is an
    autosaving ModelForm bound to one list item; fields are placed by hand
    (niceview has no generic "card grid" widget, nor should it: which
    fields go where is inherently an application layout decision, not
    something a form library can generalize). No file-level chrome
    (back/rename/delete) of its own -- that's schedules_wrapper()'s job,
    via DrillDownWrapper's title row.
    """
    schedule_path = paths.schedule_dir / filename
    if not check_filename(filename) or not schedule_path.is_file():
        ui.label(f'Schedule {filename!r} not found.').classes('text-negative')
        return

    adapter = JsonListAdapter(WeeklyScheduleModel, schedule_path)

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


def schedules_wrapper(paths: EpaperPaths) -> DrillDownWrapper:
    """
    Directory-backed list<->editor drill-down for schedule files, shared
    verbatim by standalone.py and __init__.py -- see screens_wrapper()'s
    docstring in screen_editor.py, same reasoning applies here. All the
    actual DrillDownWrapper/DirectoryAdapter wiring lives in panels.
    directory_drilldown(); this just binds it to schedule_dir and
    schedule_editor_content.
    """
    return directory_drilldown(
        paths.schedule_dir,
        default_content='[]',  # a schedule file is a plain List[WeeklyScheduleModel]
        title='Schedules',
        render_content=lambda filename: schedule_editor_content(paths, filename),
    )
