import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, HTTPException, Header, Request, Response, status
import os
import json
from typing import List, Optional
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import app_config
from app.util import logger, clean_path_parameter
from app.core.screen import get_screen_by_id

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get(
    "/screen/{id}/image.png",
    summary="Get the current image for a screen",
    response_description="PNG image"
)
async def get_screen_image(request: Request, id: str, response: Response, if_none_match: Optional[str] = Header(None), color_model: Optional[str] = None):
    # determine rendering
    id = clean_path_parameter(id)
    logger.info(f"GET /api/displays/{id}/image with If-None-Match={if_none_match} and colors={color_model}")
    screen = await get_screen_by_id(id)
    if screen is None:
        raise HTTPException(status_code=404, detail="Screen not found or not parsable")

    # determine color model
    color_model_dict = {c.id: c for c in app_config.epaper_color_models}
    #color_model = None
    if color_model is not None:
        if color_model in color_model_dict:
            color_model = color_model_dict[color_model]
        else:
            logger.info(f"Unknown color model {color_model} in request, using default. Available models: {list(color_model_dict.keys())}")
            color_model = None

    # update the image if needed
    await screen.update_if_needed(color_model=color_model)

    # collect new response header fields
    meta = await screen.get_metadata()
    if meta is None:
        raise HTTPException(status_code=500, detail="Error getting metadata")

    etag = meta.version
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
        # "Content-Disposition": f'inline; filename="{etag}.png"'
    }

    # Return 304 if content did not change
    if if_none_match != None and if_none_match == etag:
        return Response("", status.HTTP_304_NOT_MODIFIED, headers=headers)

    # return response
    filename = await screen.get_image_path(color_model=color_model)
    return FileResponse(path=filename, media_type="image/png", headers=headers)
    #image_buffer = await screen.get_image_buffer()
    #return Response(content=image_buffer, media_type="image/png", headers=headers)

