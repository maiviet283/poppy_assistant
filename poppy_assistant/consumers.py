"""
consumers.py — WebSocket "gọi điện" online (Channels), cầu nối Trình duyệt ⇄ Gemini Live.

Trình duyệt gửi audio mic (PCM 16kHz); Gemini trả audio (PCM 24kHz) + tool + transcript.
Tool dùng chung registry với chat qua ``run_tool``. Key Gemini chỉ ở server.

Bài học voice (bẫy #10): phiên Gemini chết giữa chừng -> tự đóng WebSocket (đừng bỏ),
nếu không sẽ spam lỗi và trình duyệt treo cuộc gọi im lặng.
"""

from __future__ import annotations

import asyncio
import json
import re

from channels.generic.websocket import AsyncWebsocketConsumer
from google import genai
from google.genai import types

from poppy_assistant import conf
from poppy_assistant.voice_config import build_live_config, run_tool


def _log(*args) -> None:
    print("[VOICE]", *args, flush=True)


_CTRL_TOKEN_RE = re.compile(r"<ctrl\d+>")


class VoiceConsumer(AsyncWebsocketConsumer):
    """Một phiên gọi online = một WebSocket = một phiên Gemini Live riêng."""

    async def connect(self) -> None:
        await self.accept()
        if not conf.GEMINI_API_KEY:
            _log("Thiếu GEMINI_API_KEY — không mở được phiên Live.")
            await self.close()
            return

        _log("Trình duyệt đã kết nối. Đang mở phiên Gemini Live...")
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

        _log(f"Phiên Live đã mở (model={conf.VOICE_MODEL}). Sẵn sàng nghe.")
        self._recv_task = asyncio.create_task(self._gemini_to_browser())

    async def receive(self, text_data=None, bytes_data=None) -> None:
        session = getattr(self, "session", None)
        if session is None:
            return
        if bytes_data is not None:
            try:
                await session.send_realtime_input(
                    audio=types.Blob(data=bytes_data, mime_type="audio/pcm;rate=16000")
                )
            except Exception as exc:
                _log(f"❌ Phiên Gemini đã đóng, kết thúc cuộc gọi: {type(exc).__name__}: {exc}")
                self.session = None
                await self.close()
                return
            self._mic_chunks = getattr(self, "_mic_chunks", 0) + 1
            self._mic_bytes = getattr(self, "_mic_bytes", 0) + len(bytes_data)
            if self._mic_chunks % 20 == 0:
                _log(f"🎤 [MIC->Gemini] {self._mic_chunks} chunk (~{self._mic_bytes // 1024} KB)")
        elif text_data == "__end__":
            _log("Trình duyệt báo kết thúc cuộc gọi.")
            await self.close()

    async def _gemini_to_browser(self) -> None:
        turn = 0
        try:
            while True:
                turn += 1
                _log(f"───── Lượt #{turn}: đang chờ Gemini ─────")
                audio_bytes = 0
                async for resp in self.session.receive():
                    if resp.data:
                        audio_bytes += len(resp.data)
                        await self.send(bytes_data=resp.data)

                    if resp.tool_call:
                        responses = []
                        for fc in resp.tool_call.function_calls:
                            args = dict(fc.args or {})
                            _log(f"🔧 [TOOL] Gemini gọi: {fc.name}({args})")
                            await self._send_json({"type": "tool", "name": fc.name, "args": args})
                            result = await asyncio.to_thread(run_tool, fc.name, args)
                            responses.append(
                                types.FunctionResponse(id=fc.id, name=fc.name, response=result)
                            )
                        await self.session.send_tool_response(function_responses=responses)

                    sc = resp.server_content
                    if sc:
                        if sc.interrupted:
                            _log("⏸️  Bị ngắt (khách chen ngang).")
                            await self._send_json({"type": "interrupt"})
                        if sc.input_transcription and sc.input_transcription.text:
                            t = sc.input_transcription.text
                            _log(f"🧑 [BẠN NÓI] {t!r}")
                            await self._send_json({"type": "user_text", "text": t})
                        if sc.output_transcription and sc.output_transcription.text:
                            t = sc.output_transcription.text
                            if _CTRL_TOKEN_RE.sub("", t).strip() or t.strip() == "":
                                _log(f"🤖 [BOT NÓI] {t!r}")
                                await self._send_json({"type": "bot_text", "text": t})

                _log(f"✅ Lượt #{turn} xong (~{audio_bytes // 1024} KB audio).")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _log(f"❌ Lỗi luồng nghe Gemini, kết thúc cuộc gọi: {type(exc).__name__}: {exc}")
            self.session = None
            try:
                await self.close()
            except Exception:
                pass

    async def _send_json(self, data: dict) -> None:
        await self.send(text_data=json.dumps(data, ensure_ascii=False))

    async def disconnect(self, code) -> None:
        _log(f"Đóng phiên (code={code}). Dọn dẹp...")
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
