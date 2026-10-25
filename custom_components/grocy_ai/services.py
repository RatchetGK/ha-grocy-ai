"""Services for booking Grocy stock by barcode or product id."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util
import voluptuous as vol

from .api import GrocyClient, GrocyConnectionError, GrocyError, GrocyNotFoundError
from .const import (
    ATTR_AMOUNT,
    ATTR_BARCODE,
    ATTR_BEST_BEFORE_DATE,
    ATTR_BEST_BEFORE_SOURCE,
    ATTR_CONFIG_ENTRY_ID,
    ATTR_LOCATION_ID,
    ATTR_MESSAGE,
    ATTR_MODE,
    ATTR_PRICE,
    ATTR_PRODUCT_ID,
    ATTR_PRODUCT_NAME,
    ATTR_SERVICE,
    ATTR_SPOILED,
    ATTR_STOCK_AMOUNT,
    BBD_SOURCE_DEFAULT,
    BBD_SOURCE_MANUAL,
    BBD_SOURCE_NEVER,
    BBD_SOURCE_UNSET,
    DOMAIN,
    EVENT_BARCODE_UNKNOWN,
    EVENT_ERROR,
    EVENT_STOCK_ADDED,
    EVENT_STOCK_CONSUMED,
    MODE_MINUS,
    MODE_PLUS,
    NEVER_EXPIRES_DATE,
    SERVICE_ADD_STOCK,
    SERVICE_CONSUME_STOCK,
    SERVICE_SCAN,
)

_AMOUNT = vol.All(vol.Coerce(float), vol.Range(min=0, min_included=False))
_PRODUCT_KEYS = "product"

_BASE = {
    vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
    vol.Optional(ATTR_AMOUNT, default=1): _AMOUNT,
}
_TARGET = {
    vol.Exclusive(ATTR_BARCODE, _PRODUCT_KEYS): cv.string,
    vol.Exclusive(ATTR_PRODUCT_ID, _PRODUCT_KEYS): cv.positive_int,
}

ADD_STOCK_SCHEMA = vol.All(
    vol.Schema(
        {
            **_BASE,
            **_TARGET,
            vol.Optional(ATTR_BEST_BEFORE_DATE): cv.date,
            vol.Optional(ATTR_PRICE): vol.All(vol.Coerce(float), vol.Range(min=0)),
            vol.Optional(ATTR_LOCATION_ID): cv.positive_int,
        }
    ),
    cv.has_at_least_one_key(ATTR_BARCODE, ATTR_PRODUCT_ID),
)

CONSUME_STOCK_SCHEMA = vol.All(
    vol.Schema({**_BASE, **_TARGET, vol.Optional(ATTR_SPOILED, default=False): cv.boolean}),
    cv.has_at_least_one_key(ATTR_BARCODE, ATTR_PRODUCT_ID),
)

SCAN_SCHEMA = vol.Schema(
    {
        **_BASE,
        vol.Required(ATTR_BARCODE): cv.string,
        vol.Required(ATTR_MODE): vol.In([MODE_PLUS, MODE_MINUS]),
    }
)


def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration's services (called once from async_setup)."""

    async def add_stock(call: ServiceCall) -> ServiceResponse:
        return await _run(hass, call, _async_add_stock(hass, _client(hass, call), call.data))

    async def consume_stock(call: ServiceCall) -> ServiceResponse:
        return await _run(hass, call, _async_consume_stock(hass, _client(hass, call), call.data))

    async def scan(call: ServiceCall) -> ServiceResponse:
        client = _client(hass, call)
        if call.data[ATTR_MODE] == MODE_PLUS:
            return await _run(hass, call, _async_add_stock(hass, client, call.data))
        data = {**call.data, ATTR_SPOILED: False}
        return await _run(hass, call, _async_consume_stock(hass, client, data))

    for name, handler, schema in (
        (SERVICE_ADD_STOCK, add_stock, ADD_STOCK_SCHEMA),
        (SERVICE_CONSUME_STOCK, consume_stock, CONSUME_STOCK_SCHEMA),
        (SERVICE_SCAN, scan, SCAN_SCHEMA),
    ):
        hass.services.async_register(
            DOMAIN, name, handler, schema=schema, supports_response=SupportsResponse.OPTIONAL
        )


def _client(hass: HomeAssistant, call: ServiceCall) -> GrocyClient:
    """Return the client of the addressed (or only) loaded config entry."""
    if entry_id := call.data.get(ATTR_CONFIG_ENTRY_ID):
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entry_not_found",
                translation_placeholders={"entry_id": entry_id},
            )
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="not_loaded")
        return entry.runtime_data

    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="not_loaded")
    if len(entries) > 1:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="multiple_entries")
    return entries[0].runtime_data


