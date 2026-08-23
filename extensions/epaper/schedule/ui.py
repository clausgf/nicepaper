"""
Schedule editor: a DirectoryAdapter-backed DrillDownWrapper (schedules_wrapper)
over paths.schedule_dir, plus the actual schedule content (one card per
weekly rule) rendered inside its detail view. Kept separate from
screen/ui.py since a schedule (List[WeeklyScheduleModel]) has nothing
in its editing model in common with a screen's widget tree beyond the
shared file-list/rename/delete plumbing in drilldown.py.
"""
from typing import Callable, Optional

from nicegui import ui
from niceview import DrillDownWrapper, Field, JsonListAdapter, ModelForm
from niceview.util import confirm_dialog

from extensions.epaper.schedule.backend import TIME_RANGE_INTERVALS, times_in_range
from extensions.epaper.schedule.models import WeeklyScheduleModel
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.ui.drilldown import directory_drilldown
from extensions.epaper.ui.forms import FORM_STYLE
from extensions.epaper.util import check_filename


_RULE_LAYOUT = ['by_weekdays', 'by_months']
_RULE_FIELD_INFOS = {
    # by_weekdays/by_months default to "every" (see WeeklyScheduleModel), so
    # unchecking entries is what restricts the rule -- labelled by what
    # unchecking does, not by the field name, since checkbox_group has no
    # hint slot to add that as a separate note (and a hint/tooltip wouldn't
    # show on a touch device anyway).
    'by_weekdays': Field(widget_type='checkbox_group', props='inline', label='Only on these weekdays'),
    'by_months': Field(label='Only in these months'),
    # times: List[Annotated[str, pattern]] -> ui.input_chips. Which timezone
    # the times are in isn't guessable and the description is only a tooltip
    # (no hover on a touch device), so it gets a short permanent hint too.
    'times': Field(hint="'hh:mm' in the configured timezone"),
}


def _default_rule() -> WeeklyScheduleModel:
    """A new weekly rule. It starts with a time rather than an empty list:
    `times` is required, and niceview commits an item only once it validates
    as a whole -- an empty list would block editing weekdays/months until a
    time is added (and a rule without a time wouldn't schedule anything
    anyway). Weekdays/months default to "every", see WeeklyScheduleModel."""
    return WeeklyScheduleModel(times=['08:00'])


def schedule_editor_content(paths: EpaperPaths, filename: str,
                            render_name_field: Optional[Callable[[], None]] = None) -> None:
    """
    Edit a schedule as a card per weekly rule (WeeklyScheduleModel), backed
    by a niceview JsonListAdapter over the schedule file. Each card is an
    autosaving ModelForm bound to one list item; the cards themselves are
    built here because niceview has no generic "card grid" widget, nor
    should it -- which fields go where is an application layout decision.
    No file-level chrome (back/delete) of its own -- that's
    schedules_wrapper()'s job, via DrillDownWrapper's title row.

    render_name_field() is the rename field handed down by
    drilldown.directory_drilldown(); a schedule has no settings of its own to
    put it among, so it stays on top where it has always been.
    """
    if render_name_field is not None:
        render_name_field()

    schedule_path = paths.schedule_dir / filename
    if not check_filename(filename) or not schedule_path.is_file():
        ui.label(f'Schedule {filename!r} not found.').classes('text-negative')
        return

    adapter = JsonListAdapter(WeeklyScheduleModel, schedule_path)

    async def add_times_in_range(key: str) -> None:
        """'+' next to Times: pick a start/end (HH:MM) and an interval, and
        add every time in that range to the rule (merged with what's already
        there, deduplicated -- WeeklyScheduleModel sorts on save either way)."""
        with ui.dialog() as dialog, ui.card().classes('min-w-72 gap-2'):
            ui.label('Add times in a range').classes('text-subtitle1')
            start = ui.input('Start', placeholder='HH:MM').props('mask="##:##" outlined dense')
            end = ui.input('End', placeholder='HH:MM').props('mask="##:##" outlined dense')
            interval = ui.select(TIME_RANGE_INTERVALS, value=60, label='Interval').props('outlined dense')
            with ui.row().classes('w-full justify-end'):
                ui.button('Cancel', on_click=lambda: dialog.submit(False)).props('flat')
                ui.button('Add', on_click=lambda: dialog.submit(True)).props('unelevated')
        if not await dialog:
            return
        try:
            new_times = times_in_range(start.value, end.value, interval.value)
        except ValueError as exc:
            ui.notify(str(exc), type='negative')
            return
        item = adapter.read(key)
        item.times = sorted(set(item.times) | set(new_times))
        adapter.update(item)
        rule_cards.refresh()

    @ui.refreshable
    def rule_cards():
        rules = list(adapter.items())
        if not rules:
            ui.label('No weekly rules yet — add one below.').classes('italic')
        for key, _item in rules:
            with ui.card().classes('w-full q-mb-md'):
                with ui.row().classes('w-full items-center justify-between'):
                    ui.label('Weekly rule').classes('text-subtitle1')
                    ui.button(icon='delete').props('dense round size=sm color=negative') \
                        .tooltip('Delete this rule') \
                        .on_click(lambda _, k=key: delete_rule(k))
                ModelForm.from_adapter(WeeklyScheduleModel, adapter, key, autosave=True,
                                       layout=_RULE_LAYOUT, field_infos=_RULE_FIELD_INFOS,
                                       **FORM_STYLE).render()
                # Times gets its own single-field form so the '+' can sit in the
                # same row, right after it -- ModelForm has no per-field action slot.
                with ui.row().classes('w-full items-start gap-2 no-wrap'):
                    with ui.column().classes('flex-grow gap-0'):
                        ModelForm.from_adapter(WeeklyScheduleModel, adapter, key, autosave=True,
                                               layout=['times'], field_infos=_RULE_FIELD_INFOS,
                                               **FORM_STYLE).render()
                    ui.button(icon='add').props('dense') \
                        .tooltip('Add times in a range') \
                        .on_click(lambda _, k=key: add_times_in_range(k))

    async def delete_rule(key: str):
        if not await confirm_dialog('Delete rule', 'Delete this weekly rule? This cannot be undone.',
                                     ok_label='Delete', ok_role='delete'):
            return
        adapter.delete(key)
        rule_cards.refresh()
        ui.notify('Rule deleted', type='positive')

    def add_rule():
        adapter.create(_default_rule())
        rule_cards.refresh()

    rule_cards()
    ui.button('Add Rule', icon='add', on_click=lambda: add_rule())


def schedules_wrapper(paths: EpaperPaths) -> DrillDownWrapper:
    """
    Directory-backed list<->editor drill-down for schedule files, shared
    verbatim by standalone.py and __init__.py -- see screens_wrapper()'s
    docstring in screen/ui.py, same reasoning applies here. All the
    actual DrillDownWrapper/DirectoryAdapter wiring lives in drilldown.
    directory_drilldown(); this just binds it to schedule_dir and
    schedule_editor_content.
    """
    return directory_drilldown(
        paths.schedule_dir,
        default_content='[]',  # a schedule file is a plain List[WeeklyScheduleModel]
        title='Schedules',
        render_content=lambda filename, name_field: schedule_editor_content(paths, filename, name_field),
    )
