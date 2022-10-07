"""titiler app."""

import logging
import os

from titiler.application import __version__ as titiler_version
from titiler.application.custom import templates
from titiler.application.routers import cog, mosaic, stac, tms
from titiler.application.settings import ApiSettings
from titiler.core.errors import DEFAULT_STATUS_CODES, add_exception_handlers
from titiler.core.middleware import (
    CacheControlMiddleware,
    LoggerMiddleware,
    LowerCaseQueryStringMiddleware,
    TotalTimeMiddleware,
)
from titiler.mosaic.errors import MOSAIC_STATUS_CODES

from fastapi import APIRouter, FastAPI

from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette_cramjam.middleware import CompressionMiddleware

LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}
# Remove any AWS-injected logger handlers to fix Lambda logging to CloudWatch
# https://stackoverflow.com/a/45624044
base = logging.getLogger()
if base.handlers:
    for handler in base.handlers:
        base.removeHandler(handler)
logging.basicConfig(level=LEVELS.get(os.environ.get("LOGLEVEL", "info")))
logging.getLogger("botocore.credentials").disabled = True
logging.getLogger("botocore.utils").disabled = True
logging.getLogger("rio-tiler").setLevel(logging.ERROR)

logger = logging.getLogger(__name__)
logger.info("TiTiler")

api_settings = ApiSettings()
logger.debug(f"Root path: {api_settings.root_path}")
logger.debug(f"Path prefix: {api_settings.path_prefix}")

app = FastAPI(
    title=api_settings.name,
    description="A lightweight Cloud Optimized GeoTIFF tile server",
    version=titiler_version,
    root_path=api_settings.root_path,
)

if not api_settings.disable_cog:
    app.include_router(
        cog.router,
        prefix=api_settings.path_prefix + "/cog",
        tags=["Cloud Optimized GeoTIFF"],
    )

if not api_settings.disable_stac:
    app.include_router(
        stac.router,
        prefix=api_settings.path_prefix + "/stac",
        tags=["SpatioTemporal Asset Catalog"],
    )

if not api_settings.disable_mosaic:
    app.include_router(
        mosaic.router,
        prefix=api_settings.path_prefix + "/mosaicjson",
        tags=["MosaicJSON"],
    )

app.include_router(tms.router, prefix=api_settings.path_prefix, tags=["TileMatrixSets"])
add_exception_handlers(app, DEFAULT_STATUS_CODES)
add_exception_handlers(app, MOSAIC_STATUS_CODES)


# Set all CORS enabled origins
if api_settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=api_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

app.add_middleware(
    CompressionMiddleware,
    minimum_size=0,
    exclude_mediatype={
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/jp2",
        "image/webp",
    },
)

app.add_middleware(
    CacheControlMiddleware,
    cachecontrol=api_settings.cachecontrol,
    exclude_path={api_settings.path_prefix + "/healthz"},
)

if api_settings.debug:
    app.add_middleware(LoggerMiddleware, headers=True, querystrings=True)
    app.add_middleware(TotalTimeMiddleware)

if api_settings.lower_case_query_parameters:
    app.add_middleware(LowerCaseQueryStringMiddleware)


router = APIRouter(prefix=api_settings.path_prefix)


@router.get("/healthz", description="Health Check", tags=["Health Check"])
def ping():
    """Health check."""
    return {"ping": "pong!"}


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def landing(request: Request):
    """TiTiler Landing page"""
    return templates.TemplateResponse(
        name="index.html",
        context={"request": request},
        media_type="text/html",
    )


app.include_router(router)
