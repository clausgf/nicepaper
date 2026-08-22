"""
Package-resource locations: fixed, installation-specific paths, not user
settings. See extensions/epaper/global_config/ for the persisted,
user-editable settings (GlobalConfig, app_config).
"""
import importlib.resources
from pydantic import DirectoryPath, Field
from pydantic_settings import BaseSettings

__all__ = ["resource_paths"]


def _resource_dir(name: str) -> str:
    # bundled inside the extensions.epaper package (see pyproject.toml package-data),
    # so this resolves correctly whether nicepaper runs standalone (cwd = repo root)
    # or is installed as a dependency inside another process (e.g. nice4iot)
    return str(importlib.resources.files(__package__) / "resources" / name)


class _ResourcePaths(BaseSettings):
    """Package-resource locations, resolved fresh via importlib.resources
    on every process start -- deliberately not part of GlobalConfig (not
    persisted/user-editable), see global_config/models.py's docstring. Still
    overridable via FONT_PATH/ICON_PATH env vars for advanced deployments,
    matching the old Config class."""
    font_path: DirectoryPath = Field(default_factory=lambda: _resource_dir("fonts"))
    icon_path: DirectoryPath = Field(default_factory=lambda: _resource_dir("icons"))


resource_paths = _ResourcePaths()
