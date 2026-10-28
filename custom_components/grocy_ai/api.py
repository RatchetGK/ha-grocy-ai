"""Minimal async client for the Grocy REST API."""

from __future__ import annotations

from datetime import date
import json
from typing import Any
from urllib.parse import quote

import aiohttp

from .const import DEFAULT_TIMEOUT


class GrocyError(Exception):
    """Base error for Grocy API failures."""


class GrocyConnectionError(GrocyError):
    """Grocy could not be reached."""


class GrocyAuthError(GrocyError):
    """The API key was rejected."""


class GrocyApiError(GrocyError):
    """Grocy returned an error or an unexpected response."""

    def __init__(self, message: str, status: int | None = None) -> None:
        """Store the HTTP status alongside Grocy's error message."""
        super().__init__(message)
        self.status = status


class GrocyNotFoundError(GrocyApiError):
    """The requested product or barcode does not exist in Grocy."""


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
                    raise GrocyApiError(await _error_message(resp), resp.status)
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

    async def get_product(self, product_id: int) -> dict[str, Any]:
        """Return product details (``ProductDetailsResponse``) for a product id."""
        return await self._get_product_details(f"stock/products/{product_id}")

    async def get_product_by_barcode(self, barcode: str) -> dict[str, Any]:
        """Return product details for a barcode; raise GrocyNotFoundError if unknown."""
        return await self._get_product_details(
            f"stock/products/by-barcode/{quote(barcode, safe='')}"
        )

    async def external_lookup(self, barcode: str) -> dict[str, Any] | None:
        """Look up an unknown barcode via Grocy's barcode lookup plugin and create it.

        Grocy's default plugin queries Open Food Facts. Returns the
        ``ExternalBarcodeLookupResponse`` (incl. the new product ``id``) or None
        when nothing was found.
        """
        data = await self._request(
            "GET",
            f"stock/barcodes/external-lookup/{quote(barcode, safe='')}",
            params={"add": "true"},
        )
        return data if isinstance(data, dict) and data.get("id") else None

    async def add_product(
        self,
        product_id: int,
        amount: float,
        best_before_date: date,
        price: float | None = None,
        location_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Add stock (purchase). Returns the created stock log entries."""
        body: dict[str, Any] = {
            "amount": amount,
            "best_before_date": best_before_date.isoformat(),
            "transaction_type": "purchase",
        }
        if price is not None:
            body["price"] = price
        if location_id is not None:
            body["location_id"] = location_id
        return await self._request("POST", f"stock/products/{product_id}/add", json=body) or []

    async def consume_product(
        self, product_id: int, amount: float, spoiled: bool = False
    ) -> list[dict[str, Any]]:
        """Consume stock. Raises GrocyApiError e.g. when amount exceeds the stock."""
        body = {"amount": amount, "spoiled": spoiled, "transaction_type": "consume"}
        return await self._request("POST", f"stock/products/{product_id}/consume", json=body) or []

    async def _get_product_details(self, path: str) -> dict[str, Any]:
        """GET a ProductDetailsResponse; Grocy answers 400 for unknown ids/barcodes."""
        try:
            data = await self._request("GET", path)
        except GrocyApiError as err:
            if err.status in (400, 404):
                raise GrocyNotFoundError(str(err), err.status) from err
            raise
        if not isinstance(data, dict) or "product" not in data:
            raise GrocyApiError(f"Unexpected response from /api/{path}")
        return data


async def _error_message(resp: aiohttp.ClientResponse) -> str:
    """Extract Grocy's ``error_message`` from an error response."""
    text = await resp.text()
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    if isinstance(data, dict) and data.get("error_message"):
        return str(data["error_message"])
    return f"Grocy returned HTTP {resp.status}: {text[:200]}"


def normalize_url(url: str) -> str:
    """Strip whitespace, trailing slashes and a trailing ``/api``."""
    url = url.strip().rstrip("/")
    if url.endswith("/api"):
        url = url[: -len("/api")]
    return url
