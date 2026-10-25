"""Minimal async client for the Grocy REST API."""

from __future__ import annotations

from typing import Any

import aiohttp

from .const import DEFAULT_TIMEOUT


class GrocyError(Exception):
    """Base error for Grocy API failures."""


class GrocyConnectionError(GrocyError):
    """Grocy could not be reached."""


class GrocyAuthError(GrocyError):
    """The API key was rejected."""


class GrocyApiError(GrocyError):
    """Grocy returned an unexpected response."""


class GrocyClient:
    """Thin wrapper around the Grocy REST API (``/api``)."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str,
        api_key: str,
        verify_ssl: bool = True,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._base_url = normalize_url(url)
        self._api_key = api_key
        self._verify_ssl = verify_ssl

    @property
    def base_url(self) -> str:
        """Return the normalized Grocy base URL."""
        return self._base_url

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Perform a request and return the decoded JSON body (or None)."""
        url = f"{self._base_url}/api/{path.lstrip('/')}"
        headers = {"GROCY-API-KEY": self._api_key, "Accept": "application/json"}
        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                ssl=self._verify_ssl,
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
                **kwargs,
            ) as resp:
                if resp.status in (401, 403):
                    raise GrocyAuthError("Invalid Grocy API key")
                if resp.status >= 400:
                    text = await resp.text()
                    raise GrocyApiError(f"Grocy returned HTTP {resp.status}: {text}")
                if resp.status == 204:
                    return None
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise GrocyConnectionError(f"Cannot connect to Grocy: {err}") from err

    async def get_system_info(self) -> dict[str, Any]:
        """Return Grocy system info (used as connection test)."""
        data = await self._request("GET", "system/info")
        if not isinstance(data, dict):
            raise GrocyApiError("Unexpected response from /api/system/info")
        return data


def normalize_url(url: str) -> str:
    """Strip whitespace, trailing slashes and a trailing ``/api``."""
    url = url.strip().rstrip("/")
    if url.endswith("/api"):
        url = url[: -len("/api")]
    return url
