"""FastHTML core - HTML generation utilities (server components removed)."""

__all__ = ['empty', 'htmx_hdrs', 'fh_cfg', 'htmx_resps', 'htmx_exts', 'htmxsrc', 'fhjsscr', 'surrsrc', 'scopesrc', 'viewport',
           'charset', 'cors_allow', 'iframe_scr', 'parsed_date', 'snake2hyphens',
           'HtmxHeaders', 'HttpHeader', 'HtmxResponseHeaders', 'form2dict', 'parse_form', 'ApiReturn', 'JSONResponse',
           'flat_xt', 'EventStream', 'uri', 'decode_uri', 'flat_tuple', 'noop_body',
           'respond', 'is_full_page', 'Redirect', 'get_key', 'qp', 'def_hdrs',
           'cookie', 'FtResponse', 'unqid']

import json,uuid,inspect,types,os,random,re

from fastcore.utils import (
    AttrDict, Path, camel2words, first, is_async_callable, is_listy,
    is_namedtuple, listify, maybe_await, noop, partition, risinstance,
    signature_ex, snake2camel, str2bool, str2date, str2int, tuplify,
)
from fastcore.xml import (
    Body, FT, Head, Html, Link, Meta, NotStr, Safe, Script, Title, to_xml,
)
from fastcore.meta import use_kwargs_dict,delegates  # type: ignore[reportUnusedImport]

from types import UnionType, SimpleNamespace as ns, GenericAlias
from typing import get_args, get_origin, Union, Mapping, List, Any, cast
from datetime import datetime,date
from dataclasses import dataclass
from inspect import Parameter,get_annotations
from http import cookies
from urllib.parse import urlencode, parse_qs, quote, unquote
from copy import deepcopy
from warnings import warn
from dateutil import parser as dtparse
from uuid import uuid4, UUID
from base64 import b64encode
from email.utils import format_datetime

from .starlette import (
    BackgroundTask, BackgroundTasks, CORSMiddleware, FileResponse, FormData,
    HTMLResponse, HTTPConnection, HTTPException, JSONResponseOrig, Middleware,
    RedirectResponse, Request, Response, Starlette, State, StreamingResponse,
    UploadFile, run_in_threadpool,
)

empty = Parameter.empty

def parsed_date(s:str):
    "Convert `s` to a datetime"
    return dtparse.parse(s)

def snake2hyphens(s:str):
    "Convert `s` from snake case to hyphenated and capitalised"
    s = snake2camel(s)
    return camel2words(s, '-')

htmx_hdrs = dict(
    boosted="HX-Boosted",
    current_url="HX-Current-URL",
    history_restore_request="HX-History-Restore-Request",
    prompt="HX-Prompt",
    request="HX-Request",
    target="HX-Target",
    trigger_name="HX-Trigger-Name",
    trigger="HX-Trigger")

@dataclass
class HtmxHeaders:
    boosted:str|None=None; current_url:str|None=None; history_restore_request:str|None=None; prompt:str|None=None
    request:str|None=None; target:str|None=None; trigger_name:str|None=None; trigger:str|None=None
    def __bool__(self): return any(hasattr(self,o) for o in htmx_hdrs)

def _get_htmx(h):
    res = {k:h.get(v.lower(), None) for k,v in htmx_hdrs.items()}
    return HtmxHeaders(**res)

def _mk_list(t, v): return [t(o) for o in listify(v)]

fh_cfg: AttrDict = AttrDict(indent=True)

_special_names = {'ws','request','session','scope','data','htmx','app','state','auth','send','api','body','hdrs','ftrs','bodykw','htmlkw','resp','self'}

def _check_anno(arg, anno):
    "Check for common annotation issues; returns warning string or None"
    if anno is empty and arg.lower() not in _special_names and not any(s.startswith(arg.lower()) for s in ('request','session')): return f"`{arg}` has no type annotation and is not a recognised special name, so is ignored."
    if isinstance(anno, type) and not get_origin(anno) and issubclass(anno, (list, tuple)) and not _is_body(anno): return f"`{arg}` uses bare `{anno.__name__}` annotation, so is ignored (use e.g. `{anno.__name__}[str]` instead)."

