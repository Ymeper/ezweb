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

logger = logging.getLogger(__name__)

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
        self._mode: Literal["decoupled", "Monolithic"] = "decoupled"
        self._pages: List[PageRoute] = []
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

    def _catch_all(self, request: Request):
        client_host = request.client.host if request.client else "unknown"
        if request.method == "GET":
            if request.url.path in [route.path for route in self._pages]:
                route = next(
                    route for route in self._pages if route.path == request.url.path
                )
                self._log(
                    logging.INFO, f"{client_host} -> {route.path} -> {route.name}"
                )
                html_content = (
                    "".join(route.page.html)
                    if hasattr(route.page.html, "__iter__")
                    and not isinstance(route.page.html, str)
                    else route.page.html
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
        else:
            pass

    def add_page(self, route: PageRoute):
        self._pages.append(route)

    def remove_page(self, route: PageRoute):
        self._pages.remove(route)

    @property
    def pages(self) -> List[PageRoute]:
        return self._pages

    def set_mode(self, mode: Literal["decoupled", "Monolithic"]):
        if mode not in ["decoupled", "Monolithic"]:
            raise ValueError("Invalid mode. Mode must be 'decoupled' or 'Monolithic'.")
        self._mode = mode
        return self._mode

    @property
    def mode(self) -> Literal["decoupled", "Monolithic"]:
        return self._mode

    def run(self, host: str = "127.0.0.1", port: int = 8000):
        self._log(logging.INFO, f"Starting server in {self._mode} mode on {host}:{port}")
        uvicorn.run(
            self._app,
            host=host,
            port=port,
            log_level="critical",
            access_log=False,
            server_header=False,
        )
