"""Best-before date recognition from a photo via Home Assistant's AI Task."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
import re
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

AI_TASK_DOMAIN = "ai_task"
AI_TASK_SERVICE = "generate_data"

# Below this confidence a recognized date is not trusted.
MIN_CONFIDENCE = 0.5
# Plausible window for a best-before date on a product that is being bought/checked.
MAX_PAST = timedelta(days=30)
MAX_FUTURE = timedelta(days=365 * 15)

INSTRUCTIONS = """\
Look at the photo of a grocery or household product and find its best-before or
use-by date (German: "mindestens haltbar bis", "MHD", "zu verbrauchen bis";
also "EXP", "BBE", "best before"). Ignore production dates, lot/batch numbers,
prices and times.

Return best_before_date in ISO format YYYY-MM-DD. If only month and year are
printed (e.g. "12/2026" or "12.26"), return YYYY-MM. If no such date is clearly
readable, return an empty string.
Return product_name only if it is printed clearly, otherwise an empty string.
Return confidence between 0 and 1 for how sure you are about the date.
"""

STRUCTURE: dict[str, Any] = {
    "best_before_date": {
        "description": "Best-before/use-by date as YYYY-MM-DD or YYYY-MM, empty if unreadable",
        "required": True,
        "selector": {"text": {}},
    },
    "product_name": {
        "description": "Product name if clearly printed, otherwise empty",
        "required": False,
        "selector": {"text": {}},
    },
    "confidence": {
        "description": "Confidence for the date between 0 and 1",
        "required": True,
        "selector": {"number": {"min": 0, "max": 1, "step": 0.01}},
    },
}


class BestBeforeError(HomeAssistantError):
    """The best-before date could not be determined from the photo."""

    def __init__(self, reason: str) -> None:
        """Store a short machine-readable reason."""
        super().__init__(reason)
        self.reason = reason


@dataclass(slots=True)
class BestBeforeResult:
    """Recognized best-before date."""

    best_before_date: date
    product_name: str | None
    confidence: float

    def as_dict(self) -> dict[str, Any]:
        """Serialize for service responses and events."""
        return {
            "best_before_date": self.best_before_date.isoformat(),
            "product_name": self.product_name,
            "confidence": self.confidence,
        }


async def async_read_best_before(
    hass: HomeAssistant,
    image: dict[str, Any],
    ai_task_entity: str | None,
    today: date,
) -> BestBeforeResult:
    """Ask the AI Task entity to read the best-before date from ``image``.

    ``image`` is a media selector value (``media_content_id`` and
    ``media_content_type``). Raises BestBeforeError when nothing usable comes back.
    """
    if not hass.services.has_service(AI_TASK_DOMAIN, AI_TASK_SERVICE):
        raise BestBeforeError("ai_task_unavailable")

    data: dict[str, Any] = {
        "task_name": "grocy_ai best-before date",
        "instructions": INSTRUCTIONS,
        "structure": STRUCTURE,
        "attachments": [
            {
                "media_content_id": image["media_content_id"],
                "media_content_type": image.get("media_content_type") or "image/jpeg",
            }
        ],
    }
    if ai_task_entity:
        data["entity_id"] = ai_task_entity

    try:
        response = await hass.services.async_call(
            AI_TASK_DOMAIN, AI_TASK_SERVICE, data, blocking=True, return_response=True
        )
    except HomeAssistantError as err:
        raise BestBeforeError(f"ai_task_failed: {err}") from err

    result = (response or {}).get("data")
    if not isinstance(result, dict):
        raise BestBeforeError("no_structured_result")
    return parse_result(result, today)


def parse_result(result: dict[str, Any], today: date) -> BestBeforeResult:
    """Validate the structured AI result."""
    try:
        confidence = float(result.get("confidence") or 0)
    except TypeError, ValueError:
        confidence = 0.0
    parsed = parse_best_before(str(result.get("best_before_date") or ""))
    if parsed is None:
        raise BestBeforeError("no_date")
    if confidence < MIN_CONFIDENCE:
        raise BestBeforeError("low_confidence")
    if not today - MAX_PAST <= parsed <= today + MAX_FUTURE:
        raise BestBeforeError("implausible_date")
    name = str(result.get("product_name") or "").strip() or None
    return BestBeforeResult(parsed, name, round(confidence, 2))


_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
_ISO_MONTH = re.compile(r"^(\d{4})-(\d{1,2})$")
_DMY = re.compile(r"^(\d{1,2})[./-](\d{1,2})[./-](\d{2}|\d{4})$")
_MY = re.compile(r"^(\d{1,2})[./-](\d{2}|\d{4})$")


def parse_best_before(value: str) -> date | None:
    """Parse the date formats commonly printed on German packaging.

    Month-only dates (``12/2026``) mean the end of that month.
    """
    value = value.strip()
    try:
        if m := _ISO.match(value):
            return date(int(m[1]), int(m[2]), int(m[3]))
        if m := _ISO_MONTH.match(value):
            return _end_of_month(int(m[1]), int(m[2]))
        if m := _DMY.match(value):
            return date(_year(m[3]), int(m[2]), int(m[1]))
        if m := _MY.match(value):
            return _end_of_month(_year(m[2]), int(m[1]))
    except ValueError:
        return None
    return None


def _year(value: str) -> int:
    return 2000 + int(value) if len(value) == 2 else int(value)


def _end_of_month(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])
