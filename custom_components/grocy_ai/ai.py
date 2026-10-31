"""Best-before date and barcode recognition from photos via Home Assistant's AI Task."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
import re
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .photos import async_discard_photo

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


BARCODE_INSTRUCTIONS = """Look at the photo of a product package and read the number of its EAN/UPC
barcode (the digits printed below or next to the bars). Return only the digits,
without spaces. If no barcode number is clearly readable, return an empty string.
Return confidence between 0 and 1 for how sure you are about every digit.
"""

BARCODE_STRUCTURE: dict[str, Any] = {
    "barcode": {
        "description": "Barcode digits (EAN-8, UPC-A, EAN-13 or GTIN-14), empty if unreadable",
        "required": True,
        "selector": {"text": {}},
    },
    "confidence": STRUCTURE["confidence"],
}


class BestBeforeError(HomeAssistantError):
    """The best-before date (or barcode) could not be determined from the photo."""

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
    result = await _async_generate(
        hass,
        image,
        ai_task_entity,
        task_name="grocy_ai best-before date",
        instructions=INSTRUCTIONS,
        structure=STRUCTURE,
    )
    return parse_result(result, today)


async def async_read_barcode(
    hass: HomeAssistant, image: dict[str, Any], ai_task_entity: str | None
) -> str:
    """Ask the AI Task entity to read the barcode number from ``image``.

    Only numbers with a valid GTIN check digit are accepted, so a misread digit
    never books the wrong product.
    """
    result = await _async_generate(
        hass,
        image,
        ai_task_entity,
        task_name="grocy_ai barcode",
        instructions=BARCODE_INSTRUCTIONS,
        structure=BARCODE_STRUCTURE,
    )
    barcode = re.sub(r"[\s-]", "", str(result.get("barcode") or ""))
    if not barcode:
        raise BestBeforeError("no_barcode")
    if not is_valid_gtin(barcode):
        raise BestBeforeError("invalid_barcode")
    if _confidence(result) < MIN_CONFIDENCE:
        raise BestBeforeError("low_confidence")
    return barcode


async def _async_generate(
    hass: HomeAssistant,
    image: dict[str, Any],
    ai_task_entity: str | None,
    *,
    task_name: str,
    instructions: str,
    structure: dict[str, Any],
) -> dict[str, Any]:
    """Run ai_task.generate_data with one image; uploaded photos are dropped afterwards."""
    if not hass.services.has_service(AI_TASK_DOMAIN, AI_TASK_SERVICE):
        raise BestBeforeError("ai_task_unavailable")

    data: dict[str, Any] = {
        "task_name": task_name,
        "instructions": instructions,
        "structure": structure,
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
    finally:
        async_discard_photo(hass, image["media_content_id"])

    result = (response or {}).get("data")
    if not isinstance(result, dict):
        raise BestBeforeError("no_structured_result")
    return result


def is_valid_gtin(value: str) -> bool:
    """Check length and check digit of an EAN-8/UPC-A/EAN-13/GTIN-14 number."""
    if not value.isdigit() or len(value) not in (8, 12, 13, 14):
        return False
    digits = [int(c) for c in reversed(value[:-1])]
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(digits))
    return (10 - total % 10) % 10 == int(value[-1])


def _confidence(result: dict[str, Any]) -> float:
    try:
        return float(result.get("confidence") or 0)
    except TypeError, ValueError:
        return 0.0


def parse_result(result: dict[str, Any], today: date) -> BestBeforeResult:
    """Validate the structured AI result."""
    confidence = _confidence(result)
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
