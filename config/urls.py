"""
urls.py — Định tuyến project host demo.

  /admin/  -> Django admin (quản lý Offering/Resource/Booking)
  /api/    -> API của module (poppy_assistant.urls)
  /        -> trang test tích hợp (examples/poppy-embed-example.html) — same-origin
              nên cookie session hoạt động, tiện thử nhanh không dính CORS.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path

_EXAMPLE = Path(settings.BASE_DIR) / "examples" / "poppy-embed-example.html"


def demo_index(request):
    if _EXAMPLE.exists():
        return HttpResponse(_EXAMPLE.read_text(encoding="utf-8"))
    return HttpResponse("<h1>Poppy module</h1><p>API ở <code>/api/chat</code>.</p>")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("poppy_assistant.urls", namespace="poppy")),
    path("", demo_index, name="demo_index"),
]
