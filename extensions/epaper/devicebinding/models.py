"""
The device binding: the epaper-specific configuration for one nice4iot
device, keyed by the device's name.

Both relations live here, so it is the single source of truth for them:
  device -> screen  (screen_id, the former alias target; the render path
                     still resolves a device's image by its name via this)
  device -> room    (room_id)
A room's displays are found by scanning for room_id -- the room itself
stores no device ids, so a deleted device can never dangle.

panel_type_id is a third, independent fact about the device -- which panel
it actually is (from the panel-type catalog, catalog/models.py) -- used only
to restrict the Screen select to matching resolution/palette (UI-side only;
nothing here validates screen_id against it, so a mismatched pair set some
other way still renders, same as any other dangling reference in this app).
"""
import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DeviceSnapshot(BaseModel):
    """Metadata sidecar for a device's polling state (devicebinding/
    snapshot.py). fetched_at is the last real 200's time -- the PNG bytes
    for it live next to this file, not base64 in here -- and is None until
    the device's first real delivery. next_expected_at is when the device is
    next expected to poll again, per the most recent Cache-Control: max-age
    it was sent (200 or 304 alike, so it stays current even while the image
    itself hasn't changed); None if never told one yet."""
    fetched_at: Optional[datetime.datetime] = None
    next_expected_at: Optional[datetime.datetime] = None


class DeviceBinding(BaseModel):
    room_id: Optional[str] = Field(
        default=None,
        description="Id of the room (rooms/<id>.json) this device hangs in. Empty = unassigned.",
    )
    screen_id: Optional[str] = Field(
        default=None,
        description=(
            "Id of the screen (screens/<id>.json) this device renders -- the "
            "former alias target, resolved when the device fetches its image "
            "by name. Empty = no screen assigned."
        ),
    )
    panel_type_id: Optional[str] = Field(
        default=None,
        description=(
            "Id of this device's actual panel (catalog/panel_types.json). "
            "Restricts the Screen select to screens of matching resolution/"
            "palette. Empty = no restriction."
        ),
    )