def _fix_anno(t, o):
    "Create appropriate callable type for casting a `str` to type `t` (or first type in `t` if union)"
    origin = get_origin(t)
    if origin is Union or origin is UnionType: origin = get_origin(t:=first(o for o in get_args(t) if o!=type(None)))  # type: ignore[arg-type]
    if origin in (list,List): t = first(o for o in get_args(t) if o!=type(None))  # type: ignore[arg-type]
    d = {bool: str2bool, int: str2int, date: str2date, UploadFile: noop}
    res = d.get(t, t)
    assert res is not None, f"_fix_anno: no handler for type {t}"
    if origin in (list,List): return _mk_list(res, o)  # type: ignore[arg-type]
    if isinstance(t, type) and issubclass(t, (list,tuple)): return None
    if not isinstance(o, (str,list,tuple)): return o
    return res(o[-1]) if isinstance(o,(list,tuple)) else res(o)

def _form_arg(k, v, d):
    "Get type by accessing key `k` from `d`, and use to cast `v`"
    if v is None: return
    if not isinstance(v, (str,list,tuple)): return v
    anno = d.get(k, None)
    if not anno: return v
    return _fix_anno(anno, v)

@dataclass
class HttpHeader: k:str;v:str

def _to_htmx_header(s): return 'HX-' + s.replace('_', '-').title()

htmx_resps = dict(location=None, push_url=None, redirect=None, refresh=None, replace_url=None,
                 reswap=None, retarget=None, reselect=None, trigger=None, trigger_after_settle=None, trigger_after_swap=None)

@use_kwargs_dict(**htmx_resps)  # type: ignore[arg-type]
def HtmxResponseHeaders(**kwargs):
    "HTMX response headers"
    res = tuple(HttpHeader(_to_htmx_header(k), v) for k,v in kwargs.items())
    return res[0] if len(res)==1 else res

def _annotations(anno):
    "Same as `get_annotations`, but also works on namedtuples"
    if is_namedtuple(anno): return {o:str for o in anno._fields}
    return get_annotations(anno)

def _is_body(anno): return issubclass(anno, (dict,ns)) or hasattr(anno,'__from_request__') or _annotations(anno)

def _formitem(form, k):
    "Return single item `k` from `form` if len 1, otherwise return list"
    if isinstance(form, dict): return form.get(k)
    o = form.getlist(k)
    return o[0] if len(o) == 1 else o if o else None

def form2dict(form: FormData) -> dict:
    "Convert starlette form data to a dict"
    if isinstance(form, dict): return form
    return {k: _formitem(form, k) for k in form}

async def parse_form(req: Request) -> FormData:
    "Starlette errors on empty multipart forms, so this checks for that situation"
    ctype = req.headers.get("Content-Type", "")
    if ctype.startswith("multipart/form-data"):
        try: boundary = ctype.split("boundary=")[1].strip()
        except IndexError: raise HTTPException(400, "Invalid form-data: no boundary")
        if int(req.headers.get("Content-Length", "0")) <= len(boundary) + 6: return FormData()
        return await req.form()
    await req.body()
    return await req.json() if ctype == 'application/json' else await req.form()


async def _from_body(conn, p, data):
    "Create an instance of the annotated type from pre-parsed `data`"
    anno = p.annotation
    ctor = getattr(anno, '__from_request__', None)
    if ctor:
        ps = {k:v for k,v in _params(ctor).items() if k != 'cls'}
        kwargs = await _find_ps(conn, data, conn.headers, ps)
        return await maybe_await(ctor(**kwargs))
    d = _annotations(anno)
    cargs = {k: _form_arg(k, v, d) for k, v in data.items() if not d or k in d}
    return anno(**cargs)

class ApiReturn:
    @classmethod
    async def __from_request__(cls, data, req): return cls(req.headers.get('accept')=='application/json')
    def __init__(self, isapi=False): self.isapi = isapi
    def __call__(self, norm=None, **kw): return kw if self.isapi else norm
    def __bool__(self): return bool(self.isapi)

