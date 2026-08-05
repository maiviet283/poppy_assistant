"""
notify.py — Báo nhân viên khi Poppy ghi dữ liệu (đặt/sửa/hủy lịch).

Model KHÔNG tự gửi; nó chỉ đề nghị, hàm dưới đây mới thực sự gọi Telegram Bot API.
Chưa cấu hình token -> chạy chế độ giả lập (in log) để tiện dev/demo. Mọi lỗi được
bắt và trả về dict (không ném exception) để vòng hội thoại không sập giữa chừng.
"""

from __future__ import annotations

import requests

from poppy_assistant import conf


def notify_staff(text: str) -> dict:
    """Gửi một tin nhắn văn bản tới kênh nhân viên đã cấu hình (Telegram)."""
    if not conf.TELEGRAM_ENABLED:
        print("\n[NOTIFY — CHẾ ĐỘ GIẢ LẬP] Tin nhắn lẽ ra sẽ gửi đi:")
        print(f"  {text}\n", flush=True)
        return {"ok": True, "detail": "Đã in ra màn hình (chế độ giả lập)."}

    url = f"https://api.telegram.org/bot{conf.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": conf.TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return {"ok": True, "detail": "Đã gửi thông báo thành công."}
    except requests.RequestException as exc:
        return {"ok": False, "detail": f"Lỗi khi gửi thông báo: {exc}"}
