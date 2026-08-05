"""
views.py — API chat text ``POST /chat`` (JSON hoặc SSE) + ``POST /call`` (gọi ĐI).

Lịch sử hội thoại lưu trong session Django (key riêng ``poppy_chat_messages`` — Trụ
#2 namespace) nên mỗi khách có mạch riêng mà server không giữ trạng thái trong RAM.
Giữ nguyên các bẫy streaming đã đổ máu (bẫy #1/#2/#3).
"""

from __future__ import annotations

import asyncio
import json
import re

from django.http import HttpRequest, JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from poppy_assistant.orchestrator import Orchestrator

_BUSY_REPLY = "Sorry, I'm a little busy right now — please try again in a moment. 🙏"
_SESSION_KEY = "poppy_chat_messages"
_MAX_HISTORY = 40


def _to_plain_text(text: str) -> str:
    """Bỏ định dạng Markdown để câu trả lời là TEXT thuần (khách không muốn thấy ** ##)."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text, flags=re.S)
    text = re.sub(r"__(.+?)__", r"\1", text, flags=re.S)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", text)
    text = re.sub(r"(?m)^(\s*)[*]\s+", r"\1- ", text)
    return text.replace("**", "").replace("__", "")


def _trim_history(messages: list[dict]) -> list[dict]:
    """Giữ system prompt + đuôi gần đây; cắt tại ranh giới 'user' (không tách cặp tool)."""
    if len(messages) <= _MAX_HISTORY:
        return messages
    tail = messages[-(_MAX_HISTORY - 1):]
    while tail and tail[0].get("role") != "user":
        tail.pop(0)
    return [messages[0]] + tail


@csrf_exempt
@require_POST
def chat_api(request: HttpRequest):
    """Một lượt hỏi/đáp; giữ lịch sử theo session. ``"stream": true`` -> SSE."""
    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Body phải là JSON hợp lệ (UTF-8)."}, status=400)

    message = (payload.get("message") or "").strip()
    if not message:
        return JsonResponse({"error": "Thiếu nội dung 'message'."}, status=400)

    history = request.session.get(_SESSION_KEY)
    bot = Orchestrator(messages=history)

    if payload.get("stream"):
        return _chat_stream_response(request, bot, message)

    try:
        reply = bot.ask(message)
    except Exception as exc:
        print(f"[CHAT] Lỗi khi gọi model: {type(exc).__name__}: {exc}", flush=True)
        return JsonResponse({"reply": _BUSY_REPLY}, status=200)

    request.session[_SESSION_KEY] = _trim_history(bot.messages)
    return JsonResponse({"reply": _to_plain_text(reply)})


@csrf_exempt
@require_POST
def call_api(request: HttpRequest):
    """Đặt cuộc gọi ĐI: AI gọi vào số điện thoại thật (Twilio, optional [phone])."""
    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "Body phải là JSON hợp lệ."}, status=400)

    phone = (payload.get("phone") or "").strip()
    if not phone:
        return JsonResponse({"ok": False, "error": "Missing phone number."}, status=400)

    from poppy_assistant import telephony  # lazy: chỉ nạp khi thực sự gọi

    result = telephony.place_call(phone)
    return JsonResponse(result, status=200 if result.get("ok") else 502)


_SENTINEL = object()


def _as_async_iterator(sync_gen):
    """Bọc generator đồng bộ thành async iterator (ASGI mới stream thật — bẫy #2)."""

    async def aiter():
        while True:
            item = await asyncio.to_thread(next, sync_gen, _SENTINEL)
            if item is _SENTINEL:
                break
            yield item

    return aiter()


def _chat_stream_response(request: HttpRequest, bot: Orchestrator, message: str):
    """SSE: nhiều event ``{"delta"}``/``{"reset"}`` rồi chốt ``{"done","text"}``."""
    # Tạo session TRƯỚC khi stream (Set-Cookie chốt lúc gửi headers — bẫy #3).
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
            print(f"[CHAT] Lỗi stream: {type(exc).__name__}: {exc}", flush=True)
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
