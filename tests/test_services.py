"""Tests for the Grocy AI stock booking services."""

from __future__ import annotations

from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_capture_events
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
import voluptuous as vol

from custom_components.grocy_ai.const import (
    DOMAIN,
    EVENT_BARCODE_UNKNOWN,
    EVENT_ERROR,
    EVENT_STOCK_ADDED,
    EVENT_STOCK_CONSUMED,
)

from .conftest import GROCY_URL, MOCK_CONFIG, SYSTEM_INFO

API = f"{GROCY_URL}/api"
BARCODE = "4006040001234"


def details(product_id: int = 7, best_before_days: Any = 5, stock: float = 2) -> dict:
    """Build a Grocy ProductDetailsResponse."""
    return {
        "product": {
            "id": product_id,
            "name": "Milch",
            "default_best_before_days": best_before_days,
        },
        "stock_amount": stock,
    }


@pytest.fixture
async def setup_entry(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> MockConfigEntry:
    """Set up one loaded Grocy AI entry."""
    aioclient_mock.get(f"{API}/system/info", json=SYSTEM_INFO)
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, unique_id=GROCY_URL)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _posted(aioclient_mock: AiohttpClientMocker, suffix: str) -> dict:
    """Return the JSON body of the POST request whose URL ends with ``suffix``."""
    for method, url, data, _ in aioclient_mock.mock_calls:
        if method.lower() == "post" and str(url).endswith(suffix):
            return data
    raise AssertionError(f"no POST to {suffix}")


@pytest.mark.usefixtures("setup_entry")
async def test_add_stock_by_barcode_uses_default_shelf_life(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer: FrozenDateTimeFactory
) -> None:
    """Without a date the product's default_best_before_days is applied."""
    freezer.move_to("2026-10-25 12:00:00")
    aioclient_mock.get(f"{API}/stock/products/by-barcode/{BARCODE}", json=details())
    aioclient_mock.post(f"{API}/stock/products/7/add", json=[{"id": 1}])
    aioclient_mock.get(f"{API}/stock/products/7", json=details(stock=3))
    events = async_capture_events(hass, EVENT_STOCK_ADDED)

    result = await hass.services.async_call(
        DOMAIN, "add_stock", {"barcode": BARCODE, "amount": 1}, blocking=True, return_response=True
    )

    assert result == {
        "product_id": 7,
        "product_name": "Milch",
        "barcode": BARCODE,
        "amount": 1.0,
        "best_before_date": "2026-10-30",
        "best_before_source": "default",
        "stock_amount": 3.0,
    }
    assert _posted(aioclient_mock, "/stock/products/7/add") == {
        "amount": 1.0,
        "best_before_date": "2026-10-30",
        "transaction_type": "purchase",
    }
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data == result


@pytest.mark.parametrize(
    ("days", "source"),
    [(-1, "never"), (0, "unset"), ("-1", "never"), (None, "unset")],
)
@pytest.mark.usefixtures("setup_entry")
async def test_add_stock_never_expires(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, days: Any, source: str
) -> None:
    """-1 (never) and 0 (no default) are booked as never expiring."""
    aioclient_mock.get(f"{API}/stock/products/7", json=details(best_before_days=days))
    aioclient_mock.post(f"{API}/stock/products/7/add", json=[])

    result = await hass.services.async_call(
        DOMAIN, "add_stock", {"product_id": 7}, blocking=True, return_response=True
    )

    assert result["best_before_date"] == "2999-12-31"
    assert result["best_before_source"] == source


