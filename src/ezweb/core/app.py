import json
from fastapi import Request
from pathlib import Path
import uvicorn
from jinja2 import Environment, FileSystemLoader
import colorlog
import logging
from minify_html import minify as html_minify
from starlette.routing import Route as StarletteRoute
from starlette.responses import JSONResponse
from starlette.responses import HTMLResponse
from starlette.applications import Starlette
from typing import Literal, List, Optional
from dataclasses import dataclass
from .page import Page
from .script import ScriptInterpreter, ScriptError

logger = logging.getLogger(__name__)


def _uvicorn_delegate(self, record):
    logger.handle(record)
    if logger.level == logging.NOTSET or record.levelno >= logger.level:
        self._delegate_original(record)


uvicorn_logger = logging.getLogger("uvicorn")
uvicorn_logger.handlers.clear()
object.__setattr__(uvicorn_logger, "_delegate_original", uvicorn_logger.handle)
uvicorn_logger.handle = _uvicorn_delegate.__get__(uvicorn_logger, type(uvicorn_logger))  # type: ignore[method-assign]

uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.handlers.clear()
object.__setattr__(
    uvicorn_access_logger, "_delegate_original", uvicorn_access_logger.handle
)
uvicorn_access_logger.handle = _uvicorn_delegate.__get__(
    uvicorn_access_logger, type(uvicorn_access_logger)
)  # type: ignore[method-assign]

# Set up Jinja2 environment for template rendering
_templates_dir = Path(__file__).resolve().parent.parent / "templates"
env = Environment(
    loader=FileSystemLoader(str(_templates_dir)),
    autoescape=True,
    trim_blocks=True,
    lstrip_blocks=True,
)
templates = {
    "404.html": env.get_template("404.html"),
}

_formatter = colorlog.ColoredFormatter(
    "[%(asctime)s] [%(log_color)s%(levelname)-8s%(reset)s] %(message)s",
    datefmt="%m-%d %H:%M:%S",
    reset=True,
    log_colors={
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "purple",
    },
    style="%",
)

_handler = colorlog.StreamHandler()
_handler.setFormatter(_formatter)

logger.addHandler(_handler)
logger.setLevel(logging.INFO)


@dataclass(frozen=True)
class PageRoute:
    """PageRoute represents a single page route in the application. It contains the page's name, path, page definition, and optional title and hidden status."""

    name: str
    path: str
    page: Page


class App:
    def __init__(self, logger: Optional[logging.Logger] = logger):
        self._pages: List[PageRoute] = []
        self._api_handlers: dict[str, dict] = {}
        self._logger = logger
        self._app = Starlette(
            routes=[
                StarletteRoute(
                    "/{path:path}",
                    endpoint=self._catch_all,
                    methods=[
                        "GET",
                        "POST",
                        "PUT",
                        "DELETE",
                        "PATCH",
                        "HEAD",
                        "OPTIONS",
                    ],
                )
            ]
        )

    def _log(self, level: int, msg: str, *args):
        if self._logger is not None:
            self._logger.log(level, msg, *args)

    async def _catch_all(self, request: Request):
        client_host = request.client.host if request.client else "unknown"
        if request.method == "GET":
            if request.url.path in [route.path for route in self._pages]:
                route = next(
                    route for route in self._pages if route.path == request.url.path
                )
                self._log(
                    logging.INFO, f"{client_host} -> {route.path} -> {route.name}"
                )
                route.page._name = route.name
                page_html = route.page.html
                html_content = (
                    "".join(page_html)
                    if hasattr(page_html, "__iter__") and not isinstance(page_html, str)
                    else page_html
                )
                return HTMLResponse(content=html_content)
            else:
                self._log(
                    logging.INFO, f"{client_host} -> {request.url.path} -> Not Found"
                )
                return HTMLResponse(
                    content=html_minify(
                        templates["404.html"].render(request=request),
                        minify_css=True,
                    ),
                    status_code=404,
                )
        elif request.method == "POST":
            path = request.url.path
            script_data = self._api_handlers.get(path)
            if script_data is None:
                self._log(
                    logging.INFO,
                    f"{client_host} -> {path} -> API Not Found",
                )
                return JSONResponse({"error": "endpoint not found"}, status_code=404)
            try:
                body = await request.json()
            except Exception:
                body = {}
            self._log(logging.INFO, f"{client_host} -> POST {path}")
            interpreter = ScriptInterpreter(
                initial_variables={"$body": body},
            )
            try:
                result = interpreter.execute(script_data)
            except ScriptError as e:
                detail = getattr(e, "detail", {})
                return JSONResponse(
                    {"error": str(e), "detail": detail}, status_code=500
                )
            except Exception as e:
                return JSONResponse({"error": str(e)}, status_code=500)
            return JSONResponse(result if result is not None else {"ok": True})
        else:
            pass

    def add_page(self, route: PageRoute):
        self._pages.append(route)

    def add_api(self, path: str, script: dict):
        self._api_handlers[path] = script

    def remove_page(self, route: PageRoute):
        self._pages.remove(route)

    def remove_api(self, path: str):
        self._api_handlers.pop(path, None)

    @property
    def pages(self) -> List[PageRoute]:
        return self._pages

    def run(self, host: str = "127.0.0.1", port: int = 8000):
        self._log(logging.INFO, f"Starting server on {host}:{port}")
        uvicorn.run(
            self._app,
            host=host,
            port=port,
            log_level="error",
            access_log=False,
            server_header=False,
        )
