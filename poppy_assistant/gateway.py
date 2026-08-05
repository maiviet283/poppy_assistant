from __future__ import annotations

import time

from openai import InternalServerError, OpenAI, RateLimitError

from poppy_assistant import conf

_EXTRA_RETRIES = 1
_RETRY_DELAYS = (2,)


class LLMGateway:
    """Single entry point for chat model calls, with retry and model failover.

    Transient overload (503/429) tends to follow an individual model, so after a
    short retry the gateway fails over to the fallback model rather than retrying
    the same one.
    """

    def __init__(self) -> None:
        self.client = OpenAI(
            api_key=conf.GEMINI_API_KEY,
            base_url=conf.GEMINI_BASE_URL,
            max_retries=3,
        )

    def create(self, messages: list[dict], tools: list[dict], stream: bool = False):
        """Run a chat completion, retrying then failing over on transient errors."""
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
                    print(f"[CHAT] {model} overloaded ({type(exc).__name__}), retrying in {wait}s...", flush=True)
                    time.sleep(wait)
            if m_i + 1 < len(models):
                print(f"[CHAT] {model} still overloaded, failing over to {models[m_i + 1]}.", flush=True)
        raise last_exc
