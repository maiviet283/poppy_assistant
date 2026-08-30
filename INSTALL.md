# Cài đặt — Cắm Poppy vào project Django của khách

Hướng dẫn tích hợp module `poppy_assistant` vào một project Django **đã có sẵn**. Nếu chỉ muốn chạy thử nhanh bằng project demo kèm repo, xem phần "Chạy thử nhanh" trong [README.md](README.md).

**Điều kiện tiên quyết**

- Project khách chạy **Django 5.x trên ASGI** (daphne / uvicorn) — cần cho SSE streaming và voice WebSocket. Chỉ dùng chat cũng nên chạy ASGI (SSE dùng async iterator).
- Python **≥ 3.12**.
- Đã bật `django.contrib.sessions` (lịch sử chat lưu trong session, key riêng `poppy_chat_messages`).
- Có **Google Gemini API key** (có billing).

---

## 1. Cài package

Chọn extras theo tính năng cần dùng — lõi là chat + RAG, voice/phone là optional:

```bash
# Lõi: chat + RAG
pip install "poppy-assistant @ git+https://github.com/maiviet283/poppy_assistant"

# + Voice qua trình duyệt (WebSocket, không cần số điện thoại) — kịch bản phổ biến nhất
pip install "poppy-assistant[voice] @ git+https://github.com/maiviet283/poppy_assistant"

# + Gọi qua số điện thoại thật (Twilio)
pip install "poppy-assistant[voice,phone] @ git+https://github.com/maiviet283/poppy_assistant"
```

> Đang phát triển trên cùng máy? Cài editable từ thư mục repo:
> `pip install -e . ` (hoặc `pip install -e ".[voice]"`).

## 2. `settings.py`

```python
INSTALLED_APPS += ["daphne", "channels", "poppy_assistant"]
ASGI_APPLICATION = "config.asgi.application"      # trỏ về asgi của project khách

# Giờ hẹn được parse theo timezone này — khai đúng để tránh lệch giờ.
TIME_ZONE = "Asia/Ho_Chi_Minh"
USE_TZ = True

POPPY = {
    "GEMINI_API_KEY": "...",            # bắt buộc (runtime)
    "BUSINESS_NAME": "Tiệm X",          # bắt buộc (cấu trúc — thiếu là fail loud khi khởi động)
    "ASSISTANT_NAME": "Poppy",
    "TONE": "thân thiện, ngắn gọn",
    "CUSTOM_RULES": "",                 # luật riêng của chủ quán (chèn vào prompt)
    "ENABLED_TOOLS": None,              # None = bật tất cả; hoặc ["booking", "faq"]
    "DOCS_DIR": BASE_DIR / "poppy_docs",
    "CHROMA_DB_DIR": BASE_DIR / "poppy_chroma",
    # "BOOKING_BACKEND": "myapp.backends.MyBackend",   # nếu khách có DB đặt lịch riêng (xem §7)
    # Thông báo nhân viên qua Telegram (để trống -> giả lập in log):
    "TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": "",
    # Twilio — chỉ cần khi dùng extra [phone]:
    "TWILIO_ACCOUNT_SID": "", "TWILIO_AUTH_TOKEN": "", "TWILIO_FROM_NUMBER": "",
    "PUBLIC_BASE_URL": "",
}
```

Danh sách key đầy đủ + default: xem `_SPEC` trong [poppy_assistant/conf.py](poppy_assistant/conf.py) hoặc bảng cấu hình trong [README.md](README.md).

## 3. `urls.py`

```python
path("api/", include("poppy_assistant.urls", namespace="poppy")),
# -> POST /api/chat , POST /api/call
```

## 4. `asgi.py` — ghép WebSocket

```python
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from poppy_assistant.routing import websocket_urlpatterns

django_asgi_app = get_asgi_application()
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": URLRouter([
        *websocket_urlpatterns,        # /ws/voice, /ws/twilio
        # ... route WebSocket sẵn có của khách (nếu có)
    ]),
})
```

> Cài chat-only (không có `google-genai`): `routing.py` tự bỏ route voice — không lỗi import.

## 5. Migrate + nạp dữ liệu

```bash
python manage.py migrate                 # tạo bảng poppy_offering / poppy_resource / poppy_booking
python manage.py seed_business           # dữ liệu mẫu (sửa theo khách, hoặc nhập qua /admin/)
# Bỏ tài liệu .md của khách vào POPPY["DOCS_DIR"], rồi:
python manage.py ingest                  # build vector DB (chạy lại mỗi khi sửa docs)
```

## 6. Kiểm tra

