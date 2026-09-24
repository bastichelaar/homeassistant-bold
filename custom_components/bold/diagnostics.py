"""Diagnostics for the Bold Smart Lock integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import BoldConfigEntry

TO_REDACT = {
    "access_token",
    "refresh_token",
    "emailAddress",
    "email",
    "firstName",
    "lastName",
    "name",
    "owner",
    "triggeredBy",
    "location",
    "remarks",
    "backupPin1Name",
    "backupPin2Name",
    "backupPin3Name",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BoldConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data.data
    return async_redact_data(
        {
            "devices": list(data.devices.values()),
            "last_event": data.last_event,
        },
        TO_REDACT,
    )
