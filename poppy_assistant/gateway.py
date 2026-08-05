"""
gateway.py — LLM Gateway: mọi lời gọi model chat đi qua đây (AI_PLATFORM §5.3).

Gói một chỗ: tạo client OpenAI trỏ về Gemile (API tương thích OpenAI), retry lỗi
tạm (503 quá tải / 429), và FAILOVER sang model dự phòng. Bài học demo (bẫy #5):
spike 503 bám theo TỪNG model — đổi model là thoát ngay, không chỉ retry.
"""

from __future__ import annotations

import time

from openai import InternalServerError, OpenAI, RateLimitError

from poppy_assistant import conf

# Thử lại 1 lần (2s) trên model chính rồi chuyển model dự phòng (pool tải riêng).
_EXTRA_RETRIES = 1
_RETRY_DELAYS = (2,)


class LLMGateway:
    def __init__(self) -> None:
        self.client = OpenAI(
            api_key=conf.GEMINI_API_KEY,
            base_url=conf.GEMINI_BASE_URL,
            max_retries=3,
        )

    def create(self, messages: list[dict], tools: list[dict], stream: bool = False):
        """Gọi chat completion; lỗi tạm thì retry rồi failover model. Ném lỗi cuối nếu hết cách."""
        models = [conf.CHAT_MODEL]
        if conf.CHAT_MODEL_FALLBACK and conf.CHAT_MODEL_FALLBACK != conf.CHAT_MODEL:
            models.append(conf.CHAT_MODEL_FALLBACK)

        last_exc: Exception | None = None
        for m_i, model in enumerate(models):
            for attempt in range(_EXTRA_RETRIES + 1):
                try:
                    return self.client.chat.completions.create(
                        model=model,
                        messages=messages,
                        tools=tools,
                        tool_choice="auto",
                        temperature=0.3,
                        stream=stream,
                    )
                except (InternalServerError, RateLimitError) as exc:
                    last_exc = exc
                    if attempt >= _EXTRA_RETRIES:
                        break
                    wait = _RETRY_DELAYS[attempt]
                    print(f"[CHAT] {model} quá tải ({type(exc).__name__}), thử lại sau {wait}s...", flush=True)
                    time.sleep(wait)
            if m_i + 1 < len(models):
                print(f"[CHAT] {model} vẫn quá tải — chuyển model dự phòng {models[m_i + 1]}.", flush=True)
        raise last_exc
