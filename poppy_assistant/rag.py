from __future__ import annotations

import chromadb
from chromadb.utils import embedding_functions

from poppy_assistant import conf

# Local embedding model bundled with ChromaDB; no API key or quota required, and it
# must match the function used at ingest time so query vectors align.
_embedding_fn = embedding_functions.DefaultEmbeddingFunction()


def get_collection(create_if_missing: bool = False):
    """Return the on-disk ChromaDB collection, optionally creating it."""
    client = chromadb.PersistentClient(path=str(conf.CHROMA_DB_DIR))
    if create_if_missing:
        return client.get_or_create_collection(
            name=conf.CHROMA_COLLECTION,
            embedding_function=_embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
    return client.get_collection(name=conf.CHROMA_COLLECTION, embedding_function=_embedding_fn)


def search(question: str, top_k: int | None = None) -> str:
    """Return the most relevant document chunks joined into a single string.

    Returns an empty string when the index is missing or has no matches.
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
        title = (meta or {}).get("title", "Document")
        blocks.append(f"### {title}\n{doc}")
    return "\n\n".join(blocks)
