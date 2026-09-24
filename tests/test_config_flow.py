"""Tests for the Bold config flow."""

from http import HTTPStatus

import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator
from yarl import URL

from custom_components.bold.const import DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_TOKEN

from .conftest import CLIENT_ID

REDIRECT = "https://example.com/auth/external/callback"


async def _login(hass, hass_client_no_auth, aioclient_mock, result):
    state = config_entry_oauth2_flow._encode_jwt(
        hass, {"flow_id": result["flow_id"], "redirect_uri": REDIRECT}
    )
    url = URL(result["url"])
    assert str(url.with_query(None)) == OAUTH2_AUTHORIZE
    assert url.query["client_id"] == CLIENT_ID
    assert "level" not in url.query
    assert "scope" not in url.query

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "access_token": "access",
            "refresh_token": "refresh",
            "token_type": "Bearer",
            "expires_in": 86400,
        },
    )
    return await hass.config_entries.flow.async_configure(result["flow_id"])


@pytest.mark.usefixtures("credentials", "current_request_with_host", "mock_api")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Log in and create an entry named after the Bold account."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await _login(hass, hass_client_no_auth, aioclient_mock, result)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "bas@example.com"
    assert result["result"].unique_id == "1"


@pytest.mark.usefixtures("credentials", "current_request_with_host", "mock_api")
async def test_reauth_updates_token(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """Reauth stores the new token on the existing entry."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await _login(hass, hass_client_no_auth, aioclient_mock, result)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
