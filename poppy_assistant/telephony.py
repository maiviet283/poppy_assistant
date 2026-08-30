from __future__ import annotations

import base64
import hashlib
import hmac
import re
from xml.sax.saxutils import quoteattr

import requests

from poppy_assistant import conf

_TWILIO_API = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json"


def normalize_phone(raw: str) -> str:
    """Normalise a number to E.164, applying the default country code to local ones."""
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
    """Turn PUBLIC_BASE_URL into the wss/ws URL for the Twilio media stream."""
    base = conf.PUBLIC_BASE_URL
    if base.startswith("https://"):
        base = "wss://" + base[len("https://"):]
    elif base.startswith("http://"):
        base = "ws://" + base[len("http://"):]
    return base.rstrip("/") + "/ws/twilio"


def connect_stream_twiml() -> str:
    """TwiML that hands the call audio to the /ws/twilio bridge."""
    return (
        "<Response><Connect>"
        f"<Stream url={quoteattr(_stream_url())} />"
        "</Connect></Response>"
    )


def verify_signature(full_path: str, params: dict, signature: str) -> bool:
    """Validate Twilio's X-Twilio-Signature for a webhook hit.

    The signed URL is rebuilt from PUBLIC_BASE_URL rather than the request headers,
    because behind a tunnel or proxy Django sees http/an internal host and the digest
    would never match what Twilio signed.
    """
    token = conf.TWILIO_AUTH_TOKEN
    base = conf.PUBLIC_BASE_URL
    if not token or not base or not signature:
        return False
    payload = base.rstrip("/") + full_path + "".join(k + params[k] for k in sorted(params))
    digest = hmac.new(token.encode(), payload.encode("utf-8"), hashlib.sha1).digest()
    return hmac.compare_digest(base64.b64encode(digest).decode("ascii"), signature)


def place_call(to_number: str) -> dict:
    """Ask Twilio to dial ``to_number`` and stream the call audio to /ws/twilio."""
    if not conf.TWILIO_ENABLED:
        return {"ok": False, "error": "Phone calling isn't configured yet. Please set the Twilio number."}
    if not conf.PUBLIC_BASE_URL:
        return {"ok": False, "error": "The server has no public address configured for the call audio."}

    to = normalize_phone(to_number)
    if not to or len(re.sub(r"\D", "", to)) < 8:
        return {"ok": False, "error": "That phone number doesn't look valid."}

    twiml = connect_stream_twiml()

    try:
        resp = requests.post(
            _TWILIO_API.format(sid=conf.TWILIO_ACCOUNT_SID),
            auth=(conf.TWILIO_ACCOUNT_SID, conf.TWILIO_AUTH_TOKEN),
            data={"To": to, "From": conf.TWILIO_FROM_NUMBER, "Twiml": twiml},
            timeout=15,
        )
    except requests.RequestException as exc:
        print(f"[CALL] Twilio API unreachable: {type(exc).__name__}", flush=True)
        return {"ok": False, "error": "Couldn't reach the phone service. Try again."}

    if resp.status_code in (200, 201):
        sid = ""
        try:
            sid = resp.json().get("sid", "")
        except ValueError:
            pass
        print(f"[CALL] Call placed to {to} (sid={sid}).", flush=True)
        return {"ok": True, "sid": sid}

    detail = ""
    try:
        body = resp.json()
        detail = f"{body.get('code')}: {body.get('message')}"
    except ValueError:
        detail = resp.text[:200]
    print(f"[CALL] Twilio rejected the call (HTTP {resp.status_code}) {detail}", flush=True)

    friendly = "Couldn't place the call."
    if "21219" in detail or "21608" in detail or "unverified" in detail.lower():
        friendly = (
            "On a Twilio trial you can only call verified numbers. "
            "Verify this number in the Twilio Console, then try again."
        )
    return {"ok": False, "error": friendly}
