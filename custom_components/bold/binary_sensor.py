"""Binary sensor platform for the Bold Smart Lock integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BoldConfigEntry, BoldCoordinator
from .entity import BoldEntity, async_add_per_device

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BoldConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bold binary sensors."""
    async_add_per_device(
        entry,
        async_add_entities,
        lambda coordinator, device_id, device: [
            BoldFirmwareRequired(coordinator, device_id)
        ],
    )


class BoldFirmwareRequired(BoldEntity, BinarySensorEntity):
    """On when the device runs older firmware than Bold requires."""

    _attr_device_class = BinarySensorDeviceClass.UPDATE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "firmware_required"

    def __init__(self, coordinator: BoldCoordinator, device_id: int) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, device_id, "firmware_required")

    @property
    def is_on(self) -> bool | None:
        """Return whether a firmware update is required."""
        actual = self.device.get("actualFirmwareVersion")
        required = self.device.get("requiredFirmwareVersion")
        if actual is None or required is None:
            return None
        return actual < required
