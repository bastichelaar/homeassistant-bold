"""Tests for setting up Bold and its entities."""

from datetime import timedelta
from http import HTTPStatus

import pytest

from homeassistant.components.lock import LockState
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.bold.const import API_URL, DOMAIN

from .conftest import LOCK

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
    assert err.value.translation_key == "command_failed"
    assert err.value.translation_placeholders["code"] == "GatewayUnreachable"
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
