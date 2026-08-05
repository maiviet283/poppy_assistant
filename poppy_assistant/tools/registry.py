from __future__ import annotations

import json

# name -> spec
_REGISTRY: dict[str, dict] = {}


def register(name: str, description: str, parameters: dict, handler, tags=(), wants_source: bool = False) -> None:
    """Register a tool. Called at import time from the tools/* modules."""
    _REGISTRY[name] = {
        "name": name,
        "description": description,
        "parameters": parameters or {"type": "object", "properties": {}},
        "handler": handler,
        "tags": tuple(tags),
        "wants_source": wants_source,
    }


def _enabled_names(enabled) -> list[str]:
    """Return the names of enabled tools; None enables all, else filter by tag."""
    if enabled is None:
        return list(_REGISTRY)
    allow = set(enabled)
    return [n for n, s in _REGISTRY.items() if (not s["tags"]) or (allow & set(s["tags"]))]


def openai_schemas(enabled=None) -> list[dict]:
    """Return enabled tools as OpenAI-style function schemas (for chat)."""
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
    """Invoke a tool handler by name, injecting ``source`` when it wants it."""
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
    """Run a tool from a JSON argument string (chat) and return a JSON result."""
    try:
        kwargs = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError:
        return json.dumps({"ok": False, "detail": "Tool arguments were not valid JSON."}, ensure_ascii=False)
    return json.dumps(_dispatch(name, kwargs, source), ensure_ascii=False)


def run_tool(name: str, args: dict, source: str = "voice") -> dict:
    """Run a tool from a dict of arguments (voice) and return a dict result."""
    return _dispatch(name, dict(args or {}), source)


def genai_tool(enabled=None):
    """Return a google-genai ``Tool`` wrapping the enabled function declarations.

    Imported lazily so chat-only installs without google-genai keep working.
    """
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
