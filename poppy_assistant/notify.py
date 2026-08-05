from __future__ import annotations

import requests

from poppy_assistant import conf


def notify_staff(text: str) -> dict:
    """Send a text message to the configured staff channel (Telegram).

    When no token is configured it runs in simulation mode and prints the message.
    Errors are caught and returned as a dict so a conversation never crashes here.
    """
    if not conf.TELEGRAM_ENABLED:
        print("\n[NOTIFY — SIMULATED] Would have sent:")
        print(f"  {text}\n", flush=True)
        return {"ok": True, "detail": "Printed to console (simulation mode)."}

    url = f"https://api.telegram.org/bot{conf.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": conf.TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return {"ok": True, "detail": "Notification sent."}
    except requests.RequestException as exc:
        return {"ok": False, "detail": f"Failed to send notification: {exc}"}