class JSONResponse(JSONResponseOrig):
    "Same as starlette's version, but auto-stringifies non serializable types"
    def render(self, content:Any)->bytes:
        def _default(o): return list(o) if is_listy(o) else str(o)
        res = json.dumps(content, ensure_ascii=False, allow_nan=False, indent=None, separators=(",",":"), default=_default)
        return res.encode("utf-8")


async def _find_p(conn, data, hdrs, arg:str, p:Parameter):
    "In `data` find param named `arg` of type in `p` (`arg` is ignored for body types)"
    anno = p.annotation
    if isinstance(anno, type) and not isinstance(anno, GenericAlias):
        if issubclass(anno, HtmxHeaders): return _get_htmx(hdrs)
        if issubclass(anno, Starlette): return conn.scope['app']
        if issubclass(anno, HTTPConnection): return conn
        if issubclass(anno, State): return conn.scope['app'].state
        if anno is dict: return data
        if _is_body(anno):
            if 'session'.startswith(arg.lower()): return conn.scope.get('session', {})
            return await _from_body(conn, p, data)
    if (msg := _check_anno(arg, anno)): return warn(msg)
    if anno is empty:
        if arg.lower()=='ws' or 'request'.startswith(arg.lower()): return conn
        if 'session'.startswith(arg.lower()): return conn.scope.get('session', {})
        if arg.lower()=='scope': return conn.scope
        if arg.lower()=='data': return data
        if arg.lower()=='htmx': return _get_htmx(hdrs)
        if arg.lower()=='app': return conn.scope['app']
        if arg.lower()=='state': return conn.scope['app'].state
        if arg.lower()=='auth': return conn.scope.get('auth', None)
        if arg.lower()=='send':
            assert not isinstance(conn, Request), "`send` requires a websocket, not a `Request`"
            raise NotImplementedError("WebSocket send is not available without the FastHTML server")
        if arg.lower()=='api': return ApiReturn(hdrs.get('accept')=='application/json')
        if arg.lower()=='body': return (await conn.body()).decode()
        if arg.lower() in ('hdrs','ftrs','bodykw','htmlkw'): return getattr(conn, arg.lower())
        return None
    res = conn.path_params.get(arg, None)
    if res in (empty,None): res = conn.cookies.get(arg, None)
    if res in (empty,None): res = hdrs.get(snake2hyphens(arg), None)
    if res in (empty,None): res = conn.query_params.getlist(arg)
    if res==[]: res = None
    if res in (empty,None): res = data.get(arg, None)
    if res in (empty,None):
        if p.default is empty:
            if isinstance(conn, Request): raise HTTPException(400, f"Missing required field: {arg}")
            raise ValueError(f"Missing required field: {arg}")
        res = p.default
    try: return _fix_anno(anno, res)
    except ValueError as e:
        if isinstance(conn, Request): raise HTTPException(404, f"{conn.url.path}: {e}") from None
        raise

async def _find_ps(conn, data, hdrs, params):
    if conn.query_params: data |= dict(conn.query_params)
    return {arg:await _find_p(conn, data, hdrs, arg, p) for arg,p in params.items()}

from inspect import Signature

def _params(f) -> Mapping[str, Parameter]:
    "Get the signature parameters of `f`"
    sig: Signature | None = signature_ex(f, True)
    if sig is not None:
        return sig.parameters
    return {}

async def _wrap_req(req, params):
    data = form2dict(await parse_form(req))
    return await _find_ps(req, data, req.headers, params)

def flat_xt(lst):
    "Flatten lists"
    result = []
    if isinstance(lst,(FT,str)): lst=[lst]
    for item in lst:
        if isinstance(item, (list,tuple)): result.extend(item)
        else: result.append(item)
    return tuple(result)

async def _handle(f, *args, **kwargs):
    return (await f(*args, **kwargs)) if is_async_callable(f) else await run_in_threadpool(f, *args, **kwargs)

