"""Sensor platform for the Bold Smart Lock integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import BoldConfigEntry, BoldCoordinator
from .entity import BoldEntity, async_add_per_device, is_activatable

PARALLEL_UPDATES = 0


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _time(value: Any) -> datetime | None:
    return dt_util.parse_datetime(value) if isinstance(value, str) else None


def _gateway(device: dict[str, Any]) -> dict[str, Any]:
    return device.get("gateway") or {}


@dataclass(frozen=True, kw_only=True)
class BoldSensorDescription(SensorEntityDescription):
    """Describes a Bold sensor."""

    value_fn: Callable[[dict[str, Any]], Any]
    exists_fn: Callable[[dict[str, Any]], bool]
    from_status: bool = False


SENSORS: tuple[BoldSensorDescription, ...] = (
    BoldSensorDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _number(d.get("batteryLevel")),
        exists_fn=lambda d: _number(d.get("batteryLevel")) is not None,
    ),
    # The spec types batteryLevel as a string; if Bold sends a word
    # (e.g. "Good"/"Low") rather than a number, show that instead.
    BoldSensorDescription(
        key="battery_status",
        translation_key="battery_status",
        value_fn=lambda d: d.get("batteryLevel"),
        exists_fn=lambda d: d.get("batteryLevel") is not None
        and _number(d.get("batteryLevel")) is None,
    ),
    BoldSensorDescription(
        key="battery_last_measurement",
        translation_key="battery_last_measurement",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _time(d.get("batteryLastMeasurement")),
        exists_fn=lambda d: "batteryLastMeasurement" in d,
    ),
    BoldSensorDescription(
        key="last_locked",
        translation_key="last_locked",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: _time(d.get("lastLocked")),
        exists_fn=lambda d: bool((d.get("features") or {}).get("lockedStatus"))
        or "lastLocked" in d,
    ),
    # From the periodic DeviceStatus report the lock sends; value_fn gets that event.
    BoldSensorDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        from_status=True,
        value_fn=lambda s: s.get("averageTemperature"),
        exists_fn=is_activatable,
    ),
    BoldSensorDescription(
        key="voltage_idle",
        translation_key="voltage_idle",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        suggested_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        from_status=True,
        value_fn=lambda s: s.get("voltageIdle"),
        exists_fn=is_activatable,
    ),
    BoldSensorDescription(
        key="voltage_under_load",
        translation_key="voltage_under_load",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        suggested_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        from_status=True,
        value_fn=lambda s: s.get("voltageUnderLoad"),
        exists_fn=is_activatable,
    ),
    BoldSensorDescription(
        key="gateway_signal",
        translation_key="gateway_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _gateway(d).get("rssi"),
        exists_fn=lambda d: bool(_gateway(d)),
    ),
    BoldSensorDescription(
        key="gateway_last_seen",
        translation_key="gateway_last_seen",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _time(_gateway(d).get("lastSeen")),
        exists_fn=lambda d: bool(_gateway(d)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BoldConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bold sensors."""
    async_add_per_device(
        entry,
        async_add_entities,
        lambda coordinator, device_id, device: [
            BoldSensor(coordinator, device_id, description)
            for description in SENSORS
            if description.exists_fn(device)
        ],
    )


class BoldSensor(BoldEntity, SensorEntity):
    """A Bold sensor."""

    entity_description: BoldSensorDescription

    def __init__(
        self,
        coordinator: BoldCoordinator,
        device_id: int,
        description: BoldSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        if self.entity_description.from_status:
            status = self.coordinator.data.last_status.get(self.device_id)
            return self.entity_description.value_fn(status) if status else None
        return self.entity_description.value_fn(self.device)
