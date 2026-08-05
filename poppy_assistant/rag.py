"""
rag.py — Tầng truy xuất tài liệu (Retrieval) cho RAG.

Kết nối ChromaDB (đã build bởi ``ingest``) và với mỗi câu hỏi tìm các đoạn tài liệu
liên quan nhất. Embedding chạy NGAY TRÊN MÁY bằng model ONNX nhỏ (all-MiniLM-L6-v2,
384 chiều) đi kèm ChromaDB — MIỄN PHÍ, không cần key, không quota, không thể "chết
key". Lúc ingest và lúc query dùng CÙNG một embedding function nên vector khớp nhau.
"""

from __future__ import annotations

import chromadb
from chromadb.utils import embedding_functions

from poppy_assistant import conf

# Embedding cục bộ: không phụ thuộc Gemini/OpenAI, không tốn tiền, không quota.
_embedding_fn = embedding_functions.DefaultEmbeddingFunction()


def get_collection(create_if_missing: bool = False):
    """Lấy (hoặc tạo) collection trong ChromaDB lưu ở ổ đĩa."""
    client = chromadb.PersistentClient(path=str(conf.CHROMA_DB_DIR))
    if create_if_missing:
        return client.get_or_create_collection(
            name=conf.CHROMA_COLLECTION,
            embedding_function=_embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
    return client.get_collection(name=conf.CHROMA_COLLECTION, embedding_function=_embedding_fn)


def search(question: str, top_k: int | None = None) -> str:
    """Tìm các đoạn tài liệu liên quan nhất; trả chuỗi đã ghép (kèm tiêu đề).

    Chưa build index hoặc không có kết quả -> trả chuỗi rỗng.
    """
    top_k = top_k or conf.RAG_TOP_K
    try:
        collection = get_collection()
    except Exception:
        return ""

    results = collection.query(query_texts=[question], n_results=top_k)
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    if not documents:
        return ""

    blocks = []
    for doc, meta in zip(documents, metadatas):
        title = (meta or {}).get("title", "Tài liệu")
        blocks.append(f"### {title}\n{doc}")
    return "\n\n".join(blocks)
