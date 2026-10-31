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
from homeassistant.components.media_source.models import MediaImage
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .photos import DATA_PHOTOS


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    """Set up the Grocy AI photo source."""
    return GrocyAiPhotoSource()


class GrocyAiPhotoSource(MediaSource):
    """Short-lived photos; readable as image, not browsable."""

    name = "Grocy AI"

    def __init__(self) -> None:
        """Initialize the source."""
        super().__init__(DOMAIN)

    async def async_get_media_image(self, item: MediaSourceItem) -> MediaImage | None:
        """Return the uploaded photo (used by AI Task attachments)."""
        store = item.hass.data.get(DATA_PHOTOS)
        if store is None or (photo := store.get(item.identifier)) is None:
            return None
        return MediaImage(content=photo.content, mime_type=photo.mime_type)

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Photos are only handed out as images."""
        raise Unresolvable("Grocy AI photos expire quickly and cannot be played")

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
