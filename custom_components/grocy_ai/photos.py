"""Short-lived in-memory photo store for the mobile panel.

The panel uploads a camera photo to ``/api/grocy_ai/photo`` and gets back a
media source id (``media-source://grocy_ai/<id>``) that AI Task can read. Photos
never touch the disk: they live in memory, expire after a few minutes and are
removed right after the AI has read them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from http import HTTPStatus
import secrets
import time

from aiohttp import web
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN

MEDIA_SOURCE_PREFIX = f"media-source://{DOMAIN}/"
PHOTO_TTL = 600  # seconds
MAX_PHOTOS = 10
MAX_PHOTO_BYTES = 8 * 1024 * 1024

DATA_PHOTOS: HassKey[PhotoStore] = HassKey(f"{DOMAIN}_photos")


@dataclass(slots=True)
class Photo:
    """An uploaded photo."""

    content: bytes
    mime_type: str
    created: float = field(default_factory=time.monotonic)


class PhotoStore:
    """Keeps a few recent photos in memory."""

    def __init__(self) -> None:
        """Start empty."""
        self._photos: dict[str, Photo] = {}

    def add(self, content: bytes, mime_type: str) -> str:
        """Store a photo and return its id."""
        self._purge()
        while len(self._photos) >= MAX_PHOTOS:
            self._photos.pop(next(iter(self._photos)))
        photo_id = secrets.token_hex(16)
        self._photos[photo_id] = Photo(content, mime_type)
        return photo_id

    def get(self, photo_id: str) -> Photo | None:
        """Return a photo that has not expired yet."""
        self._purge()
        return self._photos.get(photo_id)

    def discard(self, photo_id: str) -> None:
        """Forget a photo."""
        self._photos.pop(photo_id, None)

    def _purge(self) -> None:
        cutoff = time.monotonic() - PHOTO_TTL
        for photo_id in [k for k, v in self._photos.items() if v.created < cutoff]:
            del self._photos[photo_id]


@callback
def async_setup_photos(hass: HomeAssistant) -> None:
    """Create the store and register the upload endpoint."""
    hass.data[DATA_PHOTOS] = PhotoStore()
    hass.http.register_view(PhotoUploadView())


@callback
def async_discard_photo(hass: HomeAssistant, media_content_id: str) -> None:
    """Remove an uploaded photo once it has been used (no-op for other media)."""
    if media_content_id.startswith(MEDIA_SOURCE_PREFIX) and DATA_PHOTOS in hass.data:
        hass.data[DATA_PHOTOS].discard(media_content_id.removeprefix(MEDIA_SOURCE_PREFIX))


class PhotoUploadView(HomeAssistantView):
    """Accept a photo from the panel (authenticated HA users only)."""

    url = "/api/grocy_ai/photo"
    name = "api:grocy_ai:photo"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        """Store the request body as a photo."""
        hass = request.app[KEY_HASS]
        mime_type = request.content_type
        if not mime_type.startswith("image/"):
            return self.json_message("Only images are accepted", HTTPStatus.BAD_REQUEST)
        if request.content_length and request.content_length > MAX_PHOTO_BYTES:
            return self.json_message("Photo too large", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        content = await request.content.read(MAX_PHOTO_BYTES + 1)
        if not content:
            return self.json_message("Empty photo", HTTPStatus.BAD_REQUEST)
        if len(content) > MAX_PHOTO_BYTES:
            return self.json_message("Photo too large", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        photo_id = hass.data[DATA_PHOTOS].add(content, mime_type)
        return self.json(
            {
                "media_content_id": f"{MEDIA_SOURCE_PREFIX}{photo_id}",
                "media_content_type": mime_type,
            }
        )
