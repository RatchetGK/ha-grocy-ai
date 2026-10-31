"""Services for booking Grocy stock and reading best-before dates from photos."""

from __future__ import annotations

from datetime import date, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util
import voluptuous as vol

from .ai import BestBeforeError, async_read_barcode, async_read_best_before
from .api import (
    GrocyApiError,
    GrocyClient,
    GrocyConnectionError,
    GrocyError,
    GrocyNotFoundError,
)
from .const import (
    ATTR_AI_CONFIDENCE,
    ATTR_AI_ERROR,
    ATTR_AMOUNT,
    ATTR_BARCODE,
    ATTR_BEST_BEFORE_DATE,
    ATTR_BEST_BEFORE_SOURCE,
    ATTR_CONFIG_ENTRY_ID,
    ATTR_IMAGE,
    ATTR_LOCATION_ID,
    ATTR_MESSAGE,
    ATTR_MODE,
    ATTR_PRICE,
    ATTR_PRODUCT_CREATED,
    ATTR_PRODUCT_ID,
    ATTR_PRODUCT_NAME,
    ATTR_REASON,
    ATTR_RECOGNIZED,
    ATTR_SERVICE,
    ATTR_SPOILED,
    ATTR_STOCK_AMOUNT,
    BBD_SOURCE_AI,
    BBD_SOURCE_DEFAULT,
    BBD_SOURCE_MANUAL,
    BBD_SOURCE_NEVER,
    BBD_SOURCE_UNSET,
    CONF_AI_TASK_ENTITY,
    CONF_EXTERNAL_LOOKUP,
    DEFAULT_EXTERNAL_LOOKUP,
    DOMAIN,
    EVENT_BARCODE_UNKNOWN,
    EVENT_BEST_BEFORE_FAILED,
    EVENT_ERROR,
    EVENT_PRODUCT_CREATED,
    EVENT_STOCK_ADDED,
    EVENT_STOCK_CONSUMED,
    MODE_MINUS,
    MODE_PLUS,
    NEVER_EXPIRES_DATE,
    SERVICE_ADD_STOCK,
    SERVICE_CONSUME_STOCK,
    SERVICE_READ_BARCODE,
    SERVICE_READ_BEST_BEFORE,
    SERVICE_SCAN,
)

_LOGGER = logging.getLogger(__name__)

_AMOUNT = vol.All(vol.Coerce(float), vol.Range(min=0, min_included=False))
_PRODUCT_KEYS = "product"

_BASE = {
    vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
    vol.Optional(ATTR_AMOUNT, default=1): _AMOUNT,
}
# Value of a media selector, e.g. {"media_content_id": "media-source://camera/camera.x",
# "media_content_type": "image/jpeg"}.
_IMAGE = vol.Schema(
    {
        vol.Required("media_content_id"): cv.string,
        vol.Optional("media_content_type"): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)

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
            vol.Optional(ATTR_IMAGE): _IMAGE,
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
        vol.Optional(ATTR_IMAGE): _IMAGE,
    }
)

READ_IMAGE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_IMAGE): _IMAGE,
    }
)


def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration's services (called once from async_setup)."""

    async def add_stock(call: ServiceCall) -> ServiceResponse:
        return await _run(hass, call, _async_add_stock(hass, _entry(hass, call), call.data))

    async def consume_stock(call: ServiceCall) -> ServiceResponse:
        client = _entry(hass, call).runtime_data
        return await _run(hass, call, _async_consume_stock(hass, client, call.data))

    async def scan(call: ServiceCall) -> ServiceResponse:
        entry = _entry(hass, call)
        if call.data[ATTR_MODE] == MODE_PLUS:
            return await _run(hass, call, _async_add_stock(hass, entry, call.data))
        data = {**call.data, ATTR_SPOILED: False}
        return await _run(hass, call, _async_consume_stock(hass, entry.runtime_data, data))

    async def read_best_before(call: ServiceCall) -> ServiceResponse:
        entry = _entry(hass, call)
        try:
            result = await async_read_best_before(
                hass,
                call.data[ATTR_IMAGE],
                entry.options.get(CONF_AI_TASK_ENTITY),
                dt_util.now().date(),
            )
        except BestBeforeError as err:
            return {ATTR_RECOGNIZED: False, ATTR_BEST_BEFORE_DATE: None, ATTR_REASON: err.reason}
        return {ATTR_RECOGNIZED: True, **result.as_dict()}

    async def read_barcode(call: ServiceCall) -> ServiceResponse:
        entry = _entry(hass, call)
        try:
            barcode = await async_read_barcode(
                hass, call.data[ATTR_IMAGE], entry.options.get(CONF_AI_TASK_ENTITY)
            )
        except BestBeforeError as err:
            return {ATTR_RECOGNIZED: False, ATTR_BARCODE: None, ATTR_REASON: err.reason}
        return {ATTR_RECOGNIZED: True, ATTR_BARCODE: barcode}

    for name, handler, schema in (
        (SERVICE_ADD_STOCK, add_stock, ADD_STOCK_SCHEMA),
        (SERVICE_CONSUME_STOCK, consume_stock, CONSUME_STOCK_SCHEMA),
        (SERVICE_SCAN, scan, SCAN_SCHEMA),
    ):
        hass.services.async_register(
            DOMAIN, name, handler, schema=schema, supports_response=SupportsResponse.OPTIONAL
        )
    for name, handler in (
        (SERVICE_READ_BEST_BEFORE, read_best_before),
        (SERVICE_READ_BARCODE, read_barcode),
    ):
        hass.services.async_register(
            DOMAIN,
            name,
            handler,
            schema=READ_IMAGE_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )


