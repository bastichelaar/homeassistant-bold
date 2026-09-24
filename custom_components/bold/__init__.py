"""The Bold Smart Lock integration."""

from __future__ import annotations

from aiohttp import ClientError
import voluptuous as vol

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_oauth2_flow,
    config_validation as cv,
    service,
)
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)
from homeassistant.helpers.typing import ConfigType

from .api import BoldApi, BoldAuthError
from .const import ATTR_KEEP_ACTIVE_UNTIL, DOMAIN, SERVICE_ACTIVATE
from .coordinator import BoldConfigEntry, BoldCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.EVENT,
    Platform.LOCK,
    Platform.SENSOR,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the bold.activate service."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_ACTIVATE,
        entity_domain=LOCK_DOMAIN,
        schema={vol.Optional(ATTR_KEEP_ACTIVE_UNTIL): cv.datetime},
        func="async_activate",
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: BoldConfigEntry) -> bool:
    """Set up Bold from a config entry."""
    try:
        implementation = (
            await config_entry_oauth2_flow.async_get_config_entry_implementation(
                hass, entry
            )
        )
    except ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            "Bold application credentials are not available"
        ) from err

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    try:
        await session.async_ensure_token_valid()
    except OAuth2TokenRequestReauthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except (OAuth2TokenRequestError, ClientError) as err:
        raise ConfigEntryNotReady(str(err)) from err

    async def get_token() -> str:
        try:
            await session.async_ensure_token_valid()
        except OAuth2TokenRequestReauthError as err:
            raise BoldAuthError(str(err)) from err
        return session.token["access_token"]

    api = BoldApi(aiohttp_client.async_get_clientsession(hass), get_token)
    coordinator = BoldCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BoldConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
