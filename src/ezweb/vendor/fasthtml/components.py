from functools import partial

from fastcore.utils import partition, risinstance
from fastcore.xml import FT, attrmap, valmap, voids, ft
from typing import Mapping

from .core import fh_cfg, unqid

__all__ = [
    "ft_html",
    "ft_hx",
    "A",
    "Abbr",
    "Address",
    "Area",
    "Article",
    "Aside",
    "Audio",
    "B",
    "Base",
    "Bdi",
    "Bdo",
    "Blockquote",
    "Body",
    "Br",
    "Button",
    "Canvas",
    "Caption",
    "Cite",
    "Code",
    "Col",
    "Colgroup",
    "Data",
    "Datalist",
    "Dd",
    "Del",
    "Details",
    "Dfn",
    "Dialog",
    "Div",
    "Dl",
    "Dt",
    "Em",
    "Embed",
    "Fencedframe",
    "Fieldset",
    "Figcaption",
    "Figure",
    "Footer",
    "Form",
    "H1",
    "H2",
    "H3",
    "H4",
    "H5",
    "H6",
    "Head",
    "Header",
    "Hgroup",
    "Hr",
    "I",
    "Iframe",
    "Img",
    "Input",
    "Ins",
    "Kbd",
    "Label",
    "Legend",
    "Li",
    "Link",
    "Main",
    "Map",
    "Mark",
    "Menu",
    "Meta",
    "Meter",
    "Nav",
    "Noscript",
    "Object",
    "Ol",
    "Optgroup",
    "Option",
    "Output",
    "P",
    "Picture",
    "Pre",
    "Progress",
    "Q",
    "Rp",
    "Rt",
    "Ruby",
    "S",
    "Samp",
    "Script",
    "Search",
    "Section",
    "Select",
    "Slot",
    "Small",
    "Source",
    "Span",
    "Strong",
    "Style",
    "Sub",
    "Summary",
    "Sup",
    "Table",
    "Tbody",
    "Td",
    "Template",
    "Textarea",
    "Tfoot",
    "Th",
    "Thead",
    "Time",
    "Title",
    "Tr",
    "Track",
    "U",
    "Ul",
    "Var",
    "Video",
    "Wbr",
]

named = set(
    "a button form frame iframe img input map meta object param select textarea".split()
)

ft_hx_scalar_attrs = {
    "hx_swap": None,
    "hx_push_url": None,
    "hx_replace_url": None,
    "hx_disabled_elt": None,
    "hx_history": None,
    "hx_params": None,
    "hx_validate": None,
    "hx_vals": None,
    "hx_target": None,
    "target_id": None,
}


def ft_html(tag, *c, id=None, cls=None, title=None, style=None, **kwargs):
    ds, c = partition(c, risinstance(Mapping))
    for d in ds:
        kwargs = {**kwargs, **d}
    if not id and fh_cfg.get("auto_id"):
        id = True
    if id and isinstance(id, bool):
        id = unqid()
    kwargs["id"] = id.id if isinstance(id, FT) else id
    kwargs["cls"], kwargs["title"], kwargs["style"] = cls, title, style
    tag, c, kw = ft(tag, *c, attrmap=attrmap, valmap=valmap, **kwargs).list
    if fh_cfg.get("auto_name") and tag in named and id and "name" not in kw:
        kw["name"] = kw["id"]
    return FT(tag, c, kw, void_=tag in voids)


def ft_hx(tag, *c, target_id=None, hx_vals=None, hx_target=None, **kwargs):
    if hx_vals:
        import json

        kwargs["hx_vals"] = (
            json.dumps(hx_vals) if isinstance(hx_vals, dict) else hx_vals
        )
    if hx_target:
        kwargs["hx_target"] = (
            "#" + hx_target.id if isinstance(hx_target, FT) else hx_target
        )
    if target_id:
        kwargs["hx_target"] = "#" + target_id
    return ft_html(tag, *c, **kwargs)


# Dynamically generate HTML tag functions: A(), Div(), H1(), ..., Wbr()
# All bound to `ft_hx` with the tag name in lowercase.
# Pylance cannot statically verify these; suppress all type errors in this block.
_tags = (
    "A",
    "Abbr",
    "Address",
    "Area",
    "Article",
    "Aside",
    "Audio",
    "B",
    "Base",
    "Bdi",
    "Bdo",
    "Blockquote",
    "Body",
    "Br",
    "Button",
    "Canvas",
    "Caption",
    "Cite",
    "Code",
    "Col",
    "Colgroup",
    "Data",
    "Datalist",
    "Dd",
    "Del",
    "Details",
    "Dfn",
    "Dialog",
    "Div",
    "Dl",
    "Dt",
    "Em",
    "Embed",
    "Fencedframe",
    "Fieldset",
    "Figcaption",
    "Figure",
    "Footer",
    "Form",
    "H1",
    "H2",
    "H3",
    "H4",
    "H5",
    "H6",
    "Head",
    "Header",
    "Hgroup",
    "Hr",
    "I",
    "Iframe",
    "Img",
    "Input",
    "Ins",
    "Kbd",
    "Label",
    "Legend",
    "Li",
    "Link",
    "Main",
    "Map",
    "Mark",
    "Menu",
    "Meta",
    "Meter",
    "Nav",
    "Noscript",
    "Object",
    "Ol",
    "Optgroup",
    "Option",
    "Output",
    "P",
    "Picture",
    "Pre",
    "Progress",
    "Q",
    "Rp",
    "Rt",
    "Ruby",
    "S",
    "Samp",
    "Script",
    "Search",
    "Section",
    "Select",
    "Slot",
    "Small",
    "Source",
    "Span",
    "Strong",
    "Style",
    "Sub",
    "Summary",
    "Sup",
    "Table",
    "Tbody",
    "Td",
    "Template",
    "Textarea",
    "Tfoot",
    "Th",
    "Thead",
    "Time",
    "Title",
    "Tr",
    "Track",
    "U",
    "Ul",
    "Var",
    "Video",
    "Wbr",
)  # type: ignore[reportUnusedVariable]
_g = globals()
for o in _tags:  # type: ignore[reportInvalidTypeForm]
    _g[o] = partial(ft_hx, o.lower())
