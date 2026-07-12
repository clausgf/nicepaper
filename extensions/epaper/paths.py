from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EpaperPaths:
    """
    All file locations epaper needs, computed from a single root directory.

    Standalone mode uses one fixed root (the repo's data/ directory).
    As a nice4iot extension, each project gets its own root at
    extension_project_dir(project_name, 'epaper') -- same internal layout,
    just rooted differently, so core/UI code doesn't need to know which
    mode it's running in.
    """
    root: Path

    @property
    def screen_dir(self) -> Path:
        return self.root / "screens"

    @property
    def schedule_dir(self) -> Path:
        return self.root / "schedules"

    @property
    def image_dir(self) -> Path:
        return self.root / "images"

    @property
    def ical_dir(self) -> Path:
        return self.root / "ical"

    @property
    def alias_file(self) -> Path:
        return self.root / "aliases.json"

    @property
    def organizer_names_file(self) -> Path:
        return self.root / "organizer_names.json"

    def ensure_dirs(self) -> None:
        for d in (self.screen_dir, self.schedule_dir, self.image_dir, self.ical_dir):
            d.mkdir(parents=True, exist_ok=True)