async def _run(hass: HomeAssistant, call: ServiceCall, coro: Any) -> ServiceResponse:
    """Await a booking; turn Grocy errors into HA errors and fire grocy_ai_error."""
    try:
        return await coro
    except ServiceValidationError:
        raise
    except GrocyError as err:
        hass.bus.async_fire(EVENT_ERROR, {ATTR_SERVICE: call.service, ATTR_MESSAGE: str(err)})
        key = "cannot_connect" if isinstance(err, GrocyConnectionError) else "grocy_error"
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=key,
            translation_placeholders={"message": str(err)},
        ) from err


async def _async_resolve(
    hass: HomeAssistant, client: GrocyClient, data: dict[str, Any], mode: str
) -> dict[str, Any]:
    """Return Grocy product details for the barcode or product id in ``data``."""
    barcode = data.get(ATTR_BARCODE)
    try:
        if barcode:
            return await client.get_product_by_barcode(barcode)
        return await client.get_product(data[ATTR_PRODUCT_ID])
    except GrocyNotFoundError as err:
        if barcode:
            hass.bus.async_fire(EVENT_BARCODE_UNKNOWN, {ATTR_BARCODE: barcode, ATTR_MODE: mode})
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_barcode",
                translation_placeholders={"barcode": barcode},
            ) from err
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unknown_product",
            translation_placeholders={"product_id": str(data[ATTR_PRODUCT_ID])},
        ) from err


def default_best_before(product: dict[str, Any], today: date) -> tuple[date, str]:
    """Best-before date Grocy's UI would use when none is given.

    The API itself would use *today*, so it has to be computed here.
    """
    days = int(float(product.get("default_best_before_days") or 0))
    if days > 0:
        return today + timedelta(days=days), BBD_SOURCE_DEFAULT
    never = date.fromisoformat(NEVER_EXPIRES_DATE)
    return never, BBD_SOURCE_NEVER if days < 0 else BBD_SOURCE_UNSET


async def _async_add_stock(
    hass: HomeAssistant, client: GrocyClient, data: dict[str, Any]
) -> dict[str, Any]:
    details = await _async_resolve(hass, client, data, MODE_PLUS)
    product = details["product"]
    product_id = int(product["id"])

    if (best_before := data.get(ATTR_BEST_BEFORE_DATE)) is not None:
        source = BBD_SOURCE_MANUAL
    else:
        best_before, source = default_best_before(product, dt_util.now().date())

    await client.add_product(
        product_id,
        data[ATTR_AMOUNT],
        best_before,
        price=data.get(ATTR_PRICE),
        location_id=data.get(ATTR_LOCATION_ID),
    )
    after = await client.get_product(product_id)

    result = {
        ATTR_PRODUCT_ID: product_id,
        ATTR_PRODUCT_NAME: product.get("name"),
        ATTR_BARCODE: data.get(ATTR_BARCODE),
        ATTR_AMOUNT: data[ATTR_AMOUNT],
        ATTR_BEST_BEFORE_DATE: best_before.isoformat(),
        ATTR_BEST_BEFORE_SOURCE: source,
        ATTR_STOCK_AMOUNT: _stock_amount(after),
    }
    hass.bus.async_fire(EVENT_STOCK_ADDED, result)
    return result


async def _async_consume_stock(
    hass: HomeAssistant, client: GrocyClient, data: dict[str, Any]
) -> dict[str, Any]:
    details = await _async_resolve(hass, client, data, MODE_MINUS)
    product = details["product"]
    product_id = int(product["id"])

    await client.consume_product(product_id, data[ATTR_AMOUNT], data[ATTR_SPOILED])
    after = await client.get_product(product_id)

    result = {
        ATTR_PRODUCT_ID: product_id,
        ATTR_PRODUCT_NAME: product.get("name"),
        ATTR_BARCODE: data.get(ATTR_BARCODE),
        ATTR_AMOUNT: data[ATTR_AMOUNT],
        ATTR_SPOILED: data[ATTR_SPOILED],
        ATTR_STOCK_AMOUNT: _stock_amount(after),
    }
    hass.bus.async_fire(EVENT_STOCK_CONSUMED, result)
    return result


def _stock_amount(details: dict[str, Any]) -> float:
    return float(details.get("stock_amount") or 0)
