# INSTALL.md — Cắm Poppy vào project Django của khách

Điều kiện: project khách chạy **Django + ASGI** (daphne/channels/uvicorn) để có đủ
voice + chat streaming. Nếu chỉ cần chat, vẫn nên chạy ASGI (SSE streaming dùng
async iterator).

## 1. Cài package

```bash
# Lõi (chat + RAG):
pip install "git+https://github.com/ban/poppy-assistant@v1.0.0"

# Kèm voice online + gọi số điện thoại:
pip install "poppy-assistant[voice,phone] @ git+https://github.com/ban/poppy-assistant@v1.0.0"
```

> Trong repo demo này chưa publish lên git — cài trực tiếp bằng
> `pip install -e E:/project/ai_reception` (editable) hoặc copy thư mục
> `poppy_assistant/` vào project khách rồi `pip install -r requirements.txt`.

## 2. settings.py của khách

```python
INSTALLED_APPS += ["daphne", "channels", "poppy_assistant"]
ASGI_APPLICATION = "config.asgi.application"     # trỏ về asgi của khách

POPPY = {
    "GEMINI_API_KEY": "...",            # bắt buộc (runtime)
    "BUSINESS_NAME": "Tiệm X",          # bắt buộc (cấu trúc — thiếu là fail loud)
    "ASSISTANT_NAME": "Poppy",
    "TONE": "thân thiện, ngắn gọn",
    "CUSTOM_RULES": "",                 # luật riêng chủ quán (chèn vào prompt)
    "ENABLED_TOOLS": None,              # None = tất cả; hoặc ["booking", "faq"]
    "DOCS_DIR": BASE_DIR / "poppy_docs",
    "CHROMA_DB_DIR": BASE_DIR / "poppy_chroma",
    # "BOOKING_BACKEND": "myapp.backends.MyBackend",   # nếu khách có hệ booking riêng
    # Telegram (để trống -> giả lập in log):
    "TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": "",
    # Twilio (optional [phone]):
    "TWILIO_ACCOUNT_SID": "", "TWILIO_AUTH_TOKEN": "", "TWILIO_FROM_NUMBER": "",
    "PUBLIC_BASE_URL": "",
}
```

Yêu cầu sẵn có: `django.contrib.sessions` bật (lịch sử chat lưu trong session,
key riêng `poppy_chat_messages`).

## 3. urls.py của khách

```python
path("api/", include("poppy_assistant.urls", namespace="poppy")),
# -> POST /api/chat , POST /api/call
```

## 4. asgi.py của khách (ghép WebSocket)

```python
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from poppy_assistant.routing import websocket_urlpatterns

django_asgi_app = get_asgi_application()
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": URLRouter([
        *websocket_urlpatterns,        # /ws/voice, /ws/twilio
        # ... route WS sẵn có của khách (nếu có)
    ]),
})
```

> Cài chat-only (không có `google-genai`): `routing.py` tự bỏ route voice, không lỗi.

## 5. Migrate + nạp dữ liệu

```bash
python manage.py migrate                 # tạo bảng poppy_offering / poppy_resource / poppy_booking
python manage.py seed_business           # dữ liệu mẫu (sửa lại theo khách, hoặc nhập qua /admin/)
# Bỏ tài liệu .md của khách vào POPPY["DOCS_DIR"], rồi:
python manage.py ingest                  # build vector DB (chạy lại khi sửa docs)
```

## 6. Kiểm tra

```bash
python manage.py check                   # sạch
python manage.py test poppy_assistant    # guardrails xanh (không tốn token)
```

Vào `/admin/` thấy Dịch vụ / Nguồn lực / Lịch hẹn. Nối frontend theo
[INTEGRATION.md](INTEGRATION.md).

## Khách đã có sẵn bảng dịch vụ/lịch hẹn?

Viết một `BookingBackend` (xem `poppy_assistant/booking/backends.py`) trỏ vào model
của khách rồi khai `POPPY["BOOKING_BACKEND"] = "myapp.backends.MyBackend"`. Bot dùng
y hệt; guardrails vẫn áp. Khi đó `poppy_offering/poppy_resource/poppy_booking` không
dùng tới.
