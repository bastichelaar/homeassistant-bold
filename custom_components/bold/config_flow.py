"""Config flow for the Bold Smart Lock integration."""

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BoldApi, BoldError
from .const import DOMAIN, OAUTH2_LEVEL


class BoldOAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle the Bold OAuth2 login."""

    DOMAIN = DOMAIN
    VERSION = 1

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Ask for a user-level session, which remote activation requires."""
        return {"level": OAUTH2_LEVEL}

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauth after Bold rejected the token."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create or update the entry for the logged-in Bold account."""
        token = data["token"]["access_token"]

        async def get_token() -> str:
            return token

        try:
            account = await BoldApi(
                async_get_clientsession(self.hass), get_token
            ).async_get_account()
        except BoldError:
            self.logger.exception("Could not read the Bold account")
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(str(account["id"]))
        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )
        self._abort_if_unique_id_configured()
        title = account.get("email") or account.get("firstName") or "Bold"
        return self.async_create_entry(title=title, data=data)
