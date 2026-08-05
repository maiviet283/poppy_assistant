"""
twilio_consumer.py — Cầu nối Twilio Media Stream ⇄ Gemini Live (gọi vào SỐ ĐIỆN THOẠI).

Song song với ``consumers.py`` (gọi online): "bộ não" giống hệt (build_live_config +
run_tool + registry) — chỉ khác "đường ống audio":
  - Twilio gửi audio JSON (base64 µ-law 8kHz); Gemini cần PCM 16kHz vào, PCM 24kHz ra.
  => chuyển mã hai chiều bằng ``audioop`` (có sẵn trong Python 3.12).
Điện thoại thì AI phải CHÀO TRƯỚC (người ta áp tai chờ nghe).
"""

from __future__ import annotations

import asyncio
import audioop
import base64
import json
import re

from channels.generic.websocket import AsyncWebsocketConsumer
from google import genai
from google.genai import types

from poppy_assistant import conf
from poppy_assistant.voice_config import build_live_config, run_tool

_TW_RATE = 8000
_GEMINI_IN_RATE = 16000
_GEMINI_OUT_RATE = 24000
_SAMPLE_WIDTH = 2
_FRAME_BYTES = 160

_CTRL_TOKEN_RE = re.compile(r"<ctrl\d+>")


def _log(*args) -> None:
    print("[PHONE]", *args, flush=True)


class TwilioVoiceConsumer(AsyncWebsocketConsumer):
    """Một cuộc gọi điện thoại = một Media Stream Twilio = một phiên Gemini Live."""

    async def connect(self) -> None:
        await self.accept()
        if not conf.GEMINI_API_KEY:
            _log("Thiếu GEMINI_API_KEY — không mở được phiên Live.")
            await self.close()
            return

        self.stream_sid = ""
        self._greeted = False
        self._in_state = None
        self._out_state = None
        self._out_buf = b""

        _log("Twilio đã kết nối. Đang mở phiên Gemini Live...")
        self._client = genai.Client(api_key=conf.GEMINI_API_KEY)
        self._session_cm = self._client.aio.live.connect(
            model=conf.VOICE_MODEL, config=build_live_config()
        )
        try:
            self.session = await self._session_cm.__aenter__()
        except Exception as exc:
            _log(f"❌ Không mở được phiên Live: {type(exc).__name__}: {exc}")
            await self.close()
            return

        _log(f"Phiên Live đã mở (model={conf.VOICE_MODEL}).")
        self._recv_task = asyncio.create_task(self._gemini_to_twilio())

    async def receive(self, text_data=None, bytes_data=None) -> None:
        if text_data is None:
            return
        try:
            msg = json.loads(text_data)
        except (json.JSONDecodeError, TypeError):
            return

        event = msg.get("event")
        if event == "media":
            await self._forward_media(msg)
        elif event == "start":
            self.stream_sid = msg.get("start", {}).get("streamSid") or msg.get("streamSid", "")
            _log(f"▶️  Cuộc gọi bắt đầu (streamSid={self.stream_sid}).")
            await self._greet_once()
        elif event == "stop":
            _log("⏹️  Twilio báo kết thúc cuộc gọi.")
            await self.close()

    async def _forward_media(self, msg: dict) -> None:
        session = getattr(self, "session", None)
        if session is None:
            return
        payload = msg.get("media", {}).get("payload")
        if not payload:
            return
        ulaw = base64.b64decode(payload)
        pcm8 = audioop.ulaw2lin(ulaw, _SAMPLE_WIDTH)
        pcm16, self._in_state = audioop.ratecv(
            pcm8, _SAMPLE_WIDTH, 1, _TW_RATE, _GEMINI_IN_RATE, self._in_state
        )
        try:
            await session.send_realtime_input(
                audio=types.Blob(data=pcm16, mime_type="audio/pcm;rate=16000")
            )
        except Exception as exc:
            _log(f"❌ Phiên Gemini đã đóng, kết thúc cuộc gọi: {type(exc).__name__}: {exc}")
            self.session = None
            await self.close()

    async def _greet_once(self) -> None:
        if self._greeted:
            return
        self._greeted = True
        session = getattr(self, "session", None)
        if session is None:
            return
        name = conf.ASSISTANT_NAME or "Poppy"
        business = conf.BUSINESS_NAME or "our business"
        try:
            await session.send_client_content(
                turns=types.Content(
                    role="user",
                    parts=[types.Part(text=(
                        f"(The phone call just connected.) Greet the caller warmly in one "
                        f"short sentence as {name} from {business}, and ask how you can help."
                    ))],
                ),
                turn_complete=True,
            )
        except Exception as exc:
            _log(f"⚠️  Không gửi được lời chào mở đầu: {type(exc).__name__}: {exc}")

    async def _gemini_to_twilio(self) -> None:
        turn = 0
        try:
            while True:
                turn += 1
                async for resp in self.session.receive():
                    if resp.data:
                        await self._send_audio(resp.data)

                    if resp.tool_call:
                        responses = []
                        for fc in resp.tool_call.function_calls:
                            args = dict(fc.args or {})
                            _log(f"🔧 [TOOL] {fc.name}({args})")
                            result = await asyncio.to_thread(run_tool, fc.name, args)
                            responses.append(
                                types.FunctionResponse(id=fc.id, name=fc.name, response=result)
                            )
                        await self.session.send_tool_response(function_responses=responses)

                    sc = resp.server_content
                    if sc:
                        if sc.interrupted:
                            _log("⏸️  Bị ngắt (khách chen ngang).")
                            await self._clear_twilio()
                        if sc.output_transcription and sc.output_transcription.text:
                            t = sc.output_transcription.text
                            if _CTRL_TOKEN_RE.sub("", t).strip():
                                _log(f"🤖 [BOT NÓI] {t!r}")
                        if sc.input_transcription and sc.input_transcription.text:
                            _log(f"🧑 [KHÁCH NÓI] {sc.input_transcription.text!r}")

                _log(f"✅ Lượt #{turn} xong.")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _log(f"❌ Lỗi luồng nghe Gemini, kết thúc cuộc gọi: {type(exc).__name__}: {exc}")
            self.session = None
            try:
                await self.close()
            except Exception:
                pass

    async def _send_audio(self, pcm24: bytes) -> None:
        if not self.stream_sid:
            return
        pcm8, self._out_state = audioop.ratecv(
            pcm24, _SAMPLE_WIDTH, 1, _GEMINI_OUT_RATE, _TW_RATE, self._out_state
        )
        self._out_buf += audioop.lin2ulaw(pcm8, _SAMPLE_WIDTH)
        while len(self._out_buf) >= _FRAME_BYTES:
            frame, self._out_buf = self._out_buf[:_FRAME_BYTES], self._out_buf[_FRAME_BYTES:]
            await self.send(text_data=json.dumps({
                "event": "media",
                "streamSid": self.stream_sid,
                "media": {"payload": base64.b64encode(frame).decode("ascii")},
            }))

    async def _clear_twilio(self) -> None:
        self._out_buf = b""
        if not self.stream_sid:
            return
        await self.send(text_data=json.dumps({"event": "clear", "streamSid": self.stream_sid}))

    async def disconnect(self, code) -> None:
        _log(f"Đóng cuộc gọi (code={code}). Dọn dẹp...")
        task = getattr(self, "_recv_task", None)
        if task is not None:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        cm = getattr(self, "_session_cm", None)
        if cm is not None:
            try:
                await cm.__aexit__(None, None, None)
            except Exception:
                pass
