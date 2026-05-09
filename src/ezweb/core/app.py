from fastapi import Request
from threading import Thread
import uvicorn
from starlette.routing import Route as StarletteRoute
from starlette.responses import JSONResponse
from starlette.responses import HTMLResponse
from starlette.applications import Starlette
from typing import Literal, List
from dataclasses import dataclass
from .page import Page


@dataclass(frozen=True)
class PageRoute:
    """PageRoute represents a single page route in the application. It contains the page's name, path, page definition, and optional title and hidden status."""

    name: str
    path: str
    page: Page


class App:
    def __init__(self):
        self._mode: Literal["decoupled", "Monolithic"] = "decoupled"
        self._pages: List[PageRoute] = []
        self._app_thread = None
        self._app = Starlette(routes=[
            StarletteRoute(
                "/{path:path}",
                endpoint=self._catch_all,
                methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
            )
        ])

    def _catch_all(self, request: Request):
        if request.method == "GET":
            if request.url.path in [route.path for route in self._pages]:
                route = next(route for route in self._pages if route.path == request.url.path)
                html_content = "".join(route.page.html) if hasattr(route.page.html, '__iter__') and not isinstance(route.page.html, str) else route.page.html
                return HTMLResponse(content=html_content)

    
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
        self._app_thread = Thread(
            target=uvicorn.run, args=(self._app,), kwargs={"host": host, "port": port, "log_level": "critical", "access_log": False, "server_header": False},
            daemon=True,)
        self._app_thread.start()
