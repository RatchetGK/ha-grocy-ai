"""Tests for Grocy AI setup and unload."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.grocy_ai.api import GrocyClient
from custom_components.grocy_ai.const import DOMAIN

from .conftest import GROCY_URL, MOCK_CONFIG, SYSTEM_INFO

INFO_URL = f"{GROCY_URL}/api/system/info"


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, unique_id=GROCY_URL)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_setup_and_unload(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """The entry loads with a working Grocy and unloads cleanly."""
    aioclient_mock.get(INFO_URL, json=SYSTEM_INFO)
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert isinstance(entry.runtime_data, GrocyClient)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retry_when_offline(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """An unreachable Grocy leads to a setup retry."""
    aioclient_mock.get(INFO_URL, exc=TimeoutError())
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_error_on_bad_key(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A rejected API key is a permanent setup error."""
    aioclient_mock.get(INFO_URL, status=401)
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR
