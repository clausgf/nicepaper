"""
app_config is a single shared GlobalConfig instance, mutated in place by
load_global_config()/the global settings card rather than replaced --
every module that does `from extensions.epaper.config import app_config`
sees loaded/edited values automatically, without needing to change
anything, as long as callers only ever setattr() its fields (never
`app_config = ...` a new object).
"""
import importlib.resources
from pathlib import Path
from pydantic import DirectoryPath, Field
from pydantic_settings import BaseSettings

from extensions.epaper.models.global_config import ColorModel, GlobalConfig

__all__ = ["ColorModel", "GlobalConfig", "app_config", "resource_paths", "load_global_config", "save_global_config"]


def _resource_dir(name: str) -> str:
    # bundled inside the extensions.epaper package (see pyproject.toml package-data),
    # so this resolves correctly whether nicepaper runs standalone (cwd = repo root)
    # or is installed as a dependency inside another process (e.g. nice4iot)
    return str(importlib.resources.files(__package__) / "resources" / name)


class _ResourcePaths(BaseSettings):
    """Package-resource locations, resolved fresh via importlib.resources
    on every process start -- deliberately not part of GlobalConfig (not
    persisted/user-editable), see that module's docstring. Still
    overridable via FONT_PATH/ICON_PATH env vars for advanced deployments,
    matching the old Config class."""
    font_path: DirectoryPath = Field(default_factory=lambda: _resource_dir("fonts"))
    icon_path: DirectoryPath = Field(default_factory=lambda: _resource_dir("icons"))


resource_paths = _ResourcePaths()

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
