"""Constants for the Grocy AI integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "grocy_ai"

# Options
CONF_EXPIRY_DAYS: Final = "expiry_days"
CONF_NOTIFY_SERVICE: Final = "notify_service"
CONF_TODO_ENTITY: Final = "todo_entity"
CONF_AI_TASK_ENTITY: Final = "ai_task_entity"

DEFAULT_EXPIRY_DAYS: Final = 3
DEFAULT_VERIFY_SSL: Final = True
DEFAULT_TIMEOUT: Final = 10