```bash
python manage.py check                   # sạch
python manage.py test poppy_assistant    # guardrails xanh (không tốn token)
```

Vào `/admin/` thấy Dịch vụ / Nguồn lực / Lịch hẹn. Nối frontend theo [INTEGRATION.md](INTEGRATION.md).

---

## Kịch bản: chỉ cần chat + voice qua mạng (không dùng số điện thoại)

Đây là kịch bản phổ biến nhất (khách nhúng widget chat + gọi voice ngay trên web). Bạn **không cần Twilio, không cần ngrok**:

1. Cài `pip install "poppy-assistant[voice] @ ..."` (không có `phone`).
2. Không khai các key `TWILIO_*` / `PUBLIC_BASE_URL` trong `POPPY`.
3. `asgi.py` vẫn ghép `websocket_urlpatterns` như §4 — route `/ws/twilio` nằm đó nhưng không dùng tới.
4. Frontend nối thẳng vào `WS /ws/voice` (xem [INTEGRATION.md](INTEGRATION.md) §2).

---

## 7. Khách đã có sẵn bảng dịch vụ / lịch hẹn?

Khi tích hợp vào một hệ thống đã hoàn thiện (khách đặt lịch trên web của họ rồi), bạn muốn AI ghi vào **bảng có sẵn của khách**, không dùng bảng `poppy_*`. Cách làm: viết một `BookingBackend` adapter.

```python
# myapp/poppy_backend.py
from poppy_assistant.booking.backends import BookingBackend   # Protocol để tham chiếu

class MyBackend:
    """Đọc/ghi vào model đặt lịch có sẵn của khách; trả dict đúng hình dạng Poppy cần."""
    def offerings(self): ...
    def resources(self): ...
    def offering_duration(self, name): ...
    def conflicts(self, start, duration, resource, exclude_id=None): ...
    def find_duplicate(self, phone, start, time_text): ...
    def bookings_for(self, phone): ...
    def get(self, phone, booking_id): ...
    def create(self, fields, start, source): ...
    def update(self, booking_id, changes): ...
    def cancel(self, booking_id): ...
```

Mọi method trả về `dict` chuẩn: `{"id", "name", "offering", "resource", "time", "phone", "status"}`. Interface đầy đủ + cài đặt mẫu: xem [poppy_assistant/booking/backends.py](poppy_assistant/booking/backends.py).

Khai backend trong `settings.py`:

```python
POPPY["BOOKING_BACKEND"] = "myapp.poppy_backend.MyBackend"
```

Khi đó bot dùng y hệt, **guardrails vẫn áp** (chúng nằm ở `service.py`, phía trên backend), và ba bảng `poppy_*` không dùng tới.

**Không muốn tạo ba bảng `poppy_*` cho gọn schema?** Thêm vào `settings.py`:

```python
MIGRATION_MODULES = {"poppy_assistant": None}     # migrate sẽ không tạo bảng poppy_*
```

Kèm gỡ đăng ký admin của ba model đó (vì bảng không tồn tại, mở trang admin của chúng sẽ lỗi):

```python
# myapp/apps.py -> AppConfig.ready()
from django.contrib import admin
from poppy_assistant.models import Offering, Resource, Booking
for m in (Offering, Resource, Booking):
    try:
        admin.site.unregister(m)
    except admin.sites.NotRegistered:
        pass
```

> Nếu khách là doanh nghiệp nhỏ **chưa có** hệ đặt lịch riêng (tiệm nail, spa nhỏ…), bỏ qua toàn bộ §7 — dùng `DefaultBookingBackend` mặc định, ba bảng `poppy_*` chính là nơi lưu dữ liệu.

---

## Xử lý sự cố

| Triệu chứng | Nguyên nhân thường gặp |
|---|---|
| Fail loud khi khởi động, báo thiếu `BUSINESS_NAME` | Chưa khai key cấu trúc bắt buộc trong `POPPY`. |
| Lượt chat đầu báo lỗi Gemini | Thiếu / sai `GEMINI_API_KEY`, hoặc key chưa bật billing. |
| Giờ hẹn bị lệch | Sai `TIME_ZONE` hoặc chưa `USE_TZ = True`. |
| RAG trả lời theo tài liệu cũ | Chưa chạy lại `python manage.py ingest` sau khi sửa `docs/`. |
| Voice WS không kết nối | Chưa cài extra `[voice]`, hoặc project chạy WSGI thay vì ASGI. |
| Cookie session mất qua mỗi lượt chat | FE chưa gửi `credentials:"include"`; nếu khác domain xem CORS trong [INTEGRATION.md](INTEGRATION.md) §4. |
