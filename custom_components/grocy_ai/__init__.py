"""The Grocy AI integration."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .api import GrocyAuthError, GrocyClient, GrocyError
from .const import DEFAULT_VERIFY_SSL, DOMAIN, PANEL_ELEMENT, PANEL_URL_PATH, STATIC_URL
from .photos import async_setup_photos
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PANEL_FILE = Path(__file__).parent / "frontend" / "grocy-ai-panel.js"

type GrocyAiConfigEntry = ConfigEntry[GrocyClient]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register services, photo upload and panel files once."""
    async_setup_services(hass)
    async_setup_photos(hass)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(f"{STATIC_URL}/{PANEL_FILE.name}", str(PANEL_FILE), False)]
    )
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
    await _async_register_panel(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GrocyAiConfigEntry) -> bool:
    """Unload a config entry; drop the panel with the last entry."""
    if "frontend" in hass.config.components and not [
        e for e in hass.config_entries.async_loaded_entries(DOMAIN) if e.entry_id != entry.entry_id
    ]:
        from homeassistant.components import frontend  # noqa: PLC0415

        frontend.async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)
    return True


async def _async_register_panel(hass: HomeAssistant) -> None:
    """Add the mobile "Grocy AI" page to the sidebar (all users, not only admins)."""
    if "frontend" not in hass.config.components:
        return
    from homeassistant.components import frontend  # noqa: PLC0415

    version = (await async_get_integration(hass, DOMAIN)).version
    frontend.async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title="Grocy AI",
        sidebar_icon="mdi:barcode-scan",
        frontend_url_path=PANEL_URL_PATH,
        config={
            "_panel_custom": {
                "name": PANEL_ELEMENT,
                "module_url": f"{STATIC_URL}/{PANEL_FILE.name}?v={version}",
                "embed_iframe": False,
                "trust_external": False,
            }
        },
        require_admin=False,
        update=True,
    )


async def _async_update_listener(hass: HomeAssistant, entry: GrocyAiConfigEntry) -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
