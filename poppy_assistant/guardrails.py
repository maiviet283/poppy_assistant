"""
guardrails.py — Cửa chặn confirm-before-commit ở TẦNG TOOL (MODULE_PLAN §8).

Nguyên tắc bất biến (AI_PLATFORM §2.3): prompt có thể bị model phớt lờ; cửa chặn
trong code thì không. Đây là các helper THUẦN LOGIC (không tốn token, unit-test
được) mà booking/service.py dùng để dựng máy trạng thái đặt lịch.
"""

from __future__ import annotations


def is_true(value) -> bool:
    """Chuẩn hóa cờ xác nhận — model có thể gửi bool hoặc chuỗi 'true'/'yes'/'1'."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes", "y")


def missing_fields(fields: dict, required: list[tuple[str, str]]) -> list[str]:
    """Trả về danh sách MÔ TẢ (tiếng Anh) của các trường bắt buộc còn trống.

    ``required``: list các cặp (key, human_label). ``fields``: dict giá trị đã chuẩn hóa.
    """
    return [label for key, label in required if not (fields.get(key) or "").strip()]
