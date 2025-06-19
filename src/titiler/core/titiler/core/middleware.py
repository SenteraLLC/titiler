"""Titiler middlewares."""

import logging
import re
import time
from typing import Optional, Set

from fastapi.logger import logger
import rasterio
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class CacheControlMiddleware:
    """MiddleWare to add CacheControl in response headers."""

    def __init__(
        self,
        app: ASGIApp,
        cachecontrol: Optional[str] = None,
        cachecontrol_max_http_code: Optional[int] = 500,
        exclude_path: Optional[Set[str]] = None,
    ) -> None:
        """Init Middleware.

        Args:
            app (ASGIApp): starlette/FastAPI application.
            cachecontrol (str): Cache-Control string to add to the response.
            exclude_path (set): Set of regex expression to use to filter the path.

        """
        self.app = app
        self.cachecontrol = cachecontrol
        self.cachecontrol_max_http_code = cachecontrol_max_http_code
        self.exclude_path = exclude_path or set()

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        """Handle call."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message):
            """Send Message."""
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                if self.cachecontrol and not response_headers.get("Cache-Control"):
                    if (
                        scope["method"] in ["HEAD", "GET"]
                        and message["status"] < self.cachecontrol_max_http_code
                        and not any(
                            [
                                re.match(path, scope["path"])
                                for path in self.exclude_path
                            ]
                        )
                    ):
                        response_headers["Cache-Control"] = self.cachecontrol

            await send(message)

        await self.app(scope, receive, send_wrapper)


class TotalTimeMiddleware:
    """MiddleWare to add Total process time in response headers."""

    def __init__(self, app: ASGIApp) -> None:
        """Init Middleware.

        Args:
            app (ASGIApp): starlette/FastAPI application.

        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        """Handle call."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()

        async def send_wrapper(message: Message):
            """Send Message."""
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                process_time = time.time() - start_time
                app_time = "total;dur={}".format(round(process_time * 1000, 2))

                timings = response_headers.get("Server-Timing")
                response_headers["Server-Timing"] = (
                    f"{timings}, {app_time}" if timings else app_time
                )

            await send(message)

        await self.app(scope, receive, send_wrapper)


class LoggerMiddleware:
    """MiddleWare to add logging."""

    def __init__(
        self,
        app: ASGIApp,
        querystrings: bool = False,
        headers: bool = False,
    ) -> None:
        """Init Middleware.

        Args:
            app (ASGIApp): starlette/FastAPI application.

        """
        self.app = app
        self.querystrings = querystrings
        self.headers = headers
        self.logger = logger
        logger.setLevel(logging.DEBUG)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        """Handle call."""
        if scope["type"] == "http":
            request = Request(scope)

            self.logger.debug(str(request.url))

            qs = dict(request.query_params)
            if qs and self.querystrings:
                self.logger.debug(qs)

            if self.headers:
                self.logger.debug(dict(request.headers))

        await self.app(scope, receive, send)


class LowerCaseQueryStringMiddleware:
    """Middleware to make URL parameters case-insensitive.
    taken from: https://github.com/tiangolo/fastapi/issues/826
    """

    def __init__(self, app: ASGIApp) -> None:
        """Init Middleware.

        Args:
            app (ASGIApp): starlette/FastAPI application.

        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        """Handle call."""
        if scope["type"] == "http":
            request = Request(scope)

            DECODE_FORMAT = "latin-1"

            query_string = ""
            for k, v in request.query_params.multi_items():
                query_string += k.lower() + "=" + v + "&"

            query_string = query_string[:-1]
            request.scope["query_string"] = query_string.encode(DECODE_FORMAT)

        await self.app(scope, receive, send)

class BlockVRTMiddleware(BaseHTTPMiddleware):
    """Middleware to block requests with vrt in the path."""
    async def dispatch(self, request: Request, call_next):
        """Handle call."""
        # Check path for VRT
        if ".vrt" in request.scope["path"].lower():
            return Response(
                content="VRT files are not supported.",
                status_code=403,
            )

        # Check URL parameter for VRT
        url_param = request.query_params.get("url", "").lower()
        if ".vrt" in url_param:
            return Response(
                content="VRT files are not supported in URL parameters.",
                status_code=403,
            )

        try:
            with rasterio.open(url_param, sharing=False) as src:
                if src.driver == "VRT":
                    return Response(
                        content="VRT files are not supported in URL parameters.",
                        status_code=403,
                    )
        except Exception:
            # If rasterio fails to open the file, we assume it's not a VRT
            pass

        # Continue with the request if no VRT detected
        response = await call_next(request)
        return response
