from __future__ import annotations

import base64
import hashlib
import hmac

from django.test import SimpleTestCase, override_settings

from poppy_assistant import telephony

_POPPY = {
    "BUSINESS_NAME": "Petal & Polish",
    "TWILIO_AUTH_TOKEN": "test-token",
    "PUBLIC_BASE_URL": "https://poppy.example.com",
}


def _sign(url: str, params: dict, token: str = "test-token") -> str:
    """Build the signature Twilio would send for this request."""
    payload = url + "".join(k + params[k] for k in sorted(params))
    digest = hmac.new(token.encode(), payload.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("ascii")


@override_settings(POPPY=_POPPY)
class SignatureTests(SimpleTestCase):
    """Twilio webhook signature validation."""

    path = "/api/voice/incoming"
    params = {"CallSid": "CA123", "From": "+61412345678"}

    def test_accepts_a_valid_signature(self):
        sig = _sign("https://poppy.example.com" + self.path, self.params)
        self.assertTrue(telephony.verify_signature(self.path, self.params, sig))

    def test_rejects_a_tampered_body(self):
        sig = _sign("https://poppy.example.com" + self.path, self.params)
        forged = dict(self.params, From="+61400000000")
        self.assertFalse(telephony.verify_signature(self.path, forged, sig))

    def test_rejects_when_signature_is_missing(self):
        self.assertFalse(telephony.verify_signature(self.path, self.params, ""))


class WebhookViewTests(SimpleTestCase):
    """The inbound-call endpoint."""

    @override_settings(POPPY=_POPPY)
    def test_returns_stream_twiml_for_a_signed_request(self):
        params = {"CallSid": "CA123", "From": "+61412345678"}
        sig = _sign("https://poppy.example.com/api/voice/incoming", params)
        resp = self.client.post("/api/voice/incoming", params, HTTP_X_TWILIO_SIGNATURE=sig)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/xml")
        self.assertIn("wss://poppy.example.com/ws/twilio", resp.content.decode())

    @override_settings(POPPY=_POPPY)
    def test_rejects_an_unsigned_request(self):
        resp = self.client.post("/api/voice/incoming", {"CallSid": "CA123"})
        self.assertEqual(resp.status_code, 403)


@override_settings(POPPY={"BUSINESS_NAME": "Petal & Polish", "TWILIO_DEFAULT_COUNTRY_CODE": "+61"})
class NormalizePhoneTests(SimpleTestCase):
    """Australian numbers reach E.164."""

    def test_local_mobile(self):
        self.assertEqual(telephony.normalize_phone("0412 345 678"), "+61412345678")

    def test_local_landline(self):
        self.assertEqual(telephony.normalize_phone("(02) 9999 1234"), "+61299991234")

    def test_already_international(self):
        self.assertEqual(telephony.normalize_phone("+61 412 345 678"), "+61412345678")
