"""
poppy_assistant — Trợ lý AI lễ tân đóng gói thành Django app tái sử dụng.

Cắm vào project Django sẵn có của khách (xem INSTALL.md). Public API — thứ khách
được phép dựa vào — chỉ gồm 4 điểm nối:

  1. include("poppy_assistant.urls", namespace="poppy")   -> /chat, /call
  2. poppy_assistant.routing.websocket_urlpatterns         -> /ws/voice, /ws/twilio
  3. dict ``POPPY`` trong settings                          -> mọi cấu hình (xem conf.py)
  4. management commands: migrate, seed_business, ingest

Mọi thứ khác là NỘI BỘ, có thể đổi giữa các version.
"""

__version__ = "1.0.0"

default_app_config = "poppy_assistant.apps.PoppyAssistantConfig"
