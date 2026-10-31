"""Media source exposing photos uploaded from the panel to AI Task."""

from __future__ import annotations

from homeassistant.components.media_player import MediaClass
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .photos import DATA_PHOTOS


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    """Set up the Grocy AI photo source."""
    return GrocyAiPhotoSource()


class GrocyAiPhotoSource(MediaSource):
    """Short-lived uploaded photos, resolved to a temporary file; not browsable."""

    name = "Grocy AI"

    def __init__(self) -> None:
        """Initialize the source."""
        super().__init__(DOMAIN)

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Hand the photo to AI Task as a temporary local file (HA 2026.10)."""
        store = item.hass.data.get(DATA_PHOTOS)
        if store is None or (photo := store.get(item.identifier)) is None:
            raise Unresolvable("Grocy AI photo not found or expired")
        path = await store.async_get_path(item.identifier)
        return PlayMedia(url="", mime_type=photo.mime_type, path=path)

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Show an empty folder: photos are private and short-lived."""
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.DIRECTORY,
            media_content_type="",
            title=self.name,
            can_play=False,
            can_expand=True,
            children=[],
            children_media_class=MediaClass.IMAGE,
        )
