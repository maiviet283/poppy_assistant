from __future__ import annotations

import threading

from django.apps import AppConfig


class PoppyAssistantConfig(AppConfig):
    """Django app config: validate settings and warm up the retrieval index."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "poppy_assistant"
    label = "poppy_assistant"
    verbose_name = "Poppy assistant"

    def ready(self) -> None:
        """Fail fast on invalid config, then warm the RAG index off the main thread."""
        from poppy_assistant import conf

        conf.validate()

        def _warm() -> None:
            try:
                from poppy_assistant import rag

                rag.search("warmup")
            except Exception:
                pass

        threading.Thread(target=_warm, daemon=True).start()
