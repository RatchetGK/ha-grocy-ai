"""Tests for the Grocy AI config and options flow."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.grocy_ai.const import (
    CONF_AI_TASK_ENTITY,
    CONF_EXPIRY_DAYS,
    CONF_NOTIFY_SERVICE,
    CONF_TODO_ENTITY,
    DOMAIN,
)

from .conftest import GROCY_URL, MOCK_CONFIG, SYSTEM_INFO

INFO_URL = f"{GROCY_URL}/api/system/info"


async def test_user_flow_success(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """A valid URL and key create an entry; the URL is normalized."""
    aioclient_mock.get(INFO_URL, json=SYSTEM_INFO)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**MOCK_CONFIG, CONF_URL: f" {GROCY_URL}/api/ "}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Grocy AI"
    assert result["data"] == MOCK_CONFIG
    assert aioclient_mock.mock_calls[0][3]["GROCY-API-KEY"] == MOCK_CONFIG["api_key"]


@pytest.mark.parametrize(
    ("mock_kwargs", "error"),
    [
        ({"status": 401}, "invalid_auth"),
        ({"exc": TimeoutError()}, "cannot_connect"),
        ({"status": 500}, "unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_kwargs: dict, error: str
) -> None:
    """Errors are shown and the flow can recover."""
    aioclient_mock.get(INFO_URL, **mock_kwargs)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], MOCK_CONFIG)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    aioclient_mock.clear_requests()
    aioclient_mock.get(INFO_URL, json=SYSTEM_INFO)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], MOCK_CONFIG)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(hass: HomeAssistant) -> None:
    """The same Grocy URL cannot be added twice."""
    MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, unique_id=GROCY_URL).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], MOCK_CONFIG)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Options are stored and the entry is reloaded."""
    aioclient_mock.get(INFO_URL, json=SYSTEM_INFO)
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, unique_id=GROCY_URL)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    options = {
        CONF_EXPIRY_DAYS: 5,
        CONF_NOTIFY_SERVICE: "notify.mobile_app_phone",
        CONF_TODO_ENTITY: "todo.shopping_list",
        CONF_AI_TASK_ENTITY: "ai_task.example",
    }
    result = await hass.config_entries.options.async_configure(result["flow_id"], options)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == options
