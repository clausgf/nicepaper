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
    def room_dir(self) -> Path:
        """Rooms of the simplified UI, one JSON file per room (RoomModel)."""
        return self.root / "rooms"

    @property
    def booking_dir(self) -> Path:
        """Booking systems of the simplified UI, one JSON file per system
        (BookingSystemModel)."""
        return self.root / "booking"

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
    def homeassistant_dir(self) -> Path:
        """Cached Home Assistant entity states (one JSON file per entity),
        including the failure/backoff state the dashboard reads."""
        return self.root / "homeassistant"

    @property
    def device_bindings_file(self) -> Path:
        """Typed collection file mapping a nice4iot device name to its
        DeviceBinding (room + screen). Replaces the old aliases.json, which
        devicebinding/backend.py migrates from on first read."""
        return self.root / "device_bindings.json"

    @property
    def panel_types_file(self) -> Path:
        """Optional per-root panel-type presets, merged over the ones shipped
        with the package (see catalog/backend.py). Absent by default."""
        return self.root / "panel_types.json"

    @property
    def palettes_file(self) -> Path:
        """Optional per-root palettes, merged the same way as panel_types_file."""
        return self.root / "palettes.json"

    @property
    def organizer_names_file(self) -> Path:
        return self.root / "organizer_names.json"

    @property
    def device_snapshot_dir(self) -> Path:
        """Last screen PNG actually delivered to each device -- a real 200 OK
        response, not a 304 Not Modified -- plus when, so Display Detail can
        show what a device is actually displaying, not just what the current
        screen would render. One <device_name>.png + <device_name>.json
        (fetched_at) per device that has fetched at least once. Written by
        api/endpoints.py's _render_screen_image(); see devicebinding/snapshot.py."""
        return self.root / "device_snapshots"

    def ensure_dirs(self) -> None:
        for d in (self.screen_dir, self.room_dir, self.booking_dir, self.schedule_dir,
                  self.image_dir, self.ical_dir, self.weather_dir, self.image_cache_dir,
                  self.homeassistant_dir, self.device_snapshot_dir):
            d.mkdir(parents=True, exist_ok=True)
