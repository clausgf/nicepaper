"""
The device binding: the epaper-specific configuration for one nice4iot
device, keyed by the device's name.

Both relations live here, so it is the single source of truth for them:
  device -> screen  (screen_id, the former alias target; the render path
                     still resolves a device's image by its name via this)
  device -> room    (room_id)
A room's displays are found by scanning for room_id -- the room itself
stores no device ids, so a deleted device can never dangle.
"""
from typing import Optional

from pydantic import BaseModel, Field


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
