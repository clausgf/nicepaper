import asyncio
import datetime
import io
from typing import Callable
from zoneinfo import ZoneInfo
from fastapi import APIRouter, HTTPException, Header, Path as PathParam, Query, Response, status
from typing import Optional
from fastapi.responses import FileResponse

from extensions.epaper.config import app_config
from extensions.epaper.util import logger, clean_path_parameter
from extensions.epaper.screen.backend import get_screen_by_id
from extensions.epaper.paths import EpaperPaths

_RESPONSES = {
    200: {
        "content": {"image/png": {}},
        "description": (
            "The rendered screen image, quantized to the palette the screen "
            "is configured for. The `ETag` header identifies this image "
            "version; `Cache-Control: max-age` tells the display how many "
            "seconds the image stays valid at most."
        ),
    },
    status.HTTP_304_NOT_MODIFIED: {
        "description": "The image has not changed since the version given in `If-None-Match`.",
    },
    404: {"description": "No screen configuration exists for this id."},
}

_RAW_DESCRIPTION = (
    "Return the unquantized RGB render instead of the palette image. For "
    "debugging what quantization did to a color; a display never needs it."
)

_BOXES_DESCRIPTION = (
    "Outline every widget's box, marking the anchor of widgets that size "
    "themselves. Renders on demand and is never cached, so it cannot leak "
    "into the image a display fetches. For laying out a screen in the "
    "editor; a display never needs it."
)


async def _render_screen_image(paths: EpaperPaths, id: str, if_none_match: Optional[str],
                               raw: bool = False, boxes: bool = False) -> Response:
    """
    Shared logic behind both the standalone and the nice4iot-extension
    image endpoint: render (if needed) and return the current PNG for a
    screen rooted at `paths`.

    Which palette the image is quantized to is the screen's own setting,
    not a request parameter -- a screen is laid out for one panel, so the
    display doesn't need to know its own palette (and can't get it wrong).
    """
    id = clean_path_parameter(id)
    logger.info(f"GET screen/{id}/image.png with If-None-Match={if_none_match}, raw={raw}, boxes={boxes}")
    screen = await get_screen_by_id(paths, id)
    if screen is None:
        raise HTTPException(status_code=404, detail="Screen not found or not parsable")

    if boxes:
        # an editor view, not a display's image: rendered on demand and
        # returned without touching the cache or its ETag, so nothing a
        # display later fetches can carry the outlines
        image = await screen.render_preview(boxes=True, raw=raw)
        buffer = io.BytesIO()
        await asyncio.to_thread(image.save, buffer, format="PNG", compress_level=1)
        return Response(buffer.getvalue(), media_type="image/png",
                        headers={"Cache-Control": "no-store"})

    # update the image if needed
    await screen.update_if_needed()

    # collect new response header fields
    meta = await screen.get_metadata()
    if meta is None:
        raise HTTPException(status_code=500, detail="Error getting metadata")

    # meta.version identifies the served (quantized) image; the raw
    # variant is different bytes and so must not share its ETag
    etag = f"{meta.version}-raw" if raw else meta.version
    expires_at = meta.expires_at
    if expires_at:
        now = datetime.datetime.now(ZoneInfo(app_config.timezone))
        seconds_till_update = (expires_at - now).total_seconds()
        max_age = max(60, round(seconds_till_update))
    else:
        max_age = 60
    headers = {
        "ETag": etag,
        "Cache-Control": f"max-age={max_age}"
    }

    # Return 304 if content did not change
    if if_none_match is not None and if_none_match == etag:
        return Response("", status.HTTP_304_NOT_MODIFIED, headers=headers)

    filename = await screen.get_image_path(raw=raw)
    return FileResponse(path=filename, media_type="image/png", headers=headers)


def build_standalone_router(paths: EpaperPaths) -> APIRouter:
    """
    API router for standalone mode: a single fixed root, URLs unchanged
    from before the nice4iot-extension split (no project_name segment).
    """
    router = APIRouter()

    @router.get(
        "/screen/{id}/image.png",
        summary="Get the current image for a screen",
        tags=["screens"],
        response_class=FileResponse,
        responses=_RESPONSES,
    )
    async def get_screen_image(
        id: str = PathParam(description="Screen id (the screen's JSON file name without extension) or an alias defined in the alias file."),
        if_none_match: Optional[str] = Header(None, description="`ETag` of the image version the display already has; if it is still current, the response is `304 Not Modified`."),
        raw: bool = Query(False, description=_RAW_DESCRIPTION),
        boxes: bool = Query(False, description=_BOXES_DESCRIPTION),
    ):
        """
        Render (if needed) and return the current PNG image for a screen,
        quantized to the palette configured on that screen.

        The image is re-rendered when the screen configuration changed or the
        previous image expired; otherwise it is served from the cache. Displays
        should poll this endpoint, send the last `ETag` as `If-None-Match` and
        sleep for `Cache-Control: max-age` seconds between polls.
        """
        return await _render_screen_image(paths, id, if_none_match, raw, boxes)

    return router


def build_extension_router(paths_for_project: Callable[[str], EpaperPaths]) -> APIRouter:
    """
    API router for nice4iot-extension mode: every route carries
    project_name (required by app.extensions.mount_extension_router),
    resolved to an EpaperPaths root via `paths_for_project`. Deliberately
    takes a callback instead of importing nice4iot's app.paths directly,
    so this module has no nice4iot dependency and stays usable standalone.
    """
    router = APIRouter()

    @router.get(
        "/{project_name}/screens/{id}/image.png",
        summary="Get the current image for a screen",
        tags=["screens"],
        response_class=FileResponse,
        responses=_RESPONSES,
    )
    async def get_screen_image(
        project_name: str = PathParam(description="nice4iot project name."),
        id: str = PathParam(description="Screen id (the screen's JSON file name without extension) or an alias defined in the alias file."),
        if_none_match: Optional[str] = Header(None),
        raw: bool = Query(False, description=_RAW_DESCRIPTION),
        boxes: bool = Query(False, description=_BOXES_DESCRIPTION),
    ):
        paths = paths_for_project(project_name)
        return await _render_screen_image(paths, id, if_none_match, raw, boxes)

    return router
