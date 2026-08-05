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
    """Browser <-> Gemini Live audio bridge for an online voice call.

    The browser sends mic audio (PCM 16kHz); Gemini returns audio (PCM 24kHz) plus
    tool calls and transcripts. Tools share the chat registry via ``run_tool``, and
    the API key stays server-side. If the Gemini session dies mid-call the socket is
    closed rather than left spamming errors on a silently hung call.
    """

    async def connect(self) -> None:
        await self.accept()
        if not conf.GEMINI_API_KEY:
            _log("GEMINI_API_KEY missing; cannot open a Live session.")
            await self.close()
            return

        _log("Browser connected. Opening Gemini Live session...")
        self._client = genai.Client(api_key=conf.GEMINI_API_KEY)
        self._session_cm = self._client.aio.live.connect(
            model=conf.VOICE_MODEL, config=build_live_config()
        )
        try:
            self.session = await self._session_cm.__aenter__()
        except Exception as exc:
            _log(f"Failed to open Live session: {type(exc).__name__}: {exc}")
            await self.close()
            return

        _log(f"Live session open (model={conf.VOICE_MODEL}). Listening.")
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
                _log(f"Gemini session closed, ending call: {type(exc).__name__}: {exc}")
                self.session = None
                await self.close()
                return
            self._mic_chunks = getattr(self, "_mic_chunks", 0) + 1
            self._mic_bytes = getattr(self, "_mic_bytes", 0) + len(bytes_data)
            if self._mic_chunks % 20 == 0:
                _log(f"[mic->Gemini] {self._mic_chunks} chunks (~{self._mic_bytes // 1024} KB)")
        elif text_data == "__end__":
            _log("Browser signalled end of call.")
            await self.close()

    async def _gemini_to_browser(self) -> None:
        """Forward Gemini audio, tool calls and transcripts to the browser."""
        turn = 0
        try:
            while True:
                turn += 1
                _log(f"----- Turn #{turn}: waiting for Gemini -----")
                audio_bytes = 0
                async for resp in self.session.receive():
                    if resp.data:
                        audio_bytes += len(resp.data)
                        await self.send(bytes_data=resp.data)

                    if resp.tool_call:
                        responses = []
                        for fc in resp.tool_call.function_calls:
                            args = dict(fc.args or {})
                            _log(f"[tool] Gemini called: {fc.name}({args})")
                            await self._send_json({"type": "tool", "name": fc.name, "args": args})
                            result = await asyncio.to_thread(run_tool, fc.name, args)
                            responses.append(
                                types.FunctionResponse(id=fc.id, name=fc.name, response=result)
                            )
                        await self.session.send_tool_response(function_responses=responses)

                    sc = resp.server_content
                    if sc:
                        if sc.interrupted:
                            _log("Interrupted (customer spoke over).")
                            await self._send_json({"type": "interrupt"})
                        if sc.input_transcription and sc.input_transcription.text:
                            t = sc.input_transcription.text
                            _log(f"[user] {t!r}")
                            await self._send_json({"type": "user_text", "text": t})
                        if sc.output_transcription and sc.output_transcription.text:
                            t = sc.output_transcription.text
                            if _CTRL_TOKEN_RE.sub("", t).strip() or t.strip() == "":
                                _log(f"[bot] {t!r}")
                                await self._send_json({"type": "bot_text", "text": t})

                _log(f"Turn #{turn} done (~{audio_bytes // 1024} KB audio).")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _log(f"Gemini receive loop failed, ending call: {type(exc).__name__}: {exc}")
            self.session = None
            try:
                await self.close()
            except Exception:
                pass

    async def _send_json(self, data: dict) -> None:
        await self.send(text_data=json.dumps(data, ensure_ascii=False))

    async def disconnect(self, code) -> None:
        _log(f"Closing session (code={code}). Cleaning up...")
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
