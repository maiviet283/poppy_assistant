"""apps.py — AppConfig của module: validate cấu hình + warmup RAG (lười, nền)."""

from __future__ import annotations

import threading

from django.apps import AppConfig


class PoppyAssistantConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "poppy_assistant"
    label = "poppy_assistant"
    verbose_name = "Poppy — trợ lý AI lễ tân"

    def ready(self) -> None:
        # 1) Fail loud nếu thiếu cấu hình cấu trúc (Trụ #3).
        from poppy_assistant import conf

        conf.validate()

        # 2) Warmup RAG chạy NỀN + nuốt lỗi (Trụ #4: zero side-effect, không được
        #    làm chậm/chết manage.py của khách nếu chưa build index).
        def _warm() -> None:
            try:
                from poppy_assistant import rag

                rag.search("warmup")
            except Exception:
                pass

        threading.Thread(target=_warm, daemon=True).start()
