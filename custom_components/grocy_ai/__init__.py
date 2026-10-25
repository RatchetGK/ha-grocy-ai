"""The Grocy AI integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import GrocyAuthError, GrocyClient, GrocyError
from .const import DEFAULT_VERIFY_SSL, DOMAIN
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type GrocyAiConfigEntry = ConfigEntry[GrocyClient]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register services once, independent of config entries."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: GrocyAiConfigEntry) -> bool:
    """Set up Grocy AI from a config entry."""
    verify_ssl = entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
    client = GrocyClient(
        async_get_clientsession(hass, verify_ssl=verify_ssl),
        entry.data[CONF_URL],
        entry.data[CONF_API_KEY],
        verify_ssl,
    )
    try:
        await client.get_system_info()
    except GrocyAuthError as err:
        # TODO(M6): switch to ConfigEntryAuthFailed once a reauth flow exists.
        raise ConfigEntryError("Grocy rejected the API key") from err
    except GrocyError as err:
        raise ConfigEntryNotReady(str(err)) from err

    entry.runtime_data = client
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GrocyAiConfigEntry) -> bool:
    """Unload a config entry."""
    return True


async def _async_update_listener(hass: HomeAssistant, entry: GrocyAiConfigEntry) -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
