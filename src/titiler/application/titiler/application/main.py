"""titiler app."""

import logging
import os

from fastapi import APIRouter, FastAPI
from rio_tiler.io import STACReader
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.templating import Jinja2Templates
from starlette_cramjam.middleware import CompressionMiddleware

from titiler.application import __version__ as titiler_version
from titiler.application.settings import ApiSettings
from titiler.core.errors import DEFAULT_STATUS_CODES, add_exception_handlers
from titiler.core.factory import (
    AlgorithmFactory,
    MultiBaseTilerFactory,
    TilerFactory,
    TMSFactory,
)
from titiler.core.middleware import (
    CacheControlMiddleware,
    LoggerMiddleware,
    LowerCaseQueryStringMiddleware,
    TotalTimeMiddleware,
    BlockVRTMiddleware,
)
from titiler.extensions import (
    cogValidateExtension,
    cogViewerExtension,
    stacExtension,
    stacViewerExtension,
)
from titiler.mosaic.errors import MOSAIC_STATUS_CODES
from titiler.mosaic.factory import MosaicTilerFactory

try:
    from importlib.resources import files as resources_files  # type: ignore
except ImportError:
    # Try backported to PY<39 `importlib_resources`.
    from importlib_resources import files as resources_files  # type: ignore

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

# TODO: mypy fails in python 3.9, we need to find a proper way to do this
templates = Jinja2Templates(directory=str(resources_files(__package__) / "templates"))  # type: ignore

api_settings = ApiSettings()
global_prefix = api_settings.path_prefix
logger.debug(f"Root path: {api_settings.root_path}")
logger.debug(f"Path prefix: {global_prefix}")

app = FastAPI(
    title=api_settings.name,
    description="""A modern dynamic tile server built on top of FastAPI and Rasterio/GDAL.

---

**Documentation**: <a href="https://developmentseed.org/titiler/" target="_blank">https://developmentseed.org/titiler/</a>

**Source Code**: <a href="https://github.com/developmentseed/titiler" target="_blank">https://github.com/developmentseed/titiler</a>

---
    """,
    version=titiler_version,
    root_path=api_settings.root_path,
)

###############################################################################
# Simple Dataset endpoints (e.g Cloud Optimized GeoTIFF)
cog_prefix = global_prefix + "/cog"
if not api_settings.disable_cog:
    cog = TilerFactory(
        router_prefix=cog_prefix,
        extensions=[
            cogValidateExtension(),
            cogViewerExtension(),
            stacExtension(),
        ],
    )

    app.include_router(cog.router, prefix=cog_prefix, tags=["Cloud Optimized GeoTIFF"])


###############################################################################
# STAC endpoints
stac_prefix = global_prefix + "/stac"
if not api_settings.disable_stac:
    stac = MultiBaseTilerFactory(
        reader=STACReader,
        router_prefix=stac_prefix,
        extensions=[
            stacViewerExtension(),
        ],
    )

    app.include_router(
        stac.router, prefix=stac_prefix, tags=["SpatioTemporal Asset Catalog"]
    )

###############################################################################
# Mosaic endpoints
mosaicjson_prefix = global_prefix + "/mosaicjson"
if not api_settings.disable_mosaic:
    mosaic = MosaicTilerFactory(router_prefix=mosaicjson_prefix)
    app.include_router(mosaic.router, prefix=mosaicjson_prefix, tags=["MosaicJSON"])

###############################################################################
# TileMatrixSets endpoints
tms = TMSFactory()
app.include_router(tms.router, prefix=global_prefix, tags=["Tiling Schemes"])

###############################################################################
# Algorithms endpoints
algorithms = AlgorithmFactory()
app.include_router(algorithms.router, prefix=global_prefix, tags=["Algorithms"])

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
    exclude_path={global_prefix + r"/healthz"},
)

if api_settings.debug:
    app.add_middleware(LoggerMiddleware, headers=True, querystrings=True)
    app.add_middleware(TotalTimeMiddleware)

if api_settings.lower_case_query_parameters:
    app.add_middleware(LowerCaseQueryStringMiddleware)

app.add_middleware(BlockVRTMiddleware)

router = APIRouter(prefix=global_prefix)


@router.get(
    "/healthz",
    description="Health Check.",
    summary="Health Check.",
    operation_id="healthCheck",
    tags=["Health Check"],
)
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
