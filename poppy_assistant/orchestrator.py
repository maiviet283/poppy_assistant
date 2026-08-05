from __future__ import annotations

import json

from openai import BadRequestError

from poppy_assistant import conf, rag
from poppy_assistant import tools as tool_registry
from poppy_assistant.gateway import LLMGateway
from poppy_assistant.prompts import build_system_prompt, build_user_context


class Orchestrator:
    """Text-chat orchestrator combining RAG and function calling.

    Conversation history is passed in and out so callers can persist it in the
    Django session between requests. The system prompt is rebuilt from the current
    business profile on every instance so long-lived sessions never keep a stale one.
    """

    def __init__(self, messages: list[dict] | None = None) -> None:
        self.gateway = LLMGateway()
        self.max_rounds = conf.MAX_TOOL_ROUNDS
        self.tool_schemas = tool_registry.openai_schemas(conf.ENABLED_TOOLS)

        system = build_system_prompt()
        if messages:
            self.messages: list[dict] = list(messages)
            if self.messages and self.messages[0].get("role") == "system":
                self.messages[0] = {"role": "system", "content": system}
            else:
                self.messages.insert(0, {"role": "system", "content": system})
        else:
            self.messages = [{"role": "system", "content": system}]

    def _create(self, stream: bool = False):
        return self.gateway.create(self.messages, self.tool_schemas, stream=stream)

    def ask(self, question: str) -> str:
        """Answer a question in a single non-streaming turn (most stable path)."""
        documents = rag.search(question)
        self.messages.append({"role": "user", "content": build_user_context(question, documents)})
        return self._finish_nonstream()

    def _finish_nonstream(self) -> str:
        """Run tool-calling rounds without streaming until the model gives an answer."""
        for _ in range(self.max_rounds):
            response = self._create()
            message = response.choices[0].message

            if not message.tool_calls:
                answer = message.content or ""
                self.messages.append({"role": "assistant", "content": answer})
                return answer

            self.messages.append(message.model_dump(exclude_none=True))
            for tool_call in message.tool_calls:
                name = tool_call.function.name
                args = tool_call.function.arguments
                print(f"   [tool call: {name}({args})]", flush=True)
                result = tool_registry.execute_tool(name, args, source="chat")
                self.messages.append(
                    {"role": "tool", "tool_call_id": tool_call.id, "content": result}
                )

        fallback = "Sorry, I ran into a problem handling that. Please try again."
        self.messages.append({"role": "assistant", "content": fallback})
        return fallback

    def ask_stream(self, question: str):
        """Answer a question as a stream of ``{"delta"}`` / ``{"reset"}`` events.

        Streaming has two known failure modes handled here: a lost thought_signature
        (rejected as a BadRequestError) and a truncated response that swallows a tool
        call. Both fall back to the non-streaming path and emit a ``{"reset"}`` event
        so the frontend discards whatever it rendered for the turn.
        """
        documents = rag.search(question)
        self.messages.append({"role": "user", "content": build_user_context(question, documents)})

        for _ in range(self.max_rounds):
            try:
                stream = self._create(stream=True)
            except BadRequestError as exc:
                if "thought_signature" in str(exc):
                    print("[CHAT] Lost thought_signature; rolling back to non-streaming.", flush=True)
                    while self.messages and self.messages[-1]["role"] != "user":
                        self.messages.pop()
                    yield {"reset": True}
                    yield {"delta": self._finish_nonstream()}
                    return
                raise

            content_parts: list[str] = []
            calls_acc: list[dict] = []
            by_index: dict[int, dict] = {}

            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta is None:
                    continue
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        fn = tc.function
                        if tc.id or (fn and fn.name):
                            slot = {
                                "id": tc.id or "",
                                "name": fn.name if fn and fn.name else "",
                                "arguments": fn.arguments if fn and fn.arguments else "",
                                "tc_extra": dict(getattr(tc, "model_extra", None) or {}),
                                "fn_extra": dict(getattr(fn, "model_extra", None) or {}) if fn else {},
                            }
                            calls_acc.append(slot)
                            if tc.index is not None:
                                by_index[tc.index] = slot
                        else:
                            slot = by_index.get(tc.index) if tc.index is not None else None
                            if slot is None and calls_acc:
                                slot = calls_acc[-1]
                            if slot is not None and fn and fn.arguments:
                                slot["arguments"] += fn.arguments
                            if slot is not None:
                                for k, v in (getattr(tc, "model_extra", None) or {}).items():
                                    slot["tc_extra"].setdefault(k, v)
                                if fn:
                                    for k, v in (getattr(fn, "model_extra", None) or {}).items():
                                        slot["fn_extra"].setdefault(k, v)
                if delta.content:
                    content_parts.append(delta.content)
                    yield {"delta": delta.content}

            answer = "".join(content_parts)

            if not calls_acc:
                # A suspiciously short reply usually means the stream dropped a tool
                # call, so retry the whole turn without streaming.
                if len(answer.strip()) < 12:
                    print(f"[CHAT] Stream returned a stub ({answer.strip()!r}); switching to non-streaming.", flush=True)
                    yield {"reset": True}
                    yield {"delta": self._finish_nonstream()}
                    return
                self.messages.append({"role": "assistant", "content": answer})
                return

            calls = []
            for i, slot in enumerate(calls_acc):
                if not slot["name"]:
                    continue
                args = slot["arguments"] or "{}"
                try:
                    json.loads(args)
                except json.JSONDecodeError:
                    args = "{}"
                call_dict = {
                    "id": slot["id"] or f"call_{i}",
                    "type": "function",
                    "function": {"name": slot["name"], "arguments": args},
                }
                call_dict.update(slot.get("tc_extra", {}))
                call_dict["function"].update(slot.get("fn_extra", {}))
                calls.append(call_dict)
            if not calls:
                self.messages.append({"role": "assistant", "content": answer})
                return

            assistant_msg: dict = {"role": "assistant", "tool_calls": calls}
            if answer:
                assistant_msg["content"] = answer
            self.messages.append(assistant_msg)

            for call in calls:
                name = call["function"]["name"]
                args = call["function"]["arguments"]
                print(f"   [tool call: {name}({args})]", flush=True)
                result = tool_registry.execute_tool(name, args, source="chat")
                self.messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})

        fallback = "Sorry, I ran into a problem handling that. Please try again."
        self.messages.append({"role": "assistant", "content": fallback})
        yield {"delta": fallback}
