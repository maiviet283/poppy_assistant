"""
routing.py — Định tuyến WebSocket cho Channels (ghép vào ProtocolTypeRouter của khách).

Voice là optional [voice]/[phone]: nếu chưa cài ``google-genai`` thì import consumer
sẽ lỗi — ta nuốt và bỏ route voice, để cài CHAT-ONLY vẫn chạy (Trụ #1 extras).
"""

from __future__ import annotations

from django.urls import path

websocket_urlpatterns = []

try:
    from poppy_assistant.consumers import VoiceConsumer

    websocket_urlpatterns.append(path("ws/voice", VoiceConsumer.as_asgi()))
except Exception as exc:  # thiếu google-genai / daphne -> bỏ voice online
    print(f"[POPPY] Voice online tắt (thiếu extras [voice]?): {type(exc).__name__}", flush=True)

try:
    from poppy_assistant.twilio_consumer import TwilioVoiceConsumer

    websocket_urlpatterns.append(path("ws/twilio", TwilioVoiceConsumer.as_asgi()))
except Exception as exc:  # thiếu google-genai -> bỏ gọi qua số điện thoại
    print(f"[POPPY] Voice điện thoại tắt (thiếu extras [phone]?): {type(exc).__name__}", flush=True)
