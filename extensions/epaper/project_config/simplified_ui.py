"""
Preferences > Project settings: project_config_fields(), embedded here for
convenience -- unlike global_config/simplified_ui.py's Global settings, this
needs no path resolution of its own since shell.paths already points at the
right project (see project_config/backend.py's docstring: one file per root).
"""
from extensions.epaper.project_config.ui import project_config_fields
from extensions.epaper.ui.simplified_ui.common import view_header
from extensions.epaper.ui.simplified_ui.layout import Shell


def render_project_settings(shell: Shell) -> None:
    with view_header('Project settings'):
        pass
    project_config_fields(shell.paths)
