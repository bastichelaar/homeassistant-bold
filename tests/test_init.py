"""Tests for setting up Bold and its entities."""

from datetime import timedelta
from http import HTTPStatus

import pytest

from homeassistant.components.lock import LockState
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import InvalidData
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.bold.const import API_URL, DOMAIN

from .conftest import GATEWAY, LOCK

ACTIVATE = f"{API_URL}/v1/devices/{LOCK['id']}/remote-activation"


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("credentials", "mock_api")
async def test_setup_creates_entities(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Lock, sensors and diagnostics entities are created; gateway gets no lock."""
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    assert hass.states.get("lock.voordeur").state == LockState.LOCKED
    assert hass.states.get("sensor.voordeur_battery").state == "87.0"
    assert hass.states.get("sensor.voordeur_bold_connect_signal").state == "-61"
    assert hass.states.get("binary_sensor.bold_connect_firmware_update_required").state == "on"
    assert hass.states.get("binary_sensor.voordeur_firmware_update_required").state == "off"
    assert hass.states.get("lock.bold_connect") is None

    # Unique id stays the bare device id, so entities from the old integration carry over.
    assert er.async_get(hass).async_get("lock.voordeur").unique_id == "17307"
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, "17307"), config_entry.entry_id)
    assert device.sw_version == "95"
    assert device.model == "Smart Cylinder SX"


@pytest.mark.usefixtures("credentials", "mock_api")
async def test_unlock_then_relock_after_activation_time(
    hass: HomeAssistant, config_entry: MockConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    """Unlock shows unlocked for the activation time Bold returns."""
    aioclient_mock.post(
        ACTIVATE, json={"deviceId": LOCK["id"], "errorCode": "OK", "activationTime": 5}
    )
    await _setup(hass, config_entry)

    await hass.services.async_call(
        "lock", "unlock", {"entity_id": "lock.voordeur"}, blocking=True
    )
    assert hass.states.get("lock.voordeur").state == LockState.UNLOCKED

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=6))
    await hass.async_block_till_done()
    assert hass.states.get("lock.voordeur").state == LockState.LOCKED


@pytest.mark.usefixtures("credentials", "mock_api")
async def test_unlock_error_shows_bold_error_code(
    hass: HomeAssistant, config_entry: MockConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    """A failed activation surfaces Bold's error code instead of a bare message."""
    aioclient_mock.post(
        ACTIVATE,
        json={"deviceId": LOCK["id"], "errorCode": "GatewayUnreachable", "errorMessage": "Offline"},
    )
    await _setup(hass, config_entry)

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            "lock", "unlock", {"entity_id": "lock.voordeur"}, blocking=True
        )
    assert err.value.translation_key == "gateway_unreachable"
    assert hass.states.get("lock.voordeur").state == LockState.LOCKED


@pytest.mark.usefixtures("credentials")
async def test_unauthorized_starts_reauth(
    hass: HomeAssistant, config_entry: MockConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    """A 401 from Bold puts the entry in reauth instead of retrying forever."""
    aioclient_mock.get(f"{API_URL}/v2/devices", status=HTTPStatus.UNAUTHORIZED)
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flows] == ["reauth"]