def EventStream(s):
    "Create a text/event-stream response from `s`"
    return StreamingResponse(s, media_type="text/event-stream")

def uri(_arg, **kwargs):
    "Create a URI by URL-encoding `_arg` and appending query parameters from `kwargs`"
    return f"{quote(_arg)}/{urlencode(kwargs, doseq=True)}"

def decode_uri(s):
    "Decode a URI created by `uri()` back into argument and keyword dict"
    arg,_,kw = s.partition('/')
    return unquote(arg), {k:v[0] for k,v in parse_qs(kw).items()}

_verbs = dict(get='hx-get', post='hx-post', put='hx-put', delete='hx-delete', patch='hx-patch', link='href')

def _url_for(req, t):
    "Generate URL for route `t` using request `req`"
    if callable(t): t = t.__routename__
    kw: dict = {}
    if t.find('/')>-1 and (t.find('?')<0 or t.find('/')<t.find('?')): t,kw = decode_uri(t)
    t,m,q = t.partition('?')
    return f"{req.url_path_for(t, **kw)}{m}{q}"

def _find_targets(req, resp):
    "Find and convert route targets in response attributes to URLs"
    if isinstance(resp, tuple):
        for o in resp: _find_targets(req, o)
    if isinstance(resp, FT):
        for o in resp.children: _find_targets(req, o)
        for k,v in _verbs.items():
            t = resp.attrs.pop(k, None)
            if t: resp.attrs[v] = _url_for(req, t)

def _to_xml(req, resp, indent):
    "Convert response to XML string with target URL resolution"
    _find_targets(req, resp)
    return to_xml(resp, indent=indent)

_iter_typs = (tuple,list,map,filter,range,types.GeneratorType)

def flat_tuple(o):
    "Flatten nested iterables into a single tuple"
    result: list = []
    if not isinstance(o,_iter_typs): o=[o]
    o = list(o)
    for item in o:
        if isinstance(item, _iter_typs): result.extend(list(item))
        else: result.append(item)
    return tuple(result)

def noop_body(c, req):
    "Default Body wrap function which just returns the content"
    return c

def respond(req, heads, bdy):
    "Default FT response creation function"
    body_wrap = getattr(req, 'body_wrap', noop_body)
    params = inspect.signature(body_wrap).parameters
    bw_args = (bdy, req) if len(params)>1 else (bdy,)
    body = Body(body_wrap(*bw_args), *flat_xt(req.ftrs), **req.bodykw)  # type: ignore[arg-type]
    return Html(Head(*heads, *flat_xt(req.hdrs)), body, **req.htmlkw)  # type: ignore[arg-type]

def is_full_page(req, resp):
    "Check if response should be rendered as full page or fragment"
    if resp and any(getattr(o, 'tag', '')=='html' for o in resp): return True
    return 'hx-request' in req.headers and 'hx-history-restore-request' not in req.headers

def _part_resp(req, resp):
    "Partition response into HTTP headers, background tasks, and content"
    resp = flat_tuple(resp)
    resp = resp + tuple(getattr(req, 'injects', ()))
    http_hdrs,resp = partition(resp, risinstance(HttpHeader))
    tasks,resp = partition(resp, risinstance(BackgroundTask))
    kw: dict = {"headers": {"vary": "HX-Request, HX-History-Restore-Request"}}
    if http_hdrs: kw['headers'] |= {o.k:str(o.v) for o in http_hdrs}
    if tasks:
        ts = BackgroundTasks()
        for t in tasks: ts.tasks.append(t)
        kw['background'] = ts
    resp = tuple(resp)
    if len(resp)==1: resp = resp[0]
    return resp,kw

def _canonical(req):
    if not req.app.canonical: return []
    url = str(getattr(req, 'canonical', req.url)).replace('http://', 'https://', 1)
    return [Link(rel="canonical", href=url)]