def _entry(hass: HomeAssistant, call: ServiceCall) -> ConfigEntry[GrocyClient]:
    """Return the addressed (or only) loaded config entry."""
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
        return entry

    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="not_loaded")
    if len(entries) > 1:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="multiple_entries")
    return entries[0]


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
    hass: HomeAssistant,
    client: GrocyClient,
    data: dict[str, Any],
    mode: str,
    lookup: bool = False,
) -> tuple[dict[str, Any], bool]:
    """Return (product details, created) for the barcode or product id in ``data``.

    With ``lookup`` an unknown barcode is looked up externally (Open Food Facts
    via Grocy) and created in Grocy.
    """
    barcode = data.get(ATTR_BARCODE)
    try:
        if barcode:
            return await client.get_product_by_barcode(barcode), False
        return await client.get_product(data[ATTR_PRODUCT_ID]), False
    except GrocyNotFoundError as err:
        if barcode and lookup and (created := await _async_lookup(hass, client, barcode)):
            return created, True
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


async def _async_lookup(
    hass: HomeAssistant, client: GrocyClient, barcode: str
) -> dict[str, Any] | None:
    """Create an unknown product via Grocy's external barcode lookup."""
    try:
        found = await client.external_lookup(barcode)
    except GrocyApiError as err:
        _LOGGER.warning("External barcode lookup for %s failed: %s", barcode, err)
        return None
    if found is None:
        return None
    details = await client.get_product(int(found["id"]))
    hass.bus.async_fire(
        EVENT_PRODUCT_CREATED,
        {
            ATTR_PRODUCT_ID: int(found["id"]),
            ATTR_PRODUCT_NAME: details["product"].get("name"),
            ATTR_BARCODE: barcode,
        },
    )
    return details


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
    hass: HomeAssistant, entry: ConfigEntry[GrocyClient], data: dict[str, Any]
) -> dict[str, Any]:
    client = entry.runtime_data
    lookup = entry.options.get(CONF_EXTERNAL_LOOKUP, DEFAULT_EXTERNAL_LOOKUP)
    details, created = await _async_resolve(hass, client, data, MODE_PLUS, lookup)
    product = details["product"]
    product_id = int(product["id"])

    today = dt_util.now().date()
    extra: dict[str, Any] = {}
    if (best_before := data.get(ATTR_BEST_BEFORE_DATE)) is not None:
        source = BBD_SOURCE_MANUAL
    elif (image := data.get(ATTR_IMAGE)) is not None:
        try:
            recognized = await async_read_best_before(
                hass, image, entry.options.get(CONF_AI_TASK_ENTITY), today
            )
        except BestBeforeError as err:
            # Never block the booking: fall back to the product's default shelf life.
            hass.bus.async_fire(
                EVENT_BEST_BEFORE_FAILED,
                {
                    ATTR_PRODUCT_ID: product_id,
                    ATTR_BARCODE: data.get(ATTR_BARCODE),
                    ATTR_REASON: err.reason,
                },
            )
            best_before, source = default_best_before(product, today)
            extra[ATTR_AI_ERROR] = err.reason
        else:
            best_before, source = recognized.best_before_date, BBD_SOURCE_AI
            extra[ATTR_AI_CONFIDENCE] = recognized.confidence
    else:
        best_before, source = default_best_before(product, today)

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
        ATTR_PRODUCT_CREATED: created,
        **extra,
    }
    hass.bus.async_fire(EVENT_STOCK_ADDED, result)
    return result


async def _async_consume_stock(
    hass: HomeAssistant, client: GrocyClient, data: dict[str, Any]
) -> dict[str, Any]:
    details, _ = await _async_resolve(hass, client, data, MODE_MINUS)
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
