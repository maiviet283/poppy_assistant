"""
conf.py — Config-contract của module: đọc & validate cấu hình từ ``settings.POPPY``.

Trụ #3 (MODULE_PLAN §3): mọi phần của module import cấu hình TỪ ĐÂY, không đọc
``os.environ`` rải rác. Khách khai MỘT dict ``POPPY`` trong settings.py của họ;
ở đây ta điền default, cho phép fallback biến môi trường (tiện dev), và fail loud
nếu thiếu cấu hình cấu trúc bắt buộc.

Truy cập lười (PEP 562 ``__getattr__``): giá trị chỉ được đọc từ settings khi có
ai đó thực sự dùng — tránh chạm settings lúc import (Trụ #4: zero side-effect).

    from poppy_assistant import conf
    conf.GEMINI_API_KEY   # đọc POPPY["GEMINI_API_KEY"] -> env -> default
"""

from __future__ import annotations

import os
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

_DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

# name -> (default, caster). caster đổi giá trị thô sang kiểu mong muốn.
_SPEC: dict[str, tuple] = {
    # --- Bắt buộc (validate lúc ready) ---
    "GEMINI_API_KEY": ("", str),
    "BUSINESS_NAME": ("", str),
    # --- Model ---
    "GEMINI_BASE_URL": (_DEFAULT_BASE_URL, str),
    "CHAT_MODEL": ("gemini-3.1-flash-lite", str),
    "CHAT_MODEL_FALLBACK": ("gemini-2.5-flash-lite", str),
    "VOICE_MODEL": ("gemini-3.1-flash-live-preview", str),
    # --- Nhân cách & luật (config-as-data) ---
    "ASSISTANT_NAME": ("Poppy", str),
    "TONE": ("warm, friendly and concise", str),
    "CUSTOM_RULES": ("", str),
    "TIMEZONE": ("Asia/Ho_Chi_Minh", str),
    # --- Tool ---
    "MAX_TOOL_ROUNDS": (5, int),
    # --- Adapter ---
    "BOOKING_BACKEND": ("poppy_assistant.booking.backends.DefaultBookingBackend", str),
    # --- RAG ---
    "CHROMA_COLLECTION": ("poppy_docs", str),
    "RAG_TOP_K": (4, int),
    # --- Telegram ---
    "TELEGRAM_BOT_TOKEN": ("", str),
    "TELEGRAM_CHAT_ID": ("", str),
    # --- Twilio (optional) ---
    "TWILIO_ACCOUNT_SID": ("", str),
    "TWILIO_AUTH_TOKEN": ("", str),
    "TWILIO_FROM_NUMBER": ("", str),
    "TWILIO_DEFAULT_COUNTRY_CODE": ("+61", str),
    "PUBLIC_BASE_URL": ("", str),
}

# Key bắt buộc phải có (cấu trúc) — thiếu là lỗi cấu hình, fail loud lúc khởi động.
_REQUIRED = ("BUSINESS_NAME",)


def _raw() -> dict:
    return getattr(settings, "POPPY", None) or {}


def _lookup(name: str, default, caster):
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
    base = getattr(settings, "BASE_DIR", None)
    return Path(base) if base else Path.cwd()


def _path_setting(name: str, default_rel: str) -> Path:
    raw = _raw().get(name) or os.getenv(name)
    if raw:
        return Path(raw).resolve()
    return (_base_dir() / default_rel).resolve()


# PEP 562: tính giá trị khi được truy cập (lười), không chạm settings lúc import.
def __getattr__(name: str):
    if name in _SPEC:
        default, caster = _SPEC[name]
        return _lookup(name, default, caster)
    if name == "DOCS_DIR":
        return _path_setting("DOCS_DIR", "poppy_docs")
    if name == "CHROMA_DB_DIR":
        return _path_setting("CHROMA_DB_DIR", "poppy_chroma")
    if name == "ENABLED_TOOLS":
        # None = bật MỌI tool. Hoặc list tag: ["booking", "faq"].
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
    """Kiểm cấu hình lúc khởi động (gọi trong AppConfig.ready).

    - Thiếu key cấu trúc (BUSINESS_NAME) -> ImproperlyConfigured (fail loud).
    - Thiếu GEMINI_API_KEY -> chỉ cảnh báo: đây là lỗi RUNTIME, surface ở lượt chat
      đầu tiên với thông điệp rõ ràng, không nên chặn cả `manage.py check`/migrate.
    """
    raw = _raw()
    missing = [k for k in _REQUIRED if not _lookup(k, *_SPEC[k])]
    if missing:
        raise ImproperlyConfigured(
            "Thiếu cấu hình bắt buộc trong settings.POPPY: "
            + ", ".join(missing)
            + ". Ví dụ: POPPY = {'BUSINESS_NAME': 'Tiệm X', 'GEMINI_API_KEY': '...'}"
        )
    if not _lookup("GEMINI_API_KEY", *_SPEC["GEMINI_API_KEY"]):
        print(
            "[POPPY] ⚠ Chưa có POPPY['GEMINI_API_KEY'] — chat/voice sẽ báo lỗi khi "
            "gọi model cho tới khi bạn cấu hình key.",
            flush=True,
        )
    if not isinstance(raw, dict):
        raise ImproperlyConfigured("settings.POPPY phải là một dict.")


def summary() -> str:
    """Tóm tắt cấu hình (đã ẩn key) để in lúc ingest / debug."""
    key = __getattr__("GEMINI_API_KEY")
    masked = key[:6] + "..." if key else "(trống)"
    return (
        "Cấu hình Poppy (thuần Gemini):\n"
        f"  - Doanh nghiệp      : {__getattr__('BUSINESS_NAME') or '(chưa đặt)'}\n"
        f"  - Model chat        : {__getattr__('CHAT_MODEL')} (dự phòng {__getattr__('CHAT_MODEL_FALLBACK')})\n"
        f"  - Model voice       : {__getattr__('VOICE_MODEL')}\n"
        f"  - Embedding         : local all-MiniLM-L6-v2 (miễn phí, chạy trên máy)\n"
        f"  - Gemini key        : {masked}\n"
        f"  - Telegram          : {'BẬT' if __getattr__('TELEGRAM_ENABLED') else 'TẮT (giả lập)'}\n"
        f"  - Booking backend   : {__getattr__('BOOKING_BACKEND')}\n"
        f"  - Thư mục tài liệu  : {__getattr__('DOCS_DIR')}\n"
        f"  - Vector DB         : {__getattr__('CHROMA_DB_DIR')}\n"
        f"  - RAG top_k         : {__getattr__('RAG_TOP_K')}"
    )
