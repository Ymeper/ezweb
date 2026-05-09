"""Page builder module for ezweb.

Provides :class:`Page` to define page structures declaratively and render them as JSON or HTML via FastHTML.
"""

from __future__ import annotations

import json
from typing import Any

from ..vendor.fasthtml.components import H1, H2, H3, H4, H5, H6, Footer, P
from ..vendor.fasthtml.core import Html, to_xml

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

    # Public API

    @property
    def json(self) -> str:
        """Return the page structure as a compact JSON string."""
        return json.dumps(self.structure, indent=None)

    @property
    def html(self) -> str:
        """Return the page rendered as an HTML string."""
        children = [_render_element(key, value.copy()) for key, value in self.structure.items()]
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
            raise ValueError(
                f"Invalid element {key!r}."
            )

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
    if key == "level":
        if not isinstance(value, int):
            raise ValueError(
                f"Sub-element 'level' in {element!r} must be an integer, "
                f"got {type(value).__name__}"
            )
        if value not in config["content"]["range"]:
            raise ValueError(
                f"Invalid level {value!r} in {element!r}. "
                f"Must be in {list(config['content']['range'])}"
            )
        return

    if not isinstance(value, str):
        raise ValueError(
            f"Sub-element {key!r} in {element!r} must be a string, "
            f"got {type(value).__name__}"
        )


def _render_element(key: str, value: dict[str, Any]):
    config = _ELEMENTS[key]
    if config.get("content", {}).get("mode") == "level":
        return config["format"][value["level"]](value["content"])
    content = value.pop("content", "")
    return config["format"](content, **value)
