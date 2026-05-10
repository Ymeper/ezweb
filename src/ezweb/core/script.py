"""Script interpreter for ezweb monolithic mode.

Supports nested DSL operations for dynamic content generation:

  File operations:
    ``read_file``    – read a file from disk, optionally save to a variable
    ``write_file``   – write content to a file
    ``delete_file``  – delete a file
    ``file_exists``  – check whether a file exists

  Variable & data:
    ``variable``       – reference a previously stored variable
    ``json_analyze``   – parse JSON and extract a value by key
    ``json_stringify`` – convert a value to a JSON string

  String operations:
    ``concat``   – concatenate multiple values
    ``replace``  – replace substring occurrences
    ``split``    – split a string into a list
    ``join``     – join a list with a separator
    ``trim``     – strip leading/trailing whitespace
    ``upper``    – convert to uppercase
    ``lower``    – convert to lowercase

  Sequence operations:
    ``slice``  – slice a string or list
    ``length`` – get length of a string or list
    ``at``     – retrieve an element by index

  Math operations:
    ``add``  – addition
    ``sub``  – subtraction
    ``mul``  – multiplication
    ``div``  – division
    ``mod``  – modulo

  Control flow & utilities:
    ``return``    – terminate execution and return a value
    ``format``    – format a template string with variables
    ``timestamp`` – get current Unix timestamp / formatted datetime
    ``if``        – conditional value selection
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ScriptError(Exception):
    """Raised when a script operation fails."""


def _is_command_dict(value: dict[str, Any], command_keys: frozenset[str]) -> bool:
    return bool(command_keys & value.keys())


class ScriptInterpreter:
    """Executes ezweb DSL scripts for dynamic content generation."""

    _COMMAND_KEYS = frozenset({
        "read_file", "write_file", "delete_file", "file_exists",
        "variable",
        "json_analyze", "json_stringify",
        "return",
        "concat", "replace", "split", "join", "trim", "upper", "lower",
        "slice", "length", "at",
        "add", "sub", "mul", "div", "mod",
        "format", "timestamp", "if",
    })

    def __init__(self, base_path: str | Path | None = None) -> None:
        self._variables: dict[str, Any] = {}
        self._base_path = Path(base_path) if base_path else Path.cwd()

    # Public API

    def execute(self, script_data: dict[str, Any]) -> Any:
        """Execute a script and return the result."""
        if not isinstance(script_data, dict):
            raise ScriptError(f"Script must be a dict, got {type(script_data).__name__}")

        result = None
        for key in list(script_data.keys()):
            if key == "return":
                action = script_data[key]
                if not isinstance(action, dict):
                    raise ScriptError("'return' action must be a dict")
                return self._eval(action.get("data"))

            result = self._dispatch(key, script_data[key])

        return result

    # Recursive evaluator

    def _eval(self, expr: Any) -> Any:
        """Evaluate any expression recursively, resolving nested commands."""
        if not isinstance(expr, dict):
            return expr

        if not _is_command_dict(expr, self._COMMAND_KEYS):
            return expr

        for cmd in self._COMMAND_KEYS & expr.keys():
            return self._dispatch(cmd, expr[cmd])

        return expr

    # Dispatch table

    def _dispatch(self, cmd: str, action: Any) -> Any:
        """Route a command name to its implementation."""
        if cmd == "variable":
            return self._do_variable({"variable": action})

        _dispatch_map = {
            "read_file":      self._do_read_file,
            "write_file":     self._do_write_file,
            "delete_file":    self._do_delete_file,
            "file_exists":    self._do_file_exists,
            "json_analyze":   self._do_json_analyze,
            "json_stringify": self._do_json_stringify,
            "concat":  self._do_concat,
            "replace": self._do_replace,
            "split":   self._do_split,
            "join":    self._do_join,
            "trim":    self._do_trim,
            "upper":   self._do_upper,
            "lower":   self._do_lower,
            "slice":  self._do_slice,
            "length": self._do_length,
            "at":     self._do_at,
            "add": self._do_add,
            "sub": self._do_sub,
            "mul": self._do_mul,
            "div": self._do_div,
            "mod": self._do_mod,
            "format":    self._do_format,
            "timestamp": self._do_timestamp,
            "if":        self._do_if,
        }
        handler = _dispatch_map.get(cmd)
        if handler is None:
            raise ScriptError(f"Unknown command {cmd!r}")
        return handler(action)
    
    # Helper: optional save

    def _maybe_save(self, action: dict[str, Any], value: Any) -> None:
        save = action.get("save")
        if save is not None:
            if not isinstance(save, dict) or "variable" not in save:
                raise ScriptError("'save' must be a dict like {'variable': 'name'}")
            var_name = save["variable"]
            if not isinstance(var_name, str):
                raise ScriptError(f"Variable name must be a string, got {type(var_name).__name__}")
            self._variables[var_name] = value

    @staticmethod
    def _require_str(value: Any, label: str) -> str:
        if not isinstance(value, str):
            raise ScriptError(f"{label} must be a string, got {type(value).__name__}")
        return value

    @staticmethod
    def _require_num(value: Any, label: str) -> int | float:
        if not isinstance(value, (int, float)):
            raise ScriptError(f"{label} must be a number, got {type(value).__name__}")
        return value
    
    # File operations

    def _resolve_path(self, file_ref: Any) -> Path:
        path_str = self._require_str(self._eval(file_ref), "'file'")
        return self._base_path / path_str

    def _do_read_file(self, action: dict[str, Any]) -> str:
        full_path = self._resolve_path(action.get("file"))
        try:
            content = full_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise ScriptError(f"File not found: {full_path}")
        except OSError as e:
            raise ScriptError(f"Failed to read '{full_path}': {e}")
        self._maybe_save(action, content)
        return content

    def _do_write_file(self, action: dict[str, Any]) -> dict[str, Any]:
        full_path = self._resolve_path(action.get("file"))
        content = self._eval(action.get("content"))
        if content is None:
            raise ScriptError("'write_file' requires a 'content' key")
        try:
            full_path.write_text(str(content), encoding="utf-8")
        except OSError as e:
            raise ScriptError(f"Failed to write '{full_path}': {e}")
        result = {"file": str(full_path), "written": True}
        self._maybe_save(action, result)
        return result

    def _do_delete_file(self, action: dict[str, Any]) -> dict[str, Any]:
        full_path = self._resolve_path(action.get("file"))
        try:
            full_path.unlink()
            result = {"file": str(full_path), "deleted": True}
        except FileNotFoundError:
            result = {"file": str(full_path), "deleted": False, "reason": "not_found"}
        except OSError as e:
            raise ScriptError(f"Failed to delete '{full_path}': {e}")
        self._maybe_save(action, result)
        return result

    def _do_file_exists(self, action: dict[str, Any]) -> bool:
        full_path = self._resolve_path(action.get("file"))
        result = full_path.exists()
        self._maybe_save(action, result)
        return result

    # Variable

    def _do_variable(self, action: dict[str, Any]) -> Any:
        var_name = action.get("variable")
        if var_name is None:
            raise ScriptError("'variable' requires a 'variable' key with the variable name")
        var_name = self._require_str(var_name, "Variable name")
        if var_name not in self._variables:
            raise ScriptError(f"Variable '{var_name}' is not defined")
        return self._variables[var_name]
    
    # JSON operations

    def _do_json_analyze(self, action: dict[str, Any]) -> Any:
        data = action.get("data")
        if data is None:
            raise ScriptError("'json_analyze' requires a 'data' key")
        key = action.get("key")
        if key is None:
            raise ScriptError("'json_analyze' requires a 'key' key")
        key = self._require_str(key, "'key'")

        raw = self._eval(data)
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as e:
                raise ScriptError(f"Failed to parse JSON: {e}")
        elif isinstance(raw, dict):
            parsed = raw
        else:
            raise ScriptError(
                f"'json_analyze' data must resolve to a JSON string or dict, "
                f"got {type(raw).__name__}"
            )

        if key not in parsed:
            raise ScriptError(f"Key '{key}' not found in JSON data")
        result = parsed[key]
        self._maybe_save(action, result)
        return result

    def _do_json_stringify(self, action: dict[str, Any]) -> str:
        data = action.get("data")
        if data is None:
            raise ScriptError("'json_stringify' requires a 'data' key")
        indent = action.get("indent")
        result = json.dumps(self._eval(data), indent=indent, ensure_ascii=False)
        self._maybe_save(action, result)
        return result
    
    # String operations

    def _do_concat(self, action: dict[str, Any]) -> str:
        values = action.get("values")
        if not isinstance(values, list):
            raise ScriptError("'concat' requires a 'values' key with a list")
        result = "".join(str(self._eval(v)) for v in values)
        self._maybe_save(action, result)
        return result

    def _do_replace(self, action: dict[str, Any]) -> str:
        text = self._require_str(self._eval(action.get("text")), "'text'")
        old = self._require_str(self._eval(action.get("old")), "'old'")
        new = str(self._eval(action.get("new", "")))
        count = action.get("count", -1)
        result = text.replace(old, new, count if isinstance(count, int) else -1)
        self._maybe_save(action, result)
        return result

    def _do_split(self, action: dict[str, Any]) -> list[str]:
        text = self._require_str(self._eval(action.get("text")), "'text'")
        sep = self._eval(action.get("separator", ","))
        sep = str(sep) if sep is not None else None
        maxsplit = action.get("maxsplit", -1)
        result = text.split(sep, maxsplit if isinstance(maxsplit, int) else -1)
        self._maybe_save(action, result)
        return result

    def _do_join(self, action: dict[str, Any]) -> str:
        sep = str(self._eval(action.get("separator", "")))
        values = self._eval(action.get("values"))
        if not isinstance(values, list):
            raise ScriptError("'join' requires a 'values' key with a list")
        result = sep.join(str(v) for v in values)
        self._maybe_save(action, result)
        return result

    def _do_trim(self, action: dict[str, Any]) -> str:
        text = self._require_str(self._eval(action.get("text")), "'text'")
        result = text.strip()
        self._maybe_save(action, result)
        return result

    def _do_upper(self, action: dict[str, Any]) -> str:
        text = self._require_str(self._eval(action.get("text")), "'text'")
        result = text.upper()
        self._maybe_save(action, result)
        return result

    def _do_lower(self, action: dict[str, Any]) -> str:
        text = self._require_str(self._eval(action.get("text")), "'text'")
        result = text.lower()
        self._maybe_save(action, result)
        return result

    # Sequence operations

    def _do_slice(self, action: dict[str, Any]) -> Any:
        seq = self._eval(action.get("data"))
        start = action.get("start", 0)
        end = action.get("end")
        step = action.get("step", 1)
        if isinstance(seq, str):
            result = seq[start:end:step]
        elif isinstance(seq, list):
            result = seq[start:end:step]
        else:
            raise ScriptError(f"'slice' requires a string or list, got {type(seq).__name__}")
        self._maybe_save(action, result)
        return result

    def _do_length(self, action: dict[str, Any]) -> int:
        data = self._eval(action.get("data"))
        if not isinstance(data, (str, list, dict)):
            raise ScriptError(f"'length' requires a string, list, or dict, got {type(data).__name__}")
        result = len(data)
        self._maybe_save(action, result)
        return result

    def _do_at(self, action: dict[str, Any]) -> Any:
        data = self._eval(action.get("data"))
        index = action.get("index")
        if index is None:
            raise ScriptError("'at' requires an 'index' key")
        if not isinstance(index, int):
            raise ScriptError(f"'index' must be an integer, got {type(index).__name__}")
        if not isinstance(data, (str, list)):
            raise ScriptError(f"'at' requires a string or list, got {type(data).__name__}")
        try:
            result = data[index]
        except IndexError:
            raise ScriptError(f"Index {index} out of range for data of length {len(data)}")
        self._maybe_save(action, result)
        return result

    # Math operations

    def _math_binop(self, action: dict[str, Any], op_label: str, op) -> int | float:
        a = self._require_num(self._eval(action.get("a")), f"'{op_label}' 'a'")
        b = self._require_num(self._eval(action.get("b")), f"'{op_label}' 'b'")
        try:
            result = op(a, b)
        except ZeroDivisionError:
            raise ScriptError(f"Division by zero in '{op_label}'")
        self._maybe_save(action, result)
        return result

    def _do_add(self, action: dict[str, Any]) -> int | float:
        return self._math_binop(action, "add", lambda a, b: a + b)

    def _do_sub(self, action: dict[str, Any]) -> int | float:
        return self._math_binop(action, "sub", lambda a, b: a - b)

    def _do_mul(self, action: dict[str, Any]) -> int | float:
        return self._math_binop(action, "mul", lambda a, b: a * b)

    def _do_div(self, action: dict[str, Any]) -> int | float:
        return self._math_binop(action, "div", lambda a, b: a / b)

    def _do_mod(self, action: dict[str, Any]) -> int | float:
        return self._math_binop(action, "mod", lambda a, b: a % b)

    # Utility operations

    def _do_format(self, action: dict[str, Any]) -> str:
        template = self._require_str(self._eval(action.get("template")), "'template'")
        data = action.get("data", {})
        if isinstance(data, dict) and _is_command_dict(data, self._COMMAND_KEYS):
            data = self._eval(data)
        if isinstance(data, dict):
            data = {k: self._eval(v) for k, v in data.items()}
        if not isinstance(data, dict):
            raise ScriptError(f"'format' 'data' must resolve to a dict, got {type(data).__name__}")
        try:
            result = template.format_map(data)
        except KeyError as e:
            raise ScriptError(f"Missing format key: {e}")
        self._maybe_save(action, result)
        return result

    def _do_timestamp(self, action: dict[str, Any]) -> int | str:
        fmt = action.get("format")
        if fmt is not None:
            fmt = self._require_str(self._eval(fmt), "'format'")
            tz_offset = action.get("utc_offset")
            tz = timezone.utc
            if tz_offset is not None:
                from datetime import timedelta
                tz = timezone(timedelta(hours=float(tz_offset)))
            result = datetime.now(tz=tz).strftime(fmt)
        else:
            result = int(time.time())
        self._maybe_save(action, result)
        return result

    def _do_if(self, action: dict[str, Any]) -> Any:
        cond = self._eval(action.get("condition"))
        then_branch = action.get("then")
        else_branch = action.get("else")
        result = self._eval(then_branch) if cond else self._eval(else_branch)
        self._maybe_save(action, result)
        return result
