from __future__ import annotations

import re

import frontmatter
from django.core.management.base import BaseCommand

from poppy_assistant import conf
from poppy_assistant.rag import get_collection


def chunk_markdown(text: str) -> list[str]:
    """Split markdown on level-2 headings ("## ") for more precise retrieval."""
    parts = re.split(r"(?=^##\s)", text, flags=re.MULTILINE)
    return [p.strip() for p in parts if p.strip()]


class Command(BaseCommand):
    help = "Load docs/*.md into ChromaDB for retrieval."

    def handle(self, *args, **options) -> None:
        """Rebuild the vector index from every markdown file in DOCS_DIR."""
        self.stdout.write(conf.summary())
        self.stdout.write("\n[INGEST] Loading documents...")

        md_files = sorted(conf.DOCS_DIR.glob("*.md"))
        if not md_files:
            self.stdout.write(f"[INGEST] No .md files found in {conf.DOCS_DIR}")
            return

        collection = get_collection(create_if_missing=True)

        # Clear existing entries so the index is rebuilt from scratch.
        existing = collection.get()
        if existing["ids"]:
            collection.delete(ids=existing["ids"])

        ids: list[str] = []
        docs: list[str] = []
        metas: list[dict] = []
        for path in md_files:
            post = frontmatter.load(path)
            title = post.get("title", path.stem)
            chunks = chunk_markdown(post.content)
            for i, chunk in enumerate(chunks):
                ids.append(f"{path.stem}-{i}")
                docs.append(chunk)
                metas.append({"title": str(title), "source": path.name, "chunk": i})
            self.stdout.write(f"  - {path.name}: {len(chunks)} chunks")

        if ids:
            collection.add(ids=ids, documents=docs, metadatas=metas)

        self.stdout.write(
            self.style.SUCCESS(f"\n[INGEST] Done. Loaded {len(ids)} chunks from {len(md_files)} files.")
        )
        self.stdout.write(f"[INGEST] Vector DB stored at: {conf.CHROMA_DB_DIR}")
