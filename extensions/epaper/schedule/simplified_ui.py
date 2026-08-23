"""
Preferences > Schedule: the simplified UI's editor for "default", the one
schedule every screen uses unless overridden (ScreenModel.update_schedule_id
defaults to 'default', see screen/models.py) -- so editing it here changes
when every display updates. Reuses schedule/ui.py's rule-cards editor
verbatim, just pointed at one fixed file instead of a directory of them:
there is exactly one schedule to manage here, so no list/rename/delete
chrome (unlike the non-simplified Schedules tab, which can hold several).
"""
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.schedule.ui import schedule_editor_content
from extensions.epaper.ui.simplified_ui.common import view_header
from extensions.epaper.ui.simplified_ui.layout import Shell

DEFAULT_SCHEDULE_FILENAME = 'default.json'


def _ensure_default_schedule(paths: EpaperPaths) -> None:
    path = paths.schedule_dir / DEFAULT_SCHEDULE_FILENAME
    if not path.is_file():
        path.write_text('[]')


def render_schedule(shell: Shell) -> None:
    _ensure_default_schedule(shell.paths)
    with view_header('Schedule'):
        pass
    schedule_editor_content(shell.paths, DEFAULT_SCHEDULE_FILENAME)
