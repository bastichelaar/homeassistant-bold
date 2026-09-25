"""Lock platform for the Bold Smart Lock integration.

Bold locks are "activated" rather than unlocked: for a few seconds the cylinder
engages and the door can be opened, after which it disengages by itself. The
entity therefore reports unlocked while that activation window is running.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from functools import partial
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

from .api import BoldCommandError, BoldError, BoldRateLimitError
from .const import DEFAULT_ACTIVATION_TIME, DOMAIN
from .coordinator import BoldConfigEntry, BoldCoordinator, triggered_by_name
from .entity import BoldEntity, async_add_per_device, is_activatable

PARALLEL_UPDATES = 1

# Bold puts its reason in errorCode or errorMessage (seen: errorCode "Unknown error",
# errorMessage "BLECommunicationError"), so match both.
KNOWN_ERRORS = {
    "blecommunicationerror": "ble_error",
    "gatewayunreachable": "gateway_unreachable",
    "gatewaynotfounderror": "gateway_unreachable",
    "devicefirmwareoutdated": "firmware_outdated",
}


def _known_error(err: BoldCommandError) -> str | None:
    for text in (err.error_code, err.error_message):
        if key := KNOWN_ERRORS.get(str(text).lower()):
            return key
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BoldConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bold locks."""
    async_add_per_device(
        entry,
        async_add_entities,
        lambda coordinator, device_id, device: (
            [BoldLock(coordinator, device_id)] if is_activatable(device) else []
        ),
    )


class BoldLock(BoldEntity, LockEntity):
    """A Bold lock that is activated remotely through a Bold Connect."""

    _attr_name = None
    _attr_translation_key = "lock"

    def __init__(self, coordinator: BoldCoordinator, device_id: int) -> None:
        """Initialize the lock. The unique id is the bare device id, as before."""
        super().__init__(coordinator, device_id, "")
        self._active_until: datetime | None = None
        self._cancel_timer: Any = None

    @property
    def _activation_end(self) -> datetime | None:
        ends = [self._active_until]
        if raw := self.device.get("isActiveUntil"):
            ends.append(dt_util.parse_datetime(raw))
        ends = [e for e in ends if e is not None]
        return max(ends) if ends else None

    @property
    def is_locked(self) -> bool | None:
        """Unlocked while activated; otherwise the bolt position if the lock knows it.

        Locks with lock detection (Bold Elite) report LOCKED, UNLOCKED or UNKNOWN.
        Without it (Bold SX) the lock is only ever open during an activation.
        """
        end = self._activation_end
        if end is not None and end > dt_util.utcnow():
            return False
        status = self.device.get("locked")
        if status == "UNLOCKED":
            return False
        if status == "LOCKED":
            return True
        if (self.device.get("features") or {}).get("lockedStatus"):
            return None
        return True

    @property
    def changed_by(self) -> str | None:
        """Return who last used the lock, from the Bold event log."""
        return triggered_by_name(
            self.coordinator.data.last_event.get(self.device_id)
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose when the current activation ends."""
        end = self._activation_end
        return {"active_until": end.isoformat() if end else None}

    async def async_unlock(self, **kwargs: Any) -> None:
        """Activate the lock."""
        await self.async_activate()

    async def async_activate(self, keep_active_until: datetime | None = None) -> None:
        """Activate the lock, optionally keeping it active until a given time."""
        if keep_active_until is not None:
            if not (self.device.get("features") or {}).get("keepActiveMode"):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="keep_active_unsupported",
                    translation_placeholders={"name": self.device.get("name", "")},
                )
            keep_active_until = dt_util.as_utc(keep_active_until)
            if keep_active_until <= dt_util.utcnow():
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="keep_active_in_past"
                )
        result = await self._command(
            partial(
                self.coordinator.api.async_remote_activation,
                keep_active_until=keep_active_until,
            )
        )
        if keep_active_until is not None:
            self._set_active_until(keep_active_until)
            return
        seconds = (
            result.get("activationTime")
            or (self.device.get("settings") or {}).get("activationTime")
            or DEFAULT_ACTIVATION_TIME
        )
        self._set_active_until(dt_util.utcnow() + timedelta(seconds=seconds))

    async def async_lock(self, **kwargs: Any) -> None:
        """Deactivate the lock (ends a running activation)."""
        await self._command(self.coordinator.api.async_remote_deactivation)
        self._set_active_until(None)

    async def _command(self, call) -> dict[str, Any]:
        if not self.device.get("gateway"):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="no_gateway",
                translation_placeholders={"name": self.device.get("name", "")},
            )
        try:
            return await call(self.device_id)
        except BoldRateLimitError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="rate_limited"
            ) from err
        except BoldCommandError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=_known_error(err) or "command_failed",
                translation_placeholders={
                    "name": self.device.get("name", ""),
                    "code": str(err.error_code),
                    "message": str(err.error_message),
                },
            ) from err
        except BoldError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err

    @callback
    def _set_active_until(self, end: datetime | None) -> None:
        self._active_until = end
        if self._cancel_timer:
            self._cancel_timer()
            self._cancel_timer = None
        if end is not None:
            self._cancel_timer = async_track_point_in_utc_time(
                self.hass, self._activation_ended, end
            )
        self.async_write_ha_state()

    @callback
    def _activation_ended(self, _now: datetime) -> None:
        self._cancel_timer = None
        self._active_until = None
        self.async_write_ha_state()
        self.hass.async_create_task(self.coordinator.async_request_refresh())

    async def async_will_remove_from_hass(self) -> None:
        """Cancel a pending timer."""
        if self._cancel_timer:
            self._cancel_timer()
        await super().async_will_remove_from_hass()
