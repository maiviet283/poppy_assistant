"""
telephony.py — Đặt cuộc gọi ĐI qua Twilio ("AI gọi vào số điện thoại thật").

Khách bấm nút -> ``POST /call`` -> ``place_call()`` bảo Twilio quay số. Khi bắt máy,
Twilio mở Media Stream tới ``/ws/twilio``; TwilioVoiceConsumer bắc cầu sang Gemini.
Chỉ dùng ``requests`` (REST) — không cần SDK Twilio. Bí mật chỉ ở cấu hình, không log.
"""

from __future__ import annotations

import re
from xml.sax.saxutils import quoteattr

import requests

from poppy_assistant import conf

_TWILIO_API = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json"


def normalize_phone(raw: str) -> str:
    """Đưa số về E.164 (+<mã quốc gia><số>). Số nội địa '0...' -> mã mặc định."""
    cleaned = re.sub(r"[^\d+]", "", raw or "")
    if not cleaned:
        return ""
    cc = conf.TWILIO_DEFAULT_COUNTRY_CODE or "+61"
    if cleaned.startswith("+"):
        return cleaned
    if cleaned.startswith("00"):
        return "+" + cleaned[2:]
    if cleaned.startswith("0"):
        return cc + cleaned[1:]
    return cc + cleaned


def _stream_url() -> str:
    """Đổi PUBLIC_BASE_URL thành URL WebSocket wss/ws + '/ws/twilio'."""
    base = conf.PUBLIC_BASE_URL
    if base.startswith("https://"):
        base = "wss://" + base[len("https://"):]
    elif base.startswith("http://"):
        base = "ws://" + base[len("http://"):]
    return base.rstrip("/") + "/ws/twilio"


def place_call(to_number: str) -> dict:
    """Bảo Twilio quay số ``to_number`` và bắc audio về ``/ws/twilio``."""
    if not conf.TWILIO_ENABLED:
        return {"ok": False, "error": "Phone calling isn't configured yet. Please set the Twilio number."}
    if not conf.PUBLIC_BASE_URL:
        return {"ok": False, "error": "The server has no public address configured for the call audio."}

    to = normalize_phone(to_number)
    if not to or len(re.sub(r"\D", "", to)) < 8:
        return {"ok": False, "error": "That phone number doesn't look valid."}

    twiml = (
        "<Response><Connect>"
        f"<Stream url={quoteattr(_stream_url())} />"
        "</Connect></Response>"
    )

    try:
        resp = requests.post(
            _TWILIO_API.format(sid=conf.TWILIO_ACCOUNT_SID),
            auth=(conf.TWILIO_ACCOUNT_SID, conf.TWILIO_AUTH_TOKEN),
            data={"To": to, "From": conf.TWILIO_FROM_NUMBER, "Twiml": twiml},
            timeout=15,
        )
    except requests.RequestException as exc:
        print(f"[CALL] Không gọi được Twilio API: {type(exc).__name__}", flush=True)
        return {"ok": False, "error": "Couldn't reach the phone service. Try again."}

    if resp.status_code in (200, 201):
        sid = ""
        try:
            sid = resp.json().get("sid", "")
        except ValueError:
            pass
        print(f"[CALL] Đã đặt cuộc gọi tới {to} (sid={sid}).", flush=True)
        return {"ok": True, "sid": sid}

    detail = ""
    try:
        body = resp.json()
        detail = f"{body.get('code')}: {body.get('message')}"
    except ValueError:
        detail = resp.text[:200]
    print(f"[CALL] Twilio từ chối (HTTP {resp.status_code}) {detail}", flush=True)

    friendly = "Couldn't place the call."
    if "21219" in detail or "21608" in detail or "unverified" in detail.lower():
        friendly = (
            "On a Twilio trial you can only call verified numbers. "
            "Verify this number in the Twilio Console, then try again."
        )
    return {"ok": False, "error": friendly}