@pytest.mark.usefixtures("setup_entry")
async def test_add_stock_manual_date_price_location(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A given date, price and location are passed through."""
    aioclient_mock.get(f"{API}/stock/products/7", json=details())
    aioclient_mock.post(f"{API}/stock/products/7/add", json=[])

    result = await hass.services.async_call(
        DOMAIN,
        "add_stock",
        {
            "product_id": 7,
            "amount": 2,
            "best_before_date": "2027-01-31",
            "price": 1.29,
            "location_id": 3,
        },
        blocking=True,
        return_response=True,
    )

    assert result["best_before_source"] == "manual"
    assert _posted(aioclient_mock, "/stock/products/7/add") == {
        "amount": 2.0,
        "best_before_date": "2027-01-31",
        "transaction_type": "purchase",
        "price": 1.29,
        "location_id": 3,
    }


@pytest.mark.usefixtures("setup_entry")
async def test_consume_stock(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Consuming books a consume transaction and fires an event."""
    aioclient_mock.get(f"{API}/stock/products/by-barcode/{BARCODE}", json=details())
    aioclient_mock.post(f"{API}/stock/products/7/consume", json=[])
    aioclient_mock.get(f"{API}/stock/products/7", json=details(stock=1))
    events = async_capture_events(hass, EVENT_STOCK_CONSUMED)

    result = await hass.services.async_call(
        DOMAIN,
        "consume_stock",
        {"barcode": BARCODE, "spoiled": True},
        blocking=True,
        return_response=True,
    )

    assert result["stock_amount"] == 1.0
    assert result["spoiled"] is True
    assert _posted(aioclient_mock, "/stock/products/7/consume") == {
        "amount": 1.0,
        "spoiled": True,
        "transaction_type": "consume",
    }
    await hass.async_block_till_done()
    assert len(events) == 1


@pytest.mark.parametrize(("mode", "action"), [("plus", "add"), ("minus", "consume")])
@pytest.mark.usefixtures("setup_entry")
async def test_scan(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mode: str, action: str
) -> None:
    """scan dispatches to add or consume."""
    aioclient_mock.get(f"{API}/stock/products/by-barcode/{BARCODE}", json=details())
    aioclient_mock.post(f"{API}/stock/products/7/{action}", json=[])
    aioclient_mock.get(f"{API}/stock/products/7", json=details())

    await hass.services.async_call(
        DOMAIN, "scan", {"barcode": BARCODE, "mode": mode}, blocking=True, return_response=True
    )

    assert _posted(aioclient_mock, f"/stock/products/7/{action}")["transaction_type"] == (
        "purchase" if mode == "plus" else "consume"
    )


@pytest.mark.usefixtures("setup_entry")
async def test_unknown_barcode(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """An unknown barcode fires grocy_ai_barcode_unknown and raises a validation error."""
    aioclient_mock.get(
        f"{API}/stock/products/by-barcode/{BARCODE}",
        status=400,
        json={"error_message": f"No product with barcode {BARCODE} found"},
    )
    events = async_capture_events(hass, EVENT_BARCODE_UNKNOWN)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, "scan", {"barcode": BARCODE, "mode": "plus"}, blocking=True
        )

    assert err.value.translation_key == "unknown_barcode"
    await hass.async_block_till_done()
    assert events[0].data == {"barcode": BARCODE, "mode": "plus"}


@pytest.mark.usefixtures("setup_entry")
async def test_consume_more_than_stock(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Grocy's error message is surfaced and grocy_ai_error is fired."""
    aioclient_mock.get(f"{API}/stock/products/7", json=details(stock=0))
    aioclient_mock.post(
        f"{API}/stock/products/7/consume",
        status=400,
        json={"error_message": "Amount to be consumed cannot be > current stock amount"},
    )
    events = async_capture_events(hass, EVENT_ERROR)

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(DOMAIN, "consume_stock", {"product_id": 7}, blocking=True)

    assert err.value.translation_key == "grocy_error"
    assert "current stock amount" in err.value.translation_placeholders["message"]
    await hass.async_block_till_done()
    assert events[0].data["service"] == "consume_stock"


@pytest.mark.usefixtures("setup_entry")
@pytest.mark.parametrize(
    "data",
    [
        {},
        {"barcode": BARCODE, "product_id": 7},
        {"barcode": BARCODE, "amount": 0},
    ],
)
async def test_invalid_input(hass: HomeAssistant, data: dict) -> None:
    """Exactly one of barcode/product_id and a positive amount are required."""
    with pytest.raises((vol.Invalid, ServiceValidationError)):
        await hass.services.async_call(DOMAIN, "add_stock", data, blocking=True)


async def test_service_without_entry(hass: HomeAssistant) -> None:
    """Services exist without an entry but report that Grocy AI is not loaded."""
    assert await async_setup_component(hass, DOMAIN, {})
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN, "add_stock", {"product_id": 1}, blocking=True)
    assert err.value.translation_key == "not_loaded"
