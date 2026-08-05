"""
Management command: nạp tài liệu docs/*.md vào ChromaDB cho RAG.

    python manage.py ingest

Đọc mọi file .md trong POPPY['DOCS_DIR'], cắt chunk theo tiêu đề "## ", rồi nạp vào
ChromaDB. Embedding chạy LOCAL (ONNX) nên KHÔNG có quota — nạp một lần, không cần
nghỉ giữa lô như bản demo cũ. Chạy lại mỗi khi thêm/sửa tài liệu.
"""

from __future__ import annotations

import re

import frontmatter
from django.core.management.base import BaseCommand

from poppy_assistant import conf
from poppy_assistant.rag import get_collection


def chunk_markdown(text: str) -> list[str]:
    """Cắt markdown theo tiêu đề cấp 2 ("## ") để truy xuất chính xác hơn."""
    parts = re.split(r"(?=^##\s)", text, flags=re.MULTILINE)
    return [p.strip() for p in parts if p.strip()]


class Command(BaseCommand):
    help = "Nạp tài liệu docs/*.md vào ChromaDB cho RAG."

    def handle(self, *args, **options) -> None:
        self.stdout.write(conf.summary())
        self.stdout.write("\n[INGEST] Bắt đầu nạp tài liệu...")

        md_files = sorted(conf.DOCS_DIR.glob("*.md"))
        if not md_files:
            self.stdout.write(f"[INGEST] Không tìm thấy file .md nào trong {conf.DOCS_DIR}")
            return

        collection = get_collection(create_if_missing=True)

        # Xóa dữ liệu cũ để build lại từ đầu (tránh trùng lặp).
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
            self.stdout.write(f"  - {path.name}: {len(chunks)} đoạn")

        if ids:
            collection.add(ids=ids, documents=docs, metadatas=metas)

        self.stdout.write(
            self.style.SUCCESS(f"\n[INGEST] Hoàn tất! Đã nạp {len(ids)} đoạn từ {len(md_files)} file.")
        )
        self.stdout.write(f"[INGEST] Vector DB lưu tại: {conf.CHROMA_DB_DIR}")
