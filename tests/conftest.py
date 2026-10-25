"""Shared fixtures for Grocy AI tests."""

from __future__ import annotations

from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
import pytest

GROCY_URL = "http://grocy.local:9192"
API_KEY = "test-api-key"  # dummy value, never a real key
SYSTEM_INFO = {"grocy_version": {"Version": "4.5.0"}}

MOCK_CONFIG = {CONF_URL: GROCY_URL, CONF_API_KEY: API_KEY, CONF_VERIFY_SSL: True}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading custom integrations in all tests."""
    return
