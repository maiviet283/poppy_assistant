"""
tools — Tool Registry + các tool đã đăng ký.

Import package này là mọi tool tự đăng ký (booking_tools, knowledge_tools). Public
API dùng lại từ registry để nơi khác gọi gọn: ``from poppy_assistant import tools``.
"""

from __future__ import annotations

from poppy_assistant.tools.registry import (  # noqa: F401
    execute_tool,
    genai_tool,
    openai_schemas,
    register,
    run_tool,
)

# Import để KÍCH HOẠT đăng ký (thứ tự không quan trọng).
from poppy_assistant.tools import booking_tools, knowledge_tools  # noqa: E402,F401
