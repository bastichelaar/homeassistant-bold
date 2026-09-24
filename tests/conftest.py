"""Fixtures for Bold tests."""

import time

import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.bold.const import API_URL, DOMAIN

CLIENT_ID = "client-id"
CLIENT_SECRET = "client-secret"

LOCK = {
    "id": 17307,
    "name": "Voordeur",
    "model": {"name": "SX33", "description": "Smart Cylinder SX", "type": {"name": "Lock"}},
    "features": {"activatable": True, "remoteAccess": True, "lockedStatus": False},
    "settings": {"activationTime": 7},
    "locked": "UNKNOWN",
    "batteryLevel": "87",
    "batteryLastMeasurement": "2026-09-20T10:00:00Z",
    "actualFirmwareVersion": 95,
    "requiredFirmwareVersion": 95,
    "gateway": {"id": 99, "name": "Connect", "rssi": -61, "lastSeen": "2026-09-24T08:00:00Z"},
}
GATEWAY = {
    "id": 99,
    "name": "Bold Connect",
    "model": {"name": "GW", "description": "Bold Connect", "type": {"name": "Gateway"}},
    "features": {"activatable": False},
    "actualFirmwareVersion": 10,
    "requiredFirmwareVersion": 12,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations."""


@pytest.fixture
async def credentials(hass: HomeAssistant) -> None:
    """Register application credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential(CLIENT_ID, CLIENT_SECRET), DOMAIN
    )


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """A Bold config entry with a valid token."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="bas@example.com",
        unique_id="1",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "access",
                "refresh_token": "refresh",
                "token_type": "Bearer",
                "expires_in": 86400,
                "expires_at": time.time() + 86400,
            },
        },
    )


@pytest.fixture
def mock_api(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Mock the Bold API."""
    aioclient_mock.get(f"{API_URL}/v2/devices", json=[LOCK, GATEWAY])
    aioclient_mock.get(f"{API_URL}/v2/events", json=[])
    aioclient_mock.get(f"{API_URL}/v1/account", json={"id": 1, "email": "bas@example.com"})
    return aioclient_mock
