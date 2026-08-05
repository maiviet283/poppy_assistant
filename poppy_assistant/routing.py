from __future__ import annotations

from django.urls import path

# Voice is optional. If google-genai / daphne aren't installed, importing the
# consumers fails; swallow it and drop the route so chat-only installs still work.
websocket_urlpatterns = []

try:
    from poppy_assistant.consumers import VoiceConsumer

    websocket_urlpatterns.append(path("ws/voice", VoiceConsumer.as_asgi()))
except Exception as exc:
    print(f"[POPPY] Online voice disabled (missing [voice] extras?): {type(exc).__name__}", flush=True)

try:
    from poppy_assistant.twilio_consumer import TwilioVoiceConsumer

    websocket_urlpatterns.append(path("ws/twilio", TwilioVoiceConsumer.as_asgi()))
except Exception as exc:
    print(f"[POPPY] Phone voice disabled (missing [phone] extras?): {type(exc).__name__}", flush=True)
