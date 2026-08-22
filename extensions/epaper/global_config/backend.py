"""
app_config is a single shared GlobalConfig instance, mutated in place by
load_global_config()/the global settings card rather than replaced --
every module that does `from extensions.epaper.global_config.backend import
app_config` sees loaded/edited values automatically, without needing to
change anything, as long as callers only ever setattr() its fields (never
`app_config = ...` a new object).
"""
from pathlib import Path

from extensions.epaper.global_config.models import GlobalConfig

app_config = GlobalConfig()


def load_global_config(path: Path) -> None:
    """Load persisted settings from `path` into the shared `app_config`
    singleton IN PLACE (mutating its fields, not replacing the object) --
    every module that already imported app_config sees the loaded values
    without needing to change anything. Creates the file with the current
    (default) values if it doesn't exist yet."""
    if path.exists():
        loaded = GlobalConfig.model_validate_json(path.read_text())
        for field_name in GlobalConfig.model_fields:
            setattr(app_config, field_name, getattr(loaded, field_name))
    else:
        save_global_config(path)


def save_global_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(app_config.model_dump_json(indent=2))
