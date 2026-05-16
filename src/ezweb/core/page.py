"""Page builder module for ezweb.

Provides :class:`Page` to define page structures declaratively and render them as JSON or HTML via FastHTML.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..vendor.fasthtml.components import H1, H2, H3, H4, H5, H6, Footer, P  # type: ignore[attr-defined]
from ..vendor.fasthtml.core import Html, to_xml
from .script import ScriptInterpreter

logger = logging.getLogger("ezweb.core.app")

_B = "\033[1m"
_R = "\033[0m"
_C = "\033[36m"
_Y = "\033[33m"
_E = "\033[31m"
_W = "\033[37m"
_D = "\033[2m"

__all__ = ["Page"]

_TITLE_LEVELS = range(1, 7)

_ELEMENTS: dict[str, dict[str, Any]] = {
    "title": {
        "type": "string",
        "content": {
            "mode": "level",
            "range": _TITLE_LEVELS,
            "default": 2,
        },
        "format": {
            1: H1,
            2: H2,
            3: H3,
            4: H4,
            5: H5,
            6: H6,
        },
    },
    "text": {
        "type": "string",
        "content": {
            "default": "",
        },
        "format": P,
    },
    "footer": {
        "type": "string",
        "content": {
            "default": "",
        },
        "format": Footer,
    },
}


class Page:
    """A declarative page definition that renders to JSON or HTML.

    Parameters
    ----------
    structure:
        A dictionary describing the page elements.  Valid top-level keys
        are ``"title"``, ``"content"``, and ``"footer"``.

    Raises
    ------
    ValueError:
        If *structure* contains invalid elements or values.
    """

    def __init__(self, structure: dict[str, Any]) -> None:
        self._validate_structure(structure)
        self.structure: dict[str, Any] = structure
        self._name: str = ""

    # Public API

    @property
    def json(self) -> str:
        """Return the page structure as a compact JSON string."""
        return json.dumps(self.structure, indent=None)

    @property
    def html(self) -> str:
        """Return the page rendered as an HTML string."""
        name = self._name or "?"
        children = [
            _render_element(key, value.copy(), name)
            for key, value in self.structure.items()
        ]
        return to_xml(Html(*children), indent=False)

    def __repr__(self) -> str:
        return f"Page(structure={self.structure!r})"

    # Validation helpers

    def _validate_structure(self, structure: dict[str, Any]) -> None:
        for key, value in structure.items():
            self._validate_element_key(key)
            if not isinstance(value, dict):
                raise ValueError(
                    f"Element {key!r} must be a dictionary, got {type(value).__name__}"
                )
            self._validate_element_content(key, value)

    @staticmethod
    def _validate_element_key(key: str) -> None:
        if key not in _ELEMENTS:
            raise ValueError(f"Invalid element {key!r}.")

    @staticmethod
    def _validate_element_content(key: str, value: dict[str, Any]) -> None:
        config = _ELEMENTS[key]
        valid_keys = _build_valid_keys(config)

        for sub_key, sub_value in value.items():
            if sub_key not in valid_keys:
                raise ValueError(
                    f"Invalid sub-element {sub_key!r} in element {key!r}. "
                    f"Valid keys: {sorted(valid_keys)}"
                )
            _validate_sub_value(key, sub_key, sub_value, config)


# Internal helpers


def _build_valid_keys(config: dict[str, Any]) -> set[str]:
    valid_keys = set(config.keys()) - {"format"}
    if config.get("content", {}).get("mode") == "level":
        valid_keys.add("level")
    return valid_keys


def _validate_sub_value(
    element: str,
    key: str,
    value: Any,
    config: dict[str, Any],
) -> None:
    if isinstance(value, str):
        return

    if isinstance(value, dict) and "type" in value and "data" in value:
        _validate_content_dict(key, value, element, config)
        return

    raise ValueError(
        f"Sub-element {key!r} in {element!r} must be a string, "
        f"or a dict with 'type' and 'data' keys, "
        f"got {type(value).__name__}"
    )


def _validate_content_dict(
    key: str, value: dict[str, Any], element: str, config: dict[str, Any] | None = None
) -> None:
    content_type = value.get("type")
    if content_type not in ("string", "script", "int"):
        raise ValueError(
            f"Sub-element {key!r} in {element!r} has invalid 'type' {content_type!r}. "
            f"Must be 'string', 'script', or 'int'"
        )
    if key == "level" and content_type != "int":
        raise ValueError(
            f"Sub-element 'level' in {element!r} must have type 'int', "
            f"got {content_type!r}"
        )
    data = value.get("data")
    if content_type == "string":
        if not isinstance(data, str):
            raise ValueError(
                f"Sub-element {key!r} in {element!r} with type 'string' "
                f"requires 'data' to be a string, got {type(data).__name__}"
            )
    elif content_type == "script":
        if not isinstance(data, dict):
            raise ValueError(
                f"Sub-element {key!r} in {element!r} with type 'script' "
                f"requires 'data' to be a dict, got {type(data).__name__}"
            )
    elif content_type == "int":
        if not isinstance(data, int):
            raise ValueError(
                f"Sub-element {key!r} in {element!r} with type 'int' "
                f"requires 'data' to be an int, got {type(data).__name__}"
            )
        if key == "level" and config is not None:
            level_range = config.get("content", {}).get("range")
            if level_range is not None and data not in level_range:
                raise ValueError(
                    f"Invalid level {data!r} in {element!r}. "
                    f"Must be in {list(level_range)}"
                )


def _resolve_content(content: Any, element_key: str = "?", page_name: str = "?") -> str:
    """Resolve content from a string or content-dict to a final string."""
    if isinstance(content, str):
        return content
    if not isinstance(content, dict):
        return str(content)
    content_type = content.get("type")
    if content_type == "string":
        return content.get("data", "")
    if content_type == "script":
        interpreter = ScriptInterpreter()
        try:
            result = interpreter.execute(content["data"])
        except Exception as e:
            script_path = interpreter.path
            trail = f" > {element_key} > content > data"
            if script_path:
                trail += f" > {' > '.join(script_path)}"
            full_path = f"{_B}{page_name}{_R} > {_C}{trail.lstrip(' > ')}{_R}"

            detail = getattr(e, "detail", None)
            detail_line = ""
            if detail:
                k, v = next(iter(detail.items()))
                detail_line = f'\n    {_Y}{k}{_R}: {_Y}{_B}"{v}"{_R}'

            error_msg = (
                f"\n{_B}Script execution Traceback:{_R}\n"
                f"  {_C}{full_path}{_R}"
                f"{detail_line}\n"
                f"\n{_E}{_B}Error:{_R} {_E}{e}{_R}"
            )
            logger.error(error_msg)
            return ""
        return str(result) if result is not None else ""
    return ""


def _render_element(key: str, value: dict[str, Any], page_name: str = "?"):
    config = _ELEMENTS[key]
    if config.get("content", {}).get("mode") == "level":
        resolved = _resolve_content(value.get("content", ""), key, page_name)
        return config["format"][value["level"]["data"]](resolved)
    content = value.pop("content", "")
    resolved = _resolve_content(content, key, page_name)
    return config["format"](resolved, **value)
