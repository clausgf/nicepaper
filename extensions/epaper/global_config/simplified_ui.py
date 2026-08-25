"""
Preferences > Global settings: the same fields the nice4iot "E-Paper" global
settings card shows (global_config_fields()), embedded here for convenience.

The underlying file is project-independent -- one file shared by every
project (see extensions/epaper/__init__.py's register(), which computes
its path from nice4iot's own projects_dir) -- so this must persist to that
*same* file, not a per-project one, or a project's Preferences tab would
silently diverge from the real global card. _global_config_path() mirrors
layout.py's _user_menu() try/except-ImportError convention to tell nice4iot
mode from standalone, where the single fixed root already *is* the only
"global" location there is (see ui/standalone.py's page_global()).
"""
from pathlib import Path

from nicegui import ui

from extensions.epaper.global_config.backend import save_global_config
from extensions.epaper.global_config.ui import global_config_fields
from extensions.epaper.ui.simplified_ui.common import view_header
from extensions.epaper.ui.simplified_ui.layout import Shell


def _global_config_path(shell: Shell) -> Path:
    try:
        from app.config import app_config as nice4iot_app_config
    except ImportError:
        return shell.paths.root / "global_config.json"  # standalone
    return Path(nice4iot_app_config.projects_dir).parent / '.epaper_global_config.json'


def render_global_settings(shell: Shell) -> None:
    with view_header('Global settings'):
        pass
    ui.label('Shared across every project.').classes('text-caption text-grey q-mb-sm')
    global_config_fields(persist=lambda: save_global_config(_global_config_path(shell)))
