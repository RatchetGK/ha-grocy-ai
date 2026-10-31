"""Tests for the panel photo upload, media source and barcode reading."""

from __future__ import annotations

from http import HTTPStatus

from homeassistant.components import media_source
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.grocy_ai.ai import is_valid_gtin
from custom_components.grocy_ai.const import DOMAIN
from custom_components.grocy_ai.photos import DATA_PHOTOS, MEDIA_SOURCE_PREFIX

from .conftest import GROCY_URL, MOCK_CONFIG, SYSTEM_INFO
from .test_ai import mock_ai_task

API = f"{GROCY_URL}/api"
JPEG = b"\xff\xd8\xff\xe0fake-jpeg"


@pytest.fixture
async def entry(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> MockConfigEntry:
    """Loaded entry."""
    aioclient_mock.get(f"{API}/system/info", json=SYSTEM_INFO)
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, unique_id=GROCY_URL)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _upload(hass_client, body: bytes = JPEG, content_type: str = "image/jpeg"):
    client = await hass_client()
    return await client.post(
        "/api/grocy_ai/photo", data=body, headers={"Content-Type": content_type}
    )


@pytest.mark.usefixtures("entry")
async def test_upload_and_media_source(hass: HomeAssistant, hass_client) -> None:
    """An uploaded photo is readable through media-source://grocy_ai/<id>."""
    resp = await _upload(hass_client)
    assert resp.status == HTTPStatus.OK
    image = await resp.json()
    assert image["media_content_id"].startswith(MEDIA_SOURCE_PREFIX)
    assert image["media_content_type"] == "image/jpeg"

    media = await media_source.async_get_media_image(hass, image["media_content_id"])
    assert media is not None
    assert media.content == JPEG
    assert media.mime_type == "image/jpeg"


@pytest.mark.usefixtures("entry")
async def test_upload_rejects_non_images(hass_client) -> None:
    """Only image bodies are accepted."""
    resp = await _upload(hass_client, b"hello", "text/plain")
    assert resp.status == HTTPStatus.BAD_REQUEST


@pytest.mark.usefixtures("entry")
async def test_upload_requires_auth(hass_client_no_auth) -> None:
    """Anonymous uploads are refused."""
    resp = await _upload(hass_client_no_auth)
    assert resp.status == HTTPStatus.UNAUTHORIZED


@pytest.mark.usefixtures("entry")
async def test_photo_is_discarded_after_ai(hass: HomeAssistant, hass_client) -> None:
    """After AI Task has read the photo it is removed from memory."""
    image = await (await _upload(hass_client)).json()
    calls = mock_ai_task(hass, {"best_before_date": "", "confidence": 0})

    await hass.services.async_call(
        DOMAIN, "read_best_before", {"image": image}, blocking=True, return_response=True
    )

    assert calls[0].data["attachments"] == [image]
    photo_id = image["media_content_id"].removeprefix(MEDIA_SOURCE_PREFIX)
    assert hass.data[DATA_PHOTOS].get(photo_id) is None


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        ("4006381333931", True),
        ("96385074", True),
        ("036000291452", True),
        ("4006381333932", False),
        ("40063813339", False),
        ("40063813339a", False),
    ],
)
def test_is_valid_gtin(value: str, valid: bool) -> None:
    """Length and check digit are verified."""
    assert is_valid_gtin(value) is valid


@pytest.mark.usefixtures("entry")
@pytest.mark.parametrize(
    ("ai_data", "expected"),
    [
        (
            {"barcode": "4006381 333931", "confidence": 0.9},
            {"recognized": True, "barcode": "4006381333931"},
        ),
        (
            {"barcode": "4006381333932", "confidence": 0.9},
            {"recognized": False, "barcode": None, "reason": "invalid_barcode"},
        ),
        (
            {"barcode": "", "confidence": 0.9},
            {"recognized": False, "barcode": None, "reason": "no_barcode"},
        ),
        (
            {"barcode": "4006381333931", "confidence": 0.1},
            {"recognized": False, "barcode": None, "reason": "low_confidence"},
        ),
    ],
)
async def test_read_barcode_service(hass: HomeAssistant, ai_data: dict, expected: dict) -> None:
    """read_barcode returns only plausible GTINs."""
    mock_ai_task(hass, ai_data)
    image = {"media_content_id": "media-source://camera/camera.kitchen"}

    result = await hass.services.async_call(
        DOMAIN, "read_barcode", {"image": image}, blocking=True, return_response=True
    )

    assert result == expected
