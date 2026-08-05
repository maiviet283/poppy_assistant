"""
registry.py — Tool Registry: khai báo công cụ MỘT NƠI (MODULE_PLAN §8, Trụ registry).

Mỗi tool đăng ký: name + description + parameters (JSON Schema kiểu OpenAI) + handler
+ tags. Cả hai kênh đọc CÙNG registry này:
  - Chat  : ``openai_schemas()`` (định dạng OpenAI) + ``execute_tool()`` (trả JSON).
  - Voice : ``genai_tool()`` (đổi sang google-genai FunctionDeclaration) + ``run_tool()``.

Thêm tool = 1 lần ``register(...)`` trong tools/*.py — KHÔNG còn cảnh sửa 4 chỗ như
demo. ``enabled`` (POPPY['ENABLED_TOOLS']) lọc tool theo tag per doanh nghiệp.

Mô tả tool + giá trị trả về viết TIẾNG ANH (Poppy mirror ngôn ngữ khách — bài học demo).
"""

from __future__ import annotations

import json

# name -> spec
_REGISTRY: dict[str, dict] = {}


def register(name: str, description: str, parameters: dict, handler, tags=(), wants_source: bool = False) -> None:
    """Đăng ký một tool vào registry (gọi lúc import trong tools/*.py)."""
    _REGISTRY[name] = {
        "name": name,
        "description": description,
        "parameters": parameters or {"type": "object", "properties": {}},
        "handler": handler,
        "tags": tuple(tags),
        "wants_source": wants_source,
    }


def _enabled_names(enabled) -> list[str]:
    """Tên các tool được bật theo danh sách tag (None = tất cả)."""
    if enabled is None:
        return list(_REGISTRY)
    allow = set(enabled)
    return [n for n, s in _REGISTRY.items() if (not s["tags"]) or (allow & set(s["tags"]))]


# --- Chat: schema OpenAI + thực thi trả JSON --------------------------------
def openai_schemas(enabled=None) -> list[dict]:
    out = []
    for name in _enabled_names(enabled):
        s = _REGISTRY[name]
        out.append(
            {
                "type": "function",
                "function": {
                    "name": s["name"],
                    "description": s["description"],
                    "parameters": s["parameters"],
                },
            }
        )
    return out


def _dispatch(name: str, kwargs: dict, source: str) -> dict:
    spec = _REGISTRY.get(name)
    if spec is None:
        return {"ok": False, "detail": f"Unknown tool '{name}'."}
    if spec["wants_source"]:
        kwargs = {**kwargs, "source": source}
    try:
        return spec["handler"](**kwargs)
    except TypeError as exc:
        return {"ok": False, "detail": f"Bad tool arguments: {exc}"}


def execute_tool(name: str, arguments_json: str, source: str = "chat") -> str:
    """Chat: chạy tool theo tên + tham số JSON (do model sinh), trả JSON kết quả."""
    try:
        kwargs = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError:
        return json.dumps({"ok": False, "detail": "Tool arguments were not valid JSON."}, ensure_ascii=False)
    return json.dumps(_dispatch(name, kwargs, source), ensure_ascii=False)


def run_tool(name: str, args: dict, source: str = "voice") -> dict:
    """Voice: chạy tool theo tên + dict tham số, trả dict kết quả cho Gemini Live."""
    return _dispatch(name, dict(args or {}), source)


# --- Voice: đổi schema OpenAI -> google-genai (lazy import, chỉ khi bật voice) ---
def genai_tool(enabled=None):
    """Trả về một ``types.Tool`` gói mọi FunctionDeclaration được bật (dùng cho Live)."""
    from google.genai import types

    typemap = {
        "string": types.Type.STRING,
        "integer": types.Type.INTEGER,
        "number": types.Type.NUMBER,
        "boolean": types.Type.BOOLEAN,
        "object": types.Type.OBJECT,
        "array": types.Type.ARRAY,
    }

    declarations = []
    for name in _enabled_names(enabled):
        s = _REGISTRY[name]
        params = s["parameters"] or {}
        props = {}
        for pname, pschema in (params.get("properties") or {}).items():
            props[pname] = types.Schema(
                type=typemap.get(pschema.get("type", "string"), types.Type.STRING),
                description=pschema.get("description", ""),
            )
        declarations.append(
            types.FunctionDeclaration(
                name=s["name"],
                description=s["description"],
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties=props,
                    required=params.get("required") or None,
                ),
            )
        )
    return types.Tool(function_declarations=declarations)
