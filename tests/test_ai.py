"""Tests for best-before date recognition (parsing and AI Task call)."""

from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_capture_events
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.grocy_ai.ai import BestBeforeError, parse_best_before, parse_result
from custom_components.grocy_ai.const import DOMAIN, EVENT_BEST_BEFORE_FAILED

from .conftest import GROCY_URL, MOCK_CONFIG, SYSTEM_INFO

API = f"{GROCY_URL}/api"
TODAY = date(2026, 10, 29)
IMAGE = {
    "media_content_id": "media-source://camera/camera.kitchen",
    "media_content_type": "image/jpeg",
}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-11-05", date(2026, 11, 5)),
        ("2026-12", date(2026, 12, 31)),
        ("05.11.2026", date(2026, 11, 5)),
        ("5.11.26", date(2026, 11, 5)),
        ("12/2026", date(2026, 12, 31)),
        ("02.28", date(2028, 2, 29)),
        ("31.02.2026", None),
        ("2026-13", None),
        ("", None),
        ("best before soon", None),
    ],
)
def test_parse_best_before(value: str, expected: date | None) -> None:
    """Common German packaging formats are understood; month-only = end of month."""
    assert parse_best_before(value) == expected


@pytest.mark.parametrize(
    ("result", "reason"),
    [
        ({"best_before_date": "", "confidence": 0.9}, "no_date"),
        ({"best_before_date": "2026-11-05", "confidence": 0.2}, "low_confidence"),
        ({"best_before_date": "2026-11-05", "confidence": "high"}, "low_confidence"),
        ({"best_before_date": "2020-01-01", "confidence": 0.9}, "implausible_date"),
        ({"best_before_date": "2099-01-01", "confidence": 0.9}, "implausible_date"),
    ],
)
def test_parse_result_rejects(result: dict, reason: str) -> None:
    """Unusable AI answers raise BestBeforeError with a reason."""
    with pytest.raises(BestBeforeError) as err:
        parse_result(result, TODAY)
    assert err.value.reason == reason


def test_parse_result_ok() -> None:
    """A confident, plausible answer is accepted."""
    res = parse_result(
        {"best_before_date": "2026-11-05", "confidence": 0.876, "product_name": " Milch "}, TODAY
    )
    assert res.as_dict() == {
        "best_before_date": "2026-11-05",
        "product_name": "Milch",
        "confidence": 0.88,
    }


def mock_ai_task(hass: HomeAssistant, data: Any) -> list[ServiceCall]:
    """Register a fake ai_task.generate_data returning ``data``."""
    calls: list[ServiceCall] = []

    async def handler(call: ServiceCall) -> dict:
        calls.append(call)
        return {"conversation_id": "x", "data": data}

    hass.services.async_register(
        "ai_task", "generate_data", handler, supports_response=SupportsResponse.ONLY
    )
    return calls


@pytest.fixture
async def entry(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> MockConfigEntry:
    """Loaded entry with a configured AI Task entity."""
    aioclient_mock.get(f"{API}/system/info", json=SYSTEM_INFO)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id=GROCY_URL,
        options={"ai_task_entity": "ai_task.example"},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _details(days: int = 5) -> dict:
    return {
        "product": {"id": 7, "name": "Milch", "default_best_before_days": days},
        "stock_amount": 1,
    }


@pytest.mark.usefixtures("entry")
async def test_read_best_before_service(hass: HomeAssistant, freezer) -> None:
    """read_best_before sends the photo to AI Task and returns the date."""
    freezer.move_to("2026-10-29 12:00:00")
    calls = mock_ai_task(hass, {"best_before_date": "05.11.26", "confidence": 0.95})

    result = await hass.services.async_call(
        DOMAIN, "read_best_before", {"image": IMAGE}, blocking=True, return_response=True
    )

    assert result == {
        "recognized": True,
        "best_before_date": "2026-11-05",
        "product_name": None,
        "confidence": 0.95,
    }
    sent = calls[0].data
    assert sent["entity_id"] == "ai_task.example"
    assert sent["attachments"] == [IMAGE]
    assert "best_before_date" in sent["structure"]


@pytest.mark.usefixtures("entry")
async def test_read_best_before_without_ai_task(hass: HomeAssistant) -> None:
    """Without any AI Task the service answers recognized=False instead of failing."""
    result = await hass.services.async_call(
        DOMAIN, "read_best_before", {"image": IMAGE}, blocking=True, return_response=True
    )
    assert result == {
        "recognized": False,
        "best_before_date": None,
        "reason": "ai_task_unavailable",
    }


@pytest.mark.usefixtures("entry")
async def test_add_stock_with_photo(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer
) -> None:
    """A readable photo sets the best-before date (source ai)."""
    freezer.move_to("2026-10-29 12:00:00")
    mock_ai_task(hass, {"best_before_date": "2026-11-20", "confidence": 0.9})
    aioclient_mock.get(f"{API}/stock/products/7", json=_details())
    aioclient_mock.post(f"{API}/stock/products/7/add", json=[])

    result = await hass.services.async_call(
        DOMAIN,
        "add_stock",
        {"product_id": 7, "image": IMAGE},
        blocking=True,
        return_response=True,
    )

    assert result["best_before_date"] == "2026-11-20"
    assert result["best_before_source"] == "ai"
    assert result["ai_confidence"] == 0.9


@pytest.mark.usefixtures("entry")
async def test_add_stock_photo_unreadable_falls_back(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer
) -> None:
    """An unreadable photo never blocks the booking: default shelf life + event."""
    freezer.move_to("2026-10-29 12:00:00")
    mock_ai_task(hass, {"best_before_date": "", "confidence": 0})
    aioclient_mock.get(f"{API}/stock/products/7", json=_details(days=5))
    aioclient_mock.post(f"{API}/stock/products/7/add", json=[])
    failed = async_capture_events(hass, EVENT_BEST_BEFORE_FAILED)

    result = await hass.services.async_call(
        DOMAIN,
        "add_stock",
        {"product_id": 7, "image": IMAGE},
        blocking=True,
        return_response=True,
    )

    assert result["best_before_date"] == "2026-11-03"
    assert result["best_before_source"] == "default"
    assert result["ai_error"] == "no_date"
    await hass.async_block_till_done()
    assert failed[0].data == {"product_id": 7, "barcode": None, "reason": "no_date"}


@pytest.mark.usefixtures("entry")
async def test_manual_date_wins_over_photo(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """With an explicit best_before_date the AI is not asked."""
    calls = mock_ai_task(hass, {"best_before_date": "2026-11-20", "confidence": 0.9})
    aioclient_mock.get(f"{API}/stock/products/7", json=_details())
    aioclient_mock.post(f"{API}/stock/products/7/add", json=[])

    result = await hass.services.async_call(
        DOMAIN,
        "add_stock",
        {"product_id": 7, "image": IMAGE, "best_before_date": "2027-01-01"},
        blocking=True,
        return_response=True,
    )

    assert result["best_before_source"] == "manual"
    assert not calls
