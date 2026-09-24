"""Minimal client for the Bold public API.

Docs: https://apidoc.boldsmartlock.com and
https://sesamsolutions.gitlab.io/public-documentation/integration/
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
import json
import logging
from typing import Any

from aiohttp import ClientError, ClientResponse, ClientSession

from .const import API_URL

_LOGGER = logging.getLogger(__name__)

PAGE_SIZE = 100


class BoldError(Exception):
    """Base error for the Bold API."""


class BoldAuthError(BoldError):
    """The token is revoked or expired and could not be refreshed."""


class BoldRateLimitError(BoldError):
    """Too many requests; Bold limits activations per user per day."""


class BoldCommandError(BoldError):
    """The server accepted the call but the lock command failed."""

    def __init__(self, error_code: str | None, error_message: str | None) -> None:
        """Keep Bold's own error code, it is the only useful hint for users."""
        super().__init__(f"{error_code}: {error_message}")
        self.error_code = error_code
        self.error_message = error_message


class BoldApi:
    """Talk to api.boldsmartlock.com with an OAuth2 bearer token."""

    def __init__(
        self,
        session: ClientSession,
        get_token: Callable[[], Awaitable[str]],
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._get_token = get_token

    async def _request(
        self, method: str, path: str, params: dict[str, Any] | None = None
    ) -> Any:
        token = await self._get_token()
        try:
            resp = await self._session.request(
                method,
                f"{API_URL}{path}",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
        except (ClientError, TimeoutError) as err:
            raise BoldError(f"Error talking to Bold: {err}") from err
        return await self._handle(resp)

    @staticmethod
    async def _handle(resp: ClientResponse) -> Any:
        if resp.status == 401:
            raise BoldAuthError("Bold rejected the access token")
        if resp.status == 429:
            raise BoldRateLimitError("Too many requests to Bold")
        if resp.status >= 400:
            text = await resp.text()
            raise BoldError(f"Bold returned HTTP {resp.status}: {text[:200]}")
        text = await resp.text()
        return json.loads(text) if text.strip() else None

    async def async_get_account(self) -> dict[str, Any]:
        """Return the account the token belongs to."""
        return await self._request("GET", "/v1/account")

    async def async_get_devices(self) -> list[dict[str, Any]]:
        """Return all devices the account has access to."""
        devices: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = await self._request(
                "GET",
                "/v2/devices",
                {"offset": offset, "size": PAGE_SIZE},
            )
            devices.extend(page or [])
            if not page or len(page) < PAGE_SIZE:
                return devices
            offset += PAGE_SIZE

    async def async_get_events(
        self, device_ids: list[int], since: datetime, types: tuple[str, ...]
    ) -> list[dict[str, Any]]:
        """Return access events for the given devices since a moment in time."""
        if not device_ids:
            return []
        # spaceDelimited arrays per the OpenAPI spec
        return (
            await self._request(
                "GET",
                "/v2/events",
                {
                    "deviceId": " ".join(str(i) for i in device_ids),
                    "type": " ".join(types),
                    "from": since.isoformat(),
                    "size": PAGE_SIZE,
                },
            )
            or []
        )

    async def async_remote_activation(
        self, device_id: int, keep_active_until: datetime | None = None
    ) -> dict[str, Any]:
        """Activate (unlock) a device through its Bold Connect.

        With keep_active_until the lock stays active until then (keep-active mode).
        """
        params = (
            {"keepActiveUntil": keep_active_until.isoformat()}
            if keep_active_until
            else None
        )
        return self._check(
            await self._request(
                "POST", f"/v1/devices/{device_id}/remote-activation", params
            )
        )

    async def async_remote_deactivation(self, device_id: int) -> dict[str, Any]:
        """Deactivate (lock) a device through its Bold Connect."""
        return self._check(
            await self._request(
                "POST", f"/v1/devices/{device_id}/remote-deactivation"
            )
        )

    @staticmethod
    def _check(result: dict[str, Any] | None) -> dict[str, Any]:
        # HTTP 200 only means the server call worked; the lock result is in the body.
        result = result or {}
        code = result.get("errorCode")
        if code in (None, "OK"):
            return result
        if code == "TooManyRequests":
            raise BoldRateLimitError(result.get("errorMessage") or code)
        _LOGGER.debug("Bold command failed: %s", result)
        raise BoldCommandError(code, result.get("errorMessage"))
