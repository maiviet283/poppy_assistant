"""
knowledge_tools.py — Đăng ký tool tra cứu tri thức (RAG) vào registry (tag "faq").

Dùng cho voice (phiên Live cần RAG dưới dạng tool). Ở chat, RAG được ghép sẵn vào
ngữ cảnh mỗi lượt (xem orchestrator), nên tool này chủ yếu phục vụ voice — nhưng
đăng ký chung một chỗ để chat bật kèm cũng được.
"""

from __future__ import annotations

from poppy_assistant import rag
from poppy_assistant.tools.registry import register


def _search_knowledge(query: str = "", **_) -> dict:
    docs = rag.search(query)
    return {"info": docs or "No relevant information found."}


register(
    name="search_knowledge",
    description=(
        "Look up the business's information (opening hours, location, policies, product/"
        "shipping info) to answer the customer. Call this before answering factual questions "
        "about the business. Do not invent details."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to look up (a question or keywords)."}
        },
        "required": ["query"],
    },
    handler=_search_knowledge,
    tags=["faq"],
)
