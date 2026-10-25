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

# Services
SERVICE_ADD_STOCK: Final = "add_stock"
SERVICE_CONSUME_STOCK: Final = "consume_stock"
SERVICE_SCAN: Final = "scan"

ATTR_CONFIG_ENTRY_ID: Final = "config_entry_id"
ATTR_BARCODE: Final = "barcode"
ATTR_PRODUCT_ID: Final = "product_id"
ATTR_PRODUCT_NAME: Final = "product_name"
ATTR_AMOUNT: Final = "amount"
ATTR_BEST_BEFORE_DATE: Final = "best_before_date"
ATTR_BEST_BEFORE_SOURCE: Final = "best_before_source"
ATTR_PRICE: Final = "price"
ATTR_LOCATION_ID: Final = "location_id"
ATTR_SPOILED: Final = "spoiled"
ATTR_STOCK_AMOUNT: Final = "stock_amount"
ATTR_MODE: Final = "mode"
ATTR_SERVICE: Final = "service"
ATTR_MESSAGE: Final = "message"

MODE_PLUS: Final = "plus"
MODE_MINUS: Final = "minus"

# Where the best-before date of a booking came from.
BBD_SOURCE_MANUAL: Final = "manual"
BBD_SOURCE_DEFAULT: Final = "default"  # product's default_best_before_days
BBD_SOURCE_NEVER: Final = "never"  # product is configured to never expire (-1)
BBD_SOURCE_UNSET: Final = "unset"  # product has no default (0) -> booked as never expiring

# Grocy's "never expires" date.
NEVER_EXPIRES_DATE: Final = "2999-12-31"

# Events
EVENT_STOCK_ADDED: Final = "grocy_ai_stock_added"
EVENT_STOCK_CONSUMED: Final = "grocy_ai_stock_consumed"
EVENT_BARCODE_UNKNOWN: Final = "grocy_ai_barcode_unknown"
EVENT_ERROR: Final = "grocy_ai_error"
