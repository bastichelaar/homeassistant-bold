"""Base entity for the Bold Smart Lock integration."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_TYPE_LOCK, DOMAIN, MANUFACTURER
from .coordinator import BoldConfigEntry, BoldCoordinator


class BoldEntity(CoordinatorEntity[BoldCoordinator]):
    """An entity that belongs to one Bold device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BoldCoordinator, device_id: int, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.device_id = device_id
        self._attr_unique_id = f"{device_id}_{key}" if key else str(device_id)
        device = self.device
        model = device.get("model") or {}
        firmware = device.get("actualFirmwareVersion")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device_id))},
            name=device.get("name"),
            manufacturer=MANUFACTURER,
            model=model.get("description") or model.get("name"),
            model_id=model.get("name"),
            sw_version=str(firmware) if firmware is not None else None,
            suggested_area=device.get("location") or None,
        )

    @property
    def device(self) -> dict[str, Any]:
        """Return the latest data for this device."""
        return self.coordinator.data.devices.get(self.device_id, {})

    @property
    def available(self) -> bool:
        """Available while the device is still in the account."""
        return super().available and self.device_id in self.coordinator.data.devices


def device_type(device: dict[str, Any]) -> str | None:
    """Return the Bold device type name, e.g. Lock or Gateway."""
    return ((device.get("model") or {}).get("type") or {}).get("name")


def is_activatable(device: dict[str, Any]) -> bool:
    """Return whether the device is a lock that can be operated remotely."""
    features = device.get("features")
    if features is None:
        return device_type(device) == DEVICE_TYPE_LOCK
    return bool(features.get("activatable")) and features.get("remoteAccess", True)


@callback
def async_add_per_device(
    entry: BoldConfigEntry,
    add_entities: Callable[[Iterable[Entity]], None],
    build: Callable[[BoldCoordinator, int, dict[str, Any]], Iterable[Entity]],
) -> None:
    """Add entities for every device now, and for devices that show up later."""
    coordinator = entry.runtime_data
    known: set[int] = set()

    @callback
    def _add_new() -> None:
        new = set(coordinator.data.devices) - known
        if not new:
            return
        known.update(new)
        add_entities(
            entity
            for device_id in new
            for entity in build(coordinator, device_id, coordinator.data.devices[device_id])
        )

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))
