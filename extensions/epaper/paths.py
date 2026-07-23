from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class EpaperPaths:
    """
    All file locations epaper needs, computed from a single root directory.

    Standalone mode uses one fixed root (the repo's data/ directory).
    As a nice4iot extension, each project gets its own root at
    extension_project_dir(project_name, 'epaper') -- same internal layout,
    just rooted differently, so core/UI code doesn't need to know which
    mode it's running in.

    project_root is where the Image widget looks for user-provided image
    files: in the nice4iot extension this is the project directory itself
    (root's parent, i.e. where 'Project Files' live), not epaper's own
    `.epaper` root. Standalone leaves it unset and falls back to root.
    """
    root: Path
    project_root: Optional[Path] = None

    @property
    def asset_dir(self) -> Path:
        """Directory of user-provided image files selectable by the Image
        widget -- the project directory (see project_root), or the data root
        standalone."""
        return self.project_root if self.project_root is not None else self.root

    @property
    def image_cache_dir(self) -> Path:
        """Cache for images fetched by the Image widget (downloaded URLs / a
        snapshot of the chosen file), so 'load once' survives re-renders."""
        return self.root / "imagecache"

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
    def weather_dir(self) -> Path:
        return self.root / "weather"

    @property
    def alias_file(self) -> Path:
        return self.root / "aliases.json"

    @property
    def organizer_names_file(self) -> Path:
        return self.root / "organizer_names.json"

    def ensure_dirs(self) -> None:
        for d in (self.screen_dir, self.schedule_dir, self.image_dir, self.ical_dir,
                  self.weather_dir, self.image_cache_dir):
            d.mkdir(parents=True, exist_ok=True)
