"""Application credentials platform for the Bold Smart Lock integration."""

from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.core import HomeAssistant

from .const import OAUTH2_AUTHORIZE, OAUTH2_TOKEN


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return the Bold authorization server."""
    return AuthorizationServer(authorize_url=OAUTH2_AUTHORIZE, token_url=OAUTH2_TOKEN)


async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    """Return placeholders for the credentials dialog."""
    return {
        "request_url": "https://sesamsolutions.gitlab.io/public-documentation/integration/oauth-authentication.html",
        "redirect_url": "https://my.home-assistant.io/redirect/oauth",
    }
