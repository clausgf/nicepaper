"""
Unlike GlobalConfig's app_config singleton, ProjectConfig is per-project --
there is one instance per EpaperPaths.root, not one per process -- so it is
read fresh from disk on every call instead of being cached in a module-level
object. The file is optional (absent means every field is at its default),
matching panel_types_file/palettes_file (see paths.py).
"""
from extensions.epaper.paths import EpaperPaths
from extensions.epaper.project_config.models import ProjectConfig


def get_project_config(paths: EpaperPaths) -> ProjectConfig:
    path = paths.project_config_file
    if path.exists():
        return ProjectConfig.model_validate_json(path.read_text())
    return ProjectConfig()


def save_project_config(paths: EpaperPaths, config: ProjectConfig) -> None:
    path = paths.project_config_file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(config.model_dump_json(indent=2))