def _xt_cts(req, resp):
    "Extract content and headers, render as full page or fragment"
    hdr_tags = 'title','meta','link','style','base'
    resp = tuplify(resp)
    heads,bdy = partition(resp, lambda o: getattr(o, 'tag', '') in hdr_tags)
    if not is_full_page(req, resp):
        title = [] if any(getattr(o, 'tag', '')=='title' for o in heads) else [Title(req.app.title)]
        resp = respond(req, [*heads, *title, *_canonical(req)], bdy)
    return _to_xml(req, resp, indent=fh_cfg.indent)

def _is_ft_resp(resp):
    "Check if response is a FastTag-compatible type"
    return isinstance(resp, _iter_typs+(HttpHeader,FT)) or hasattr(resp, '__ft__')

def _resp(req, resp, cls=empty, status_code=200):
    "Create appropriate HTTP response from request and response data"
    if not resp: resp=''
    if hasattr(resp, '__response__'): resp = resp.__response__(req)  # type: ignore[union-attr]
    if not (isinstance(cls, type) and issubclass(cls, Response)): cls=empty
    if isinstance(resp, FileResponse) and not os.path.isfile(cast(str | os.PathLike[str], resp.path)): raise HTTPException(404, str(resp.path))
    resp,kw = _part_resp(req, resp)
    if isinstance(resp, Response): return resp
    if cls is not empty: return cls(resp, status_code=status_code, **kw)  # type: ignore[misc]
    if _is_ft_resp(resp):
        cts = _xt_cts(req, resp)
        return HTMLResponse(cts, status_code=status_code, **kw)  # type: ignore[arg-type]
    if isinstance(resp, str): cls = HTMLResponse
    elif isinstance(resp, Mapping): cls = JSONResponse
    else:
        resp = str(resp)
        cls = HTMLResponse
    return cls(resp, status_code=status_code, **kw)  # type: ignore[misc]

class Redirect:
    "Use HTMX or Starlette RedirectResponse as required to redirect to `loc`"
    def __init__(self, loc): self.loc = loc
    def __response__(self, req):
        if 'hx-request' in req.headers: return HtmxResponseHeaders(redirect=self.loc)
        return RedirectResponse(self.loc, status_code=303)

htmx_exts = {
    "morph": "https://cdn.jsdelivr.net/npm/idiomorph@0.7.3/dist/idiomorph-ext.min.js",
    "head-support": "https://cdn.jsdelivr.net/npm/htmx-ext-head-support@2.0.4/head-support.js",
    "preload": "https://cdn.jsdelivr.net/npm/htmx-ext-preload@2.1.1/preload.js",
    "class-tools": "https://cdn.jsdelivr.net/npm/htmx-ext-class-tools@2.0.1/class-tools.js",
    "loading-states": "https://cdn.jsdelivr.net/npm/htmx-ext-loading-states@2.0.1/loading-states.js",
    "multi-swap": "https://cdn.jsdelivr.net/npm/htmx-ext-multi-swap@2.0.0/multi-swap.js",
    "path-deps": "https://cdn.jsdelivr.net/npm/htmx-ext-path-deps@2.0.0/path-deps.js",
    "remove-me": "https://cdn.jsdelivr.net/npm/htmx-ext-remove-me@2.0.0/remove-me.js",
    "debug": "https://unpkg.com/htmx.org@1.9.12/dist/ext/debug.js",
    "ws": "https://cdn.jsdelivr.net/npm/htmx-ext-ws@2.0.3/ws.js",
    "chunked-transfer": "https://cdn.jsdelivr.net/npm/htmx-ext-transfer-encoding-chunked@0.4.0/transfer-encoding-chunked.js"
}

htmxsrc   = Script(src="https://cdn.jsdelivr.net/npm/htmx.org@2.0.7/dist/htmx.js")
fhjsscr   = Script(src="https://cdn.jsdelivr.net/gh/answerdotai/fasthtml-js@1.0.12/fasthtml.js")
surrsrc   = Script(src="https://cdn.jsdelivr.net/gh/answerdotai/surreal@main/surreal.js")
scopesrc  = Script(src="https://cdn.jsdelivr.net/gh/gnat/css-scope-inline@main/script.js")
viewport  = Meta(name="viewport", content="width=device-width, initial-scale=1, viewport-fit=cover")
charset   = Meta(charset="utf-8")