@pytest.mark.usefixtures("credentials", "mock_api")
async def test_events_fire_and_set_changed_by(
    hass: HomeAssistant, config_entry: MockConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    """New access events are fired on the bus and fill changed_by."""
    await _setup(hass, config_entry)
    fired = []
    hass.bus.async_listen("bold_event", fired.append)

    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{API_URL}/v2/devices", json=[LOCK])
    aioclient_mock.get(
        f"{API_URL}/v2/events",
        json=[
            {
                "id": 5,
                "type": "DeviceActivation",
                "time": "2026-09-24T08:01:00Z",
                "device": {"id": LOCK["id"], "name": "Voordeur"},
                "triggeredBy": {"firstName": "Bas", "lastName": "T"},
            }
        ],
    )
    await config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert fired[0].data["user"] == "Bas T"
    assert fired[0].data["type"] == "DeviceActivation"
    assert hass.states.get("lock.voordeur").attributes["changed_by"] == "Bas T"
    assert config_entry.runtime_data.data.last_event[LOCK["id"]]["id"] == 5


ELITE = {
    **LOCK,
    "features": {**LOCK["features"], "lockedStatus": True},
    "lastLocked": "2026-09-24T07:30:00Z",
}


@pytest.mark.parametrize(
    ("status", "expected"),
    [("LOCKED", LockState.LOCKED), ("UNLOCKED", LockState.UNLOCKED), ("UNKNOWN", "unknown")],
)
@pytest.mark.usefixtures("credentials")
async def test_elite_reports_bolt_status(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    status: str,
    expected: str,
) -> None:
    """A lock with lock detection shows the real bolt position, or unknown."""
    aioclient_mock.get(f"{API_URL}/v2/devices", json=[{**ELITE, "locked": status}, GATEWAY])
    aioclient_mock.get(f"{API_URL}/v2/events", json=[])
    await _setup(hass, config_entry)

    assert hass.states.get("lock.voordeur").state == expected
    assert hass.states.get("sensor.voordeur_last_locked").state == "2026-09-24T07:30:00+00:00"


@pytest.mark.usefixtures("credentials", "mock_api")
async def test_sx_without_detection_has_no_last_locked(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A Bold SX (no lock detection) gets no last-locked sensor."""
    await _setup(hass, config_entry)
    assert hass.states.get("sensor.voordeur_last_locked") is None


@pytest.mark.usefixtures("credentials", "mock_api")
async def test_options_set_scan_interval(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """The polling interval option is applied after the entry reloads."""
    await _setup(hass, config_entry)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"scan_interval": 60}
    )
    await hass.async_block_till_done()

    assert config_entry.options == {"scan_interval": 60}
    assert config_entry.runtime_data.update_interval == timedelta(seconds=60)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"], {"scan_interval": 5}
        )


def _event(event_id: int, bold_type: str, **extra) -> dict:
    return {
        "id": event_id,
        "type": bold_type,
        "time": f"2026-09-24T08:0{event_id}:00Z",
        "device": {"id": LOCK["id"], "name": "Voordeur"},
        "triggeredBy": {"firstName": "Bas"},
        **extra,
    }


@pytest.mark.usefixtures("credentials", "mock_api")
async def test_activity_event_entity(
    hass: HomeAssistant, config_entry: MockConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    """Tamper alerts, failed PINs and bolt changes fire on the activity entity."""
    await _setup(hass, config_entry)
    assert hass.states.get("event.voordeur_activity").state == "unknown"

    async def poll(events: list[dict]) -> str:
        aioclient_mock.clear_requests()
        aioclient_mock.get(f"{API_URL}/v2/devices", json=[LOCK])
        aioclient_mock.get(f"{API_URL}/v2/events", json=events)
        await config_entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        return hass.states.get("event.voordeur_activity")

    state = await poll([_event(1, "DeviceActivation", method="Pin", result="PinInvalid", pinName="Oppas")])
    assert state.attributes["event_type"] == "activation_failed"
    assert state.attributes["method"] == "Pin"
    assert state.attributes["pin_name"] == "Oppas"

    state = await poll([_event(2, "DeviceLocked", status="Locked")])
    assert state.attributes["event_type"] == "locked"

    state = await poll([_event(3, "DeviceTamperVibration")])
    assert state.attributes["event_type"] == "tamper_vibration"

    # A status report updates the sensors but is not an activity.
    state = await poll([_event(4, "DeviceStatus", averageTemperature=19, voltageIdle=3012, voltageUnderLoad=2890)])
    assert state.attributes["event_type"] == "tamper_vibration"
    assert hass.states.get("sensor.voordeur_temperature").state == "19"
    assert float(hass.states.get("sensor.voordeur_battery_voltage_idle").state) == pytest.approx(3.012)


@pytest.mark.usefixtures("credentials", "mock_api")
async def test_activate_keep_active_until(
    hass: HomeAssistant, config_entry: MockConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    """bold.activate passes keepActiveUntil and keeps the lock unlocked until then."""
    aioclient_mock.post(ACTIVATE, json={"deviceId": LOCK["id"], "errorCode": "OK"})
    await _setup(hass, config_entry)  # LOCK has no keepActiveMode feature

    until = dt_util.utcnow() + timedelta(minutes=30)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "bold", "activate",
            {"entity_id": "lock.voordeur", "keep_active_until": until.isoformat()},
            blocking=True,
        )

    await hass.config_entries.async_unload(config_entry.entry_id)
    aioclient_mock.clear_requests()
    keep = {**LOCK, "features": {**LOCK["features"], "keepActiveMode": True}}
    aioclient_mock.get(f"{API_URL}/v2/devices", json=[keep])
    aioclient_mock.get(f"{API_URL}/v2/events", json=[])
    aioclient_mock.post(ACTIVATE, json={"deviceId": LOCK["id"], "errorCode": "OK"})
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "bold", "activate",
        {"entity_id": "lock.voordeur", "keep_active_until": until.isoformat()},
        blocking=True,
    )
    (call,) = [c for c in aioclient_mock.mock_calls if c[0] == "POST"]
    assert "keepActiveUntil" in call[1].query
    assert hass.states.get("lock.voordeur").state == LockState.UNLOCKED

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
    await hass.async_block_till_done()
    assert hass.states.get("lock.voordeur").state == LockState.UNLOCKED

    async_fire_time_changed(hass, until + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert hass.states.get("lock.voordeur").state == LockState.LOCKED


@pytest.mark.usefixtures("credentials", "mock_api")
async def test_ble_error_in_error_message_is_recognised(
    hass: HomeAssistant, config_entry: MockConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    """Bold's reason can sit in errorMessage, as seen on a real Bold Elite."""
    aioclient_mock.post(
        ACTIVATE,
        json={"deviceId": LOCK["id"], "errorCode": "Unknown error", "errorMessage": "BLECommunicationError"},
    )
    await _setup(hass, config_entry)
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            "lock", "unlock", {"entity_id": "lock.voordeur"}, blocking=True
        )
    assert err.value.translation_key == "ble_error"
    assert "Bluetooth" in str(err.value)
