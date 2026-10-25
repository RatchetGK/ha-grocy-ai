"""Config and options flow for Grocy AI."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .api import GrocyAuthError, GrocyClient, GrocyConnectionError, GrocyError, normalize_url
from .const import (
    CONF_AI_TASK_ENTITY,
    CONF_EXPIRY_DAYS,
    CONF_NOTIFY_SERVICE,
    CONF_TODO_ENTITY,
    DEFAULT_EXPIRY_DAYS,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
        ),
        vol.Required(CONF_API_KEY): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
        vol.Required(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
    }
)


async def _async_validate(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the connection; return Grocy system info."""
    client = GrocyClient(
        async_get_clientsession(hass, verify_ssl=data[CONF_VERIFY_SSL]),
        data[CONF_URL],
        data[CONF_API_KEY],
        data[CONF_VERIFY_SSL],
    )
    return await client.get_system_info()


class GrocyAiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Grocy AI."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_URL] = normalize_url(user_input[CONF_URL])
            await self.async_set_unique_id(user_input[CONF_URL].lower())
            self._abort_if_unique_id_configured()
            try:
                await _async_validate(self.hass, user_input)
            except GrocyAuthError:
                errors["base"] = "invalid_auth"
            except GrocyConnectionError:
                errors["base"] = "cannot_connect"
            except GrocyError:
                _LOGGER.exception("Unexpected response from Grocy")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title="Grocy AI", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(STEP_USER_DATA_SCHEMA, user_input),
            errors=errors,
            description_placeholders={"url_example": "http://homeassistant.local:9192"},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> GrocyAiOptionsFlow:
        """Return the options flow."""
        return GrocyAiOptionsFlow()


class GrocyAiOptionsFlow(OptionsFlow):
    """Options: expiry lead time, notify service, to-do list, AI Task entity."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        notify_services = sorted(
            f"notify.{name}"
            for name in self.hass.services.async_services_for_domain("notify")
            if name not in ("send_message", "persistent_notification")
        )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_EXPIRY_DAYS, default=DEFAULT_EXPIRY_DAYS
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=60, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(CONF_NOTIFY_SERVICE): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=notify_services,
                        custom_value=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_TODO_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="todo")
                ),
                vol.Optional(CONF_AI_TASK_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="ai_task")
                ),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, self.config_entry.options),
        )
