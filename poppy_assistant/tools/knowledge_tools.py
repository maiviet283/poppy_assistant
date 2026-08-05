from __future__ import annotations

# Retrieval exposed as a tool, mainly for voice sessions. Chat splices RAG into
# each turn's context directly (see orchestrator), but registering it here lets
# chat opt in as well.

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
