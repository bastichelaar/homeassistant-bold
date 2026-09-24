"""Data coordinator for the Bold Smart Lock integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import BoldApi, BoldAuthError, BoldError
from .const import (
    ACCESS_EVENT_TYPES,
    DOMAIN,
    EVENT_BOLD,
    EVENT_LOOKBACK,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

type BoldConfigEntry = ConfigEntry[BoldCoordinator]


@dataclass
class BoldData:
    """Everything the entities need from one poll."""

    devices: dict[int, dict[str, Any]]
    # Most recent access event per device id (activation, deactivation, locked).
    last_event: dict[int, dict[str, Any]] = field(default_factory=dict)


class BoldCoordinator(DataUpdateCoordinator[BoldData]):
    """Poll devices and access events from the Bold cloud."""

    config_entry: BoldConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: BoldConfigEntry, api: BoldApi
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api
        self._events_since: datetime | None = None
        self._seen_event_ids: set[int] = set()
        self._events_available = True

    async def _async_update_data(self) -> BoldData:
        try:
            devices = await self.api.async_get_devices()
        except BoldAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except BoldError as err:
            raise UpdateFailed(str(err)) from err

        data = BoldData(devices={d["id"]: d for d in devices if "id" in d})
        data.last_event = dict(self.data.last_event) if self.data else {}
        await self._async_update_events(data)
        return data

    async def _async_update_events(self, data: BoldData) -> None:
        """Fetch new access events; failures here never break the devices poll."""
        if not self._events_available:
            return
        now = dt_util.utcnow()
        first_run = self._events_since is None
        since = self._events_since or now - EVENT_LOOKBACK
        try:
            events = await self.api.async_get_events(
                list(data.devices), since, ACCESS_EVENT_TYPES
            )
        except BoldAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except BoldError as err:
            if "HTTP 403" in str(err):
                # The OAuth client lacks the events scope; stop asking.
                _LOGGER.warning("Bold refuses access to events, disabling them: %s", err)
                self._events_available = False
            else:
                _LOGGER.debug("Could not fetch Bold events: %s", err)
            return

        self._events_since = now
        for event in sorted(events, key=lambda e: e.get("time") or ""):
            event_id = event.get("id")
            if event_id in self._seen_event_ids:
                continue
            self._seen_event_ids.add(event_id)
            device_id = (event.get("device") or {}).get("id")
            if device_id is not None:
                data.last_event[device_id] = event
            if not first_run:
                self.hass.bus.async_fire(EVENT_BOLD, _event_payload(event))
        # Only ids inside the next lookback window can come back.
        if len(self._seen_event_ids) > 1000:
            self._seen_event_ids = {e.get("id") for e in events}


def _event_payload(event: dict[str, Any]) -> dict[str, Any]:
    device = event.get("device") or {}
    return {
        "type": event.get("type"),
        "time": event.get("time"),
        "device_id": device.get("id"),
        "device_name": device.get("name"),
        "status": event.get("status"),
        "user": triggered_by_name(event),
    }


def triggered_by_name(event: dict[str, Any] | None) -> str | None:
    """Return a readable name for whoever triggered an event."""
    if not event:
        return None
    who = event.get("triggeredBy") or {}
    name = " ".join(p for p in (who.get("firstName"), who.get("lastName")) if p)
    return name or who.get("emailAddress")