def get_key(key=None, fname='.sesskey'):
    "Get session key from `key` param or read/create from file `fname`"
    if key: return key
    fname = Path(fname)
    if fname.exists(): return fname.read_text()
    key = str(uuid.uuid4())
    fname.write_text(key)
    return key

def _list(o):
    "Wrap non-list item in a list, returning empty list if None"
    return [] if not o else list(o) if isinstance(o, (tuple,list)) else [o]

def qp(p:str, **kw) -> str:
    "Add parameters kw to path p"
    def _sub(m):
        pre,post = m.groups()
        if pre not in kw: return f'{{{pre}{post or ""}}}'
        pre = kw.pop(pre)
        return '' if pre in (False,None) else str(pre)
    p = re.sub(r'\{([^:}]+)(:.+?)?}', _sub, p)
    return p + ('?' + urlencode({k:'' if v in (False,None) else v for k,v in kw.items()},doseq=True) if kw else '')

def def_hdrs(htmx=True, surreal=True):
    "Default headers for a FastHTML app"
    hdrs = []
    if surreal: hdrs = [surrsrc,scopesrc] + hdrs
    if htmx: hdrs = [htmxsrc,fhjsscr] + hdrs
    return [charset, viewport] + hdrs

cors_allow = Middleware(CORSMiddleware, allow_credentials=True,
                        allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

iframe_scr = Script(NotStr("""
    function sendmsg() {
        window.parent.postMessage({height: document.documentElement.offsetHeight}, '*');
    }
    window.onload = function() {
        sendmsg();
        document.body.addEventListener('htmx:afterSettle',    sendmsg);
        document.body.addEventListener('htmx:wsAfterMessage', sendmsg);
    };"""))

def cookie(key: str, value="", max_age=None, expires=None, path="/", domain=None, secure=False, httponly=False, samesite="lax",):
    "Create a 'set-cookie' `HttpHeader`"
    cookie = cookies.SimpleCookie()
    cookie[key] = value
    if max_age is not None: cookie[key]["max-age"] = max_age
    if expires is not None:
        cookie[key]["expires"] = format_datetime(expires, usegmt=True) if isinstance(expires, datetime) else expires  # type: ignore[arg-type]
    if path is not None: cookie[key]["path"] = path
    if domain is not None: cookie[key]["domain"] = domain
    if secure: cookie[key]["secure"] = True
    if httponly: cookie[key]["httponly"] = True
    if samesite is not None:
        assert samesite.lower() in [ "strict", "lax", "none", ], "must be 'strict', 'lax' or 'none'"
        cookie[key]["samesite"] = samesite
    cookie_val = cookie.output(header="").strip()
    return HttpHeader("set-cookie", cookie_val)

class FtResponse:
    "Wrap an FT response with any Starlette `Response`"
    def __init__(self, content, status_code:int=200, headers=None, cls=HTMLResponse, media_type:str|None=None, background: BackgroundTask | None = None):
        self.content,self.status_code,self.headers = content,status_code,headers
        self.cls,self.media_type,self.background = cls,media_type,background

    def __response__(self, req):
        resp,kw = _part_resp(req, self.content)
        cts = _xt_cts(req, resp)
        tasks,httphdrs = kw.get('background'),kw.get('headers')
        if not tasks: tasks = self.background
        headers = {**(self.headers or {}), **(httphdrs or {})}
        return self.cls(cts, status_code=self.status_code, headers=headers, media_type=self.media_type, background=tasks)  # type: ignore[arg-type]

def unqid(seeded=False):
    id4 = UUID(int=random.getrandbits(128), version=4) if seeded else uuid4()
    res = b64encode(id4.bytes)
    return '_' + res.decode().rstrip('=').translate(str.maketrans('+/', '_-'))

def _add_ids(s):
    if not isinstance(s, FT): return
    if not getattr(s, 'id', None): s.id = unqid()
    for c in s.children: _add_ids(c)
