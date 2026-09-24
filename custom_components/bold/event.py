"""Event platform for the Bold Smart Lock integration.

One event entity per lock that fires on everything Bold logs for it: activations
(and how: PIN, button, Bluetooth, ...), failed attempts, bolt status changes on
locks with lock detection (Bold Elite) and tamper alerts.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BoldConfigEntry, BoldCoordinator, event_payload
from .entity import BoldEntity, async_add_per_device, is_activatable

PARALLEL_UPDATES = 0

TAMPER_TYPES = {
    "DeviceTamperVibration": "tamper_vibration",
    "DeviceTamperRotations": "tamper_rotations",
    "DeviceTamperFaultyPin": "tamper_faulty_pin",
}
EVENT_TYPES = [
    "activated",
    "activation_failed",
    "deactivated",
    "locked",
    "unlocked",
    *TAMPER_TYPES.values(),
]


def ha_event_type(event: dict[str, Any]) -> str | None:
    """Map a Bold event to one of this entity's event types."""
    match event.get("type"):
        case "DeviceActivation":
            result = event.get("result")
            return "activated" if result in (None, "Success") else "activation_failed"
        case "DeviceDeactivation":
            return "deactivated"
        case "DeviceLocked":
            return {"Locked": "locked", "Unlocked": "unlocked"}.get(event.get("status"))
        case bold_type:
            return TAMPER_TYPES.get(bold_type)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BoldConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bold event entities."""
    async_add_per_device(
        entry,
        async_add_entities,
        lambda coordinator, device_id, device: (
            [BoldActivity(coordinator, device_id)] if is_activatable(device) else []
        ),
    )


class BoldActivity(BoldEntity, EventEntity):
    """Everything that happens at a Bold lock."""

    _attr_event_types = EVENT_TYPES
    _attr_translation_key = "activity"

    def __init__(self, coordinator: BoldCoordinator, device_id: int) -> None:
        """Initialize the event entity."""
        super().__init__(coordinator, device_id, "activity")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Fire the events that came in with the last poll."""
        for event in self.coordinator.data.new_events:
            if (event.get("device") or {}).get("id") != self.device_id:
                continue
            if (event_type := ha_event_type(event)) is None:
                continue
            attributes = event_payload(event)
            attributes.pop("type")
            self._trigger_event(event_type, attributes)
            self.async_write_ha_state()
        super()._handle_coordinator_update()
