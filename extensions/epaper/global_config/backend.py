"""Shared global configuration instance and persistence helpers."""
from pathlib import Path

from extensions.epaper.global_config.models import GlobalConfig

app_config = GlobalConfig()


def load_global_config(path: Path) -> None:
    """Load settings into the shared instance, creating defaults if absent."""
    if path.exists():
        loaded = GlobalConfig.model_validate_json(path.read_text())
        for field_name in GlobalConfig.model_fields:
            setattr(app_config, field_name, getattr(loaded, field_name))
    else:
        save_global_config(path)


def save_global_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(app_config.model_dump_json(indent=2))
