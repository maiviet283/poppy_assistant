from __future__ import annotations

import asyncio
import json
import re

from django.http import HttpRequest, HttpResponse, JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from poppy_assistant.orchestrator import Orchestrator

_BUSY_REPLY = "Sorry, I'm a little busy right now — please try again in a moment. 🙏"
_SESSION_KEY = "poppy_chat_messages"
_MAX_HISTORY = 40


def _to_plain_text(text: str) -> str:
    """Strip Markdown so replies render as plain text."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text, flags=re.S)
    text = re.sub(r"__(.+?)__", r"\1", text, flags=re.S)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", text)
    text = re.sub(r"(?m)^(\s*)[*]\s+", r"\1- ", text)
    return text.replace("**", "").replace("__", "")


def _trim_history(messages: list[dict]) -> list[dict]:
    """Keep the system prompt and recent tail, cutting at a 'user' boundary."""
    if len(messages) <= _MAX_HISTORY:
        return messages
    tail = messages[-(_MAX_HISTORY - 1):]
    while tail and tail[0].get("role") != "user":
        tail.pop(0)
    return [messages[0]] + tail


@csrf_exempt
@require_POST
def chat_api(request: HttpRequest):
    """Handle one chat turn, persisting history in the session. ``stream`` -> SSE."""
    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Body must be valid JSON (UTF-8)."}, status=400)

    message = (payload.get("message") or "").strip()
    if not message:
        return JsonResponse({"error": "Missing 'message'."}, status=400)

    history = request.session.get(_SESSION_KEY)
    bot = Orchestrator(messages=history)

    if payload.get("stream"):
        return _chat_stream_response(request, bot, message)

    try:
        reply = bot.ask(message)
    except Exception as exc:
        print(f"[CHAT] Model call failed: {type(exc).__name__}: {exc}", flush=True)
        return JsonResponse({"reply": _BUSY_REPLY}, status=200)

    request.session[_SESSION_KEY] = _trim_history(bot.messages)
    return JsonResponse({"reply": _to_plain_text(reply)})


@csrf_exempt
@require_POST
def call_api(request: HttpRequest):
    """Place an outbound call: the assistant dials a real phone number via Twilio."""
    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "Body must be valid JSON."}, status=400)

    phone = (payload.get("phone") or "").strip()
    if not phone:
        return JsonResponse({"ok": False, "error": "Missing phone number."}, status=400)

    from poppy_assistant import telephony  # lazy: only load when actually calling

    result = telephony.place_call(phone)
    return JsonResponse(result, status=200 if result.get("ok") else 502)


@csrf_exempt
@require_POST
def voice_incoming_api(request: HttpRequest):
    """Answer an inbound Twilio call by connecting it to the /ws/twilio bridge."""
    from poppy_assistant import telephony  # lazy: the phone extras are optional

    params = request.POST.dict()
    signature = request.META.get("HTTP_X_TWILIO_SIGNATURE", "")
    if not telephony.verify_signature(request.get_full_path(), params, signature):
        print("[CALL] Rejected an inbound webhook: bad signature or PUBLIC_BASE_URL "
              "does not match the Voice URL set in Twilio.", flush=True)
        return HttpResponse("Forbidden", status=403)

    print(f"[CALL] Inbound call from {params.get('From', '?')}.", flush=True)
    return HttpResponse(telephony.connect_stream_twiml(), content_type="text/xml")


_SENTINEL = object()


def _as_async_iterator(sync_gen):
    """Wrap a synchronous generator as an async iterator so ASGI streams it live."""

    async def aiter():
        while True:
            item = await asyncio.to_thread(next, sync_gen, _SENTINEL)
            if item is _SENTINEL:
                break
            yield item

    return aiter()


def _chat_stream_response(request: HttpRequest, bot: Orchestrator, message: str):
    """Stream a turn over SSE: ``{delta}``/``{reset}`` events then a final ``{done}``."""
    # Create the session before streaming, since Set-Cookie is fixed once headers go out.
    if not request.session.session_key:
        request.session.create()
    request.session.modified = True

    def events():
        parts: list[str] = []
        try:
            for event in bot.ask_stream(message):
                if event.get("reset"):
                    parts.clear()
                    yield 'data: {"reset": true}\n\n'
                    continue
                chunk = event.get("delta", "")
                if not chunk:
                    continue
                parts.append(chunk)
                yield f'data: {json.dumps({"delta": chunk}, ensure_ascii=False)}\n\n'
        except Exception as exc:
            print(f"[CHAT] Stream error: {type(exc).__name__}: {exc}", flush=True)
            if not parts:
                parts.append(_BUSY_REPLY)
                yield f'data: {json.dumps({"delta": _BUSY_REPLY}, ensure_ascii=False)}\n\n'

        request.session[_SESSION_KEY] = _trim_history(bot.messages)
        request.session.save()

        text = _to_plain_text("".join(parts))
        yield f'data: {json.dumps({"done": True, "text": text}, ensure_ascii=False)}\n\n'

    response = StreamingHttpResponse(_as_async_iterator(events()), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
