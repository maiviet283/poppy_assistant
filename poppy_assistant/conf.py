from __future__ import annotations

import os
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

_DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

# name -> (default, caster)
_SPEC: dict[str, tuple] = {
    "GEMINI_API_KEY": ("", str),
    "BUSINESS_NAME": ("", str),
    "GEMINI_BASE_URL": (_DEFAULT_BASE_URL, str),
    "CHAT_MODEL": ("gemini-3.1-flash-lite", str),
    "CHAT_MODEL_FALLBACK": ("gemini-2.5-flash-lite", str),
    "VOICE_MODEL": ("gemini-3.1-flash-live-preview", str),
    "ASSISTANT_NAME": ("Poppy", str),
    "TONE": ("warm, friendly and concise", str),
    "CUSTOM_RULES": ("", str),
    "TIMEZONE": ("Asia/Ho_Chi_Minh", str),
    "MAX_TOOL_ROUNDS": (5, int),
    "BOOKING_BACKEND": ("poppy_assistant.booking.backends.DefaultBookingBackend", str),
    "CHROMA_COLLECTION": ("poppy_docs", str),
    "RAG_TOP_K": (4, int),
    "TELEGRAM_BOT_TOKEN": ("", str),
    "TELEGRAM_CHAT_ID": ("", str),
    "TWILIO_ACCOUNT_SID": ("", str),
    "TWILIO_AUTH_TOKEN": ("", str),
    "TWILIO_FROM_NUMBER": ("", str),
    "TWILIO_DEFAULT_COUNTRY_CODE": ("+61", str),
    "PUBLIC_BASE_URL": ("", str),
}

# Structural keys that must be present; a missing one is a startup error.
_REQUIRED = ("BUSINESS_NAME",)


def _raw() -> dict:
    """Return the host project's ``settings.POPPY`` dict (empty if unset)."""
    return getattr(settings, "POPPY", None) or {}


def _lookup(name: str, default, caster):
    """Resolve a setting: POPPY dict -> environment variable -> default."""
    raw = _raw()
    val = raw.get(name)
    if val is None or val == "":
        env = os.getenv(name)
        val = env if env not in (None, "") else default
    try:
        return caster(val)
    except (TypeError, ValueError):
        return default


def _base_dir() -> Path:
    """Return the host project's BASE_DIR, or the current directory."""
    base = getattr(settings, "BASE_DIR", None)
    return Path(base) if base else Path.cwd()


def _path_setting(name: str, default_rel: str) -> Path:
    """Resolve a path setting to an absolute path, relative to BASE_DIR by default."""
    raw = _raw().get(name) or os.getenv(name)
    if raw:
        return Path(raw).resolve()
    return (_base_dir() / default_rel).resolve()


def __getattr__(name: str):
    """Resolve a config value lazily on attribute access (PEP 562)."""
    if name in _SPEC:
        default, caster = _SPEC[name]
        return _lookup(name, default, caster)
    if name == "DOCS_DIR":
        return _path_setting("DOCS_DIR", "poppy_docs")
    if name == "CHROMA_DB_DIR":
        return _path_setting("CHROMA_DB_DIR", "poppy_chroma")
    if name == "ENABLED_TOOLS":
        # None enables every tool; otherwise a list of tags, e.g. ["booking", "faq"].
        return _raw().get("ENABLED_TOOLS")
    if name == "TELEGRAM_ENABLED":
        return bool(__getattr__("TELEGRAM_BOT_TOKEN") and __getattr__("TELEGRAM_CHAT_ID"))
    if name == "TWILIO_ENABLED":
        return bool(
            __getattr__("TWILIO_ACCOUNT_SID")
            and __getattr__("TWILIO_AUTH_TOKEN")
            and __getattr__("TWILIO_FROM_NUMBER")
        )
    raise AttributeError(f"module 'poppy_assistant.conf' has no attribute {name!r}")


def validate() -> None:
    """Validate configuration at startup.

    A missing structural key raises ImproperlyConfigured. A missing API key only
    warns, since it is a runtime error surfaced on the first chat turn.
    """
    raw = _raw()
    if not isinstance(raw, dict):
        raise ImproperlyConfigured("settings.POPPY must be a dict.")

    missing = [k for k in _REQUIRED if not _lookup(k, *_SPEC[k])]
    if missing:
        raise ImproperlyConfigured(
            "Missing required keys in settings.POPPY: "
            + ", ".join(missing)
            + ". Example: POPPY = {'BUSINESS_NAME': 'Acme', 'GEMINI_API_KEY': '...'}"
        )
    if not _lookup("GEMINI_API_KEY", *_SPEC["GEMINI_API_KEY"]):
        print(
            "[POPPY] Warning: POPPY['GEMINI_API_KEY'] is not set; chat and voice will "
            "error when calling the model until it is configured.",
            flush=True,
        )


def summary() -> str:
    """Return a human-readable config summary with the API key masked."""
    key = __getattr__("GEMINI_API_KEY")
    masked = key[:6] + "..." if key else "(empty)"
    return (
        "Poppy configuration (Gemini):\n"
        f"  - Business        : {__getattr__('BUSINESS_NAME') or '(unset)'}\n"
        f"  - Chat model      : {__getattr__('CHAT_MODEL')} (fallback {__getattr__('CHAT_MODEL_FALLBACK')})\n"
        f"  - Voice model     : {__getattr__('VOICE_MODEL')}\n"
        f"  - Embedding       : local all-MiniLM-L6-v2\n"
        f"  - Gemini key      : {masked}\n"
        f"  - Telegram        : {'on' if __getattr__('TELEGRAM_ENABLED') else 'off (simulated)'}\n"
        f"  - Booking backend : {__getattr__('BOOKING_BACKEND')}\n"
        f"  - Docs dir        : {__getattr__('DOCS_DIR')}\n"
        f"  - Vector DB       : {__getattr__('CHROMA_DB_DIR')}\n"
        f"  - RAG top_k       : {__getattr__('RAG_TOP_K')}"
    )
