<div align="center">

# 🌸 Poppy — Trợ lý AI lễ tân cho doanh nghiệp dịch vụ

**Chat + gọi điện bằng AI, trả lời khách và tự đặt/sửa/hủy lịch hẹn — đóng gói thành một Django app cắm thẳng vào project sẵn có.**

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.x-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Gemini](https://img.shields.io/badge/AI-Google%20Gemini-4285F4?logo=google&logoColor=white)](https://ai.google.dev/)
[![Version](https://img.shields.io/badge/version-1.0.0-blue)](CHANGELOG.md)

</div>

---

## Poppy là gì

Poppy là **trợ lý AI lễ tân** cho doanh nghiệp dịch vụ (mẫu demo: tiệm nail *Petal & Polish*, nhưng trừu tượng hóa cho mọi ngành có "dịch vụ" và "lịch hẹn": spa, phòng khám, nhà hàng, studio…). Nó trả lời khách qua **chat** và **gọi điện**, kết hợp hai năng lực:

- **RAG** — trả lời câu hỏi sự thật (giờ mở cửa, chính sách, bảng giá) từ tài liệu `docs/*.md` của doanh nghiệp.
- **Function calling** — đặt / sửa / hủy lịch hẹn ghi thẳng vào database, có **guardrails** chống đặt nhầm, đặt trùng, đặt đè giờ.

Điểm khác biệt trong thiết kế: đây **không phải một website**, mà là một **module tái sử dụng**. Bạn `pip install` vào project Django có sẵn của khách, khai một khối cấu hình, và có ngay lễ tân AI — không phải dựng lại hệ thống.

## Tính năng chính

| | |
|---|---|
| 💬 **Chat streaming (SSE)** | Trả lời hiện dần như người nhắn tin, đã strip Markdown thành văn bản thuần. |
| 📞 **Voice realtime** | Gọi qua trình duyệt (WebSocket) hoặc số điện thoại thật (Twilio) — chung một "bộ não". |
| 📚 **RAG embedding local** | Vector search bằng ONNX MiniLM chạy **local** — miễn phí, không quota, không bao giờ "chết key". |
| 📅 **Đặt lịch có guardrails** | Máy trạng thái *confirm-before-commit*: không ghi DB khi thiếu thông tin, chưa xác nhận, hoặc trùng giờ. |
| 🔌 **Cắm vào DB sẵn có** | Có hệ đặt lịch riêng? Viết một `BookingBackend` adapter — không đụng lõi, guardrails vẫn áp. |
| 🎭 **Nhân cách cấu hình được** | Tên doanh nghiệp, giọng điệu, luật riêng khai bằng config — không sửa code. |
| 🧩 **Cài chọn lọc** | Lõi = chat + RAG. Voice/phone là extras optional — chỉ cần chat thì không kéo về thư viện voice. |
| 🌐 **Đa ngôn ngữ** | Poppy "mirror" ngôn ngữ của khách — khách nhắn tiếng nào, trả lời tiếng đó. |

## Kiến trúc

```
                         ┌──────────── tools/registry.py ────────────┐
                         │   khai báo tool MỘT NƠI (booking + faq)     │
                         └────────────────────────────────────────────┘
                                 ▲                        ▲
   CHAT (text)                   │                        │            VOICE (audio)
   POST /api/chat  ─►  orchestrator.py (RAG + function calling)  ◄─  WS /ws/voice   (trình duyệt)
        (SSE)                    │                        │            WS /ws/twilio (điện thoại)
                                 ├─► gateway.py  ─► Gemini (OpenAI-compat API)
                                 └─► rag.py      ─► ChromaDB (embedding local ONNX)
                                              │
                                 booking/service.py  (guardrails: confirm-before-commit)
                                              │
                                 booking/backends.py (adapter seam) ─► models.py (bảng poppy_*)
```

Nhà cung cấp AI: **thuần Google Gemini** — chat qua API tương thích OpenAI, voice qua Gemini Live. Chi tiết thiết kế và lý do từng quyết định: xem **[MODULE_PLAN.md](MODULE_PLAN.md)**.

## Yêu cầu hệ thống

- **Python ≥ 3.12** (dùng `audioop` cho chuyển mã audio Twilio).
- **Django 5.x** chạy trên **ASGI** (daphne) — cần cho SSE streaming và voice WebSocket.
- **Google Gemini API key** (có billing) — cho chat và voice.
- Database bất kỳ Django hỗ trợ (demo dùng SQLite; production khuyến nghị PostgreSQL).

---

## Chạy thử nhanh (project demo)

Repo này kèm sẵn một project host demo (`config/` + `manage.py`) đóng vai "project của khách" để bạn chạy thử ngay.

```bash
git clone https://github.com/maiviet283/poppy_assistant.git
cd poppy_assistant

python -m venv .venv
.venv\Scripts\activate                    # Windows;  macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env                     # rồi mở .env điền GEMINI_API_KEY

python manage.py migrate                   # tạo bảng poppy_offering / poppy_resource / poppy_booking
python manage.py createsuperuser           # tài khoản vào /admin/
python manage.py seed_business             # nạp dữ liệu mẫu (idempotent)
python manage.py ingest                    # build vector DB từ docs/*.md

python manage.py runserver 8000
```

| URL | Nội dung |
|---|---|
| http://localhost:8000/ | Trang test tích hợp — chat SSE chạy thật |
| http://localhost:8000/admin/ | Quản lý Dịch vụ / Nguồn lực / Lịch hẹn |

> ⚠️ Đổi `.env` phải **restart server** mới có hiệu lực.
> ⚠️ Sửa file trong `docs/` phải chạy lại `python manage.py ingest`, nếu không RAG dùng index cũ.

---

## Cắm vào project Django có sẵn

Đây mới là cách dùng chính. Tóm tắt bốn bước (chi tiết đầy đủ trong **[INSTALL.md](INSTALL.md)**):

**1. Cài package** (chọn extras theo nhu cầu):

```bash
pip install "poppy-assistant @ git+https://github.com/maiviet283/poppy_assistant"          # chat + RAG
pip install "poppy-assistant[voice] @ git+https://github.com/maiviet283/poppy_assistant"    # + voice trình duyệt
pip install "poppy-assistant[voice,phone] @ git+https://github.com/maiviet283/poppy_assistant"  # + gọi số điện thoại
```

**2. `settings.py`** — thêm app và khai cấu hình:

```python
INSTALLED_APPS += ["daphne", "channels", "poppy_assistant"]
ASGI_APPLICATION = "config.asgi.application"

TIME_ZONE = "Asia/Ho_Chi_Minh"   # QUAN TRỌNG: giờ hẹn parse theo timezone này
USE_TZ = True

POPPY = {
    "GEMINI_API_KEY": "...",         # bắt buộc (runtime)
    "BUSINESS_NAME": "Tiệm X",       # bắt buộc (cấu trúc — thiếu là fail loud khi khởi động)
    "ASSISTANT_NAME": "Poppy",
    "TONE": "thân thiện, ngắn gọn",
    "CUSTOM_RULES": "",              # luật riêng của chủ quán, chèn vào prompt
}
```

**3. `urls.py` + `asgi.py`** — nối HTTP và WebSocket:

```python
# urls.py
path("api/", include("poppy_assistant.urls", namespace="poppy")),

# asgi.py
from poppy_assistant.routing import websocket_urlpatterns
# ... đưa *websocket_urlpatterns vào URLRouter cho "websocket"
```

**4. Khởi tạo dữ liệu:**

```bash
python manage.py migrate
python manage.py seed_business     # hoặc nhập trực tiếp qua /admin/
python manage.py ingest            # sau khi bỏ docs/*.md của khách vào DOCS_DIR
```

> 💡 **Khách đã có DB đặt lịch riêng?** Viết một `BookingBackend` trỏ vào model của họ rồi khai `POPPY["BOOKING_BACKEND"]`. Bot dùng y hệt, guardrails vẫn áp, ba bảng `poppy_*` không dùng tới. Xem cuối [INSTALL.md](INSTALL.md).

---

## Cấu hình

Toàn bộ cấu hình đọc từ **một dict `settings.POPPY`** (contract tập trung trong `conf.py`). Các key hay dùng:

| Key | Mặc định | Ghi chú |
|---|---|---|
| `GEMINI_API_KEY` | — | Bắt buộc runtime (thiếu → cảnh báo, lỗi ở lượt chat đầu) |
| `BUSINESS_NAME` | — | **Bắt buộc cấu trúc** — thiếu là fail loud khi khởi động |
| `ASSISTANT_NAME` / `TONE` / `CUSTOM_RULES` | Poppy / warm… / "" | Nhân cách bot (config-as-data) |
| `CHAT_MODEL` / `CHAT_MODEL_FALLBACK` | `gemini-3.1-flash-lite` / `gemini-2.5-flash-lite` | Failover khi 503/429 |
| `VOICE_MODEL` | `gemini-3.1-flash-live-preview` | Gemini Live |
| `ENABLED_TOOLS` | `None` (bật hết) | Hoặc list tag: `["booking", "faq"]` |
| `MAX_TOOL_ROUNDS` | `5` | Số vòng gọi tool tối đa mỗi lượt |
| `BOOKING_BACKEND` | `DefaultBookingBackend` | Dotted path adapter của khách |
| `DOCS_DIR` / `CHROMA_DB_DIR` | `poppy_docs` / `poppy_chroma` | Nguồn tài liệu & vector store cho RAG |
| `RAG_TOP_K` | `4` | Số đoạn tài liệu lấy về mỗi câu hỏi |
| `TELEGRAM_*` | "" | Trống → thông báo nhân viên chạy giả lập (in log) |
| `TWILIO_*` / `PUBLIC_BASE_URL` | "" | Optional `[phone]` — gọi đi / gọi đến |

Danh sách đầy đủ: xem `_SPEC` trong [poppy_assistant/conf.py](poppy_assistant/conf.py).

## Sử dụng

**Quản lý danh mục & lịch hẹn.** Vào `/admin/` để thêm/sửa **Dịch vụ** (`Offering`: tên, giá, thời lượng), **Nguồn lực** (`Resource`: thợ/bàn/phòng, sức chứa), và xem **Lịch hẹn** (`Booking`) Poppy ghi vào.

**Cập nhật kiến thức doanh nghiệp (RAG).** Sửa các file `.md` trong `DOCS_DIR` (giờ mở cửa, chính sách, FAQ…) rồi chạy lại `python manage.py ingest`.

**Nối frontend.** Module chỉ làm backend; FE (React/Vue/HTML) nói chuyện qua hợp đồng API ổn định. Có sẵn code mẫu vanilla JS chạy được ngay tại `examples/poppy-embed-example.html`. Tóm tắt hợp đồng (chi tiết trong **[INTEGRATION.md](INTEGRATION.md)**):

| Endpoint | Mục đích |
|---|---|
| `POST /api/chat` | Chat. `stream:true` → SSE (`delta`/`reset`/`done`); ngược lại JSON `{reply}`. FE phải gửi cookie session và xử lý `reset`. |
| `WS /ws/voice` | Voice qua trình duyệt: mic PCM 16kHz lên, bot PCM 24kHz xuống + event JSON. FE phải xử lý `interrupt`. |
| `WS /ws/twilio` | Twilio Media Stream (server-to-server, không phải cho FE). |
| `POST /api/call` | AI gọi ĐI tới một số (optional `[phone]`). |

## Kiểm thử

Không tốn token (logic thuần, chạy trên backend giả — không đụng DB, không gọi LLM):

```bash
python manage.py test poppy_assistant
python manage.py check
python manage.py makemigrations --check --dry-run
```

## Cấu trúc repo

```
poppy_assistant/            ★ MODULE — sản phẩm thật, đem cắm vào project khách
├── conf.py                 config-contract: đọc & validate settings.POPPY
├── gateway.py              gọi LLM + retry 503 + failover model
├── orchestrator.py         lõi chat (ask / ask_stream) + lưới an toàn streaming
├── prompts.py              system prompt dựng từ business profile
├── rag.py                  ChromaDB + embedding local ONNX
├── models.py               Offering / Resource / Booking  (db_table = "poppy_*")
├── guardrails.py           helper confirm-before-commit (unit-test được)
├── booking/
│   ├── backends.py         BookingBackend (adapter seam) + DefaultBookingBackend
│   └── service.py          máy trạng thái đặt lịch (guardrails ở tầng tool)
├── tools/                  registry (khai tool một nơi) + booking/knowledge tools
├── consumers.py            voice online (WebSocket, PCM)
├── twilio_consumer.py      voice qua điện thoại (µ-law 8k ↔ PCM)
├── voice_config.py         cấu hình Gemini Live
├── views.py / urls.py / routing.py
├── management/commands/    ingest, seed_business
└── tests/                  test_guardrails.py

config/ + manage.py         Project host DEMO — bỏ khi giao khách
docs/                       Tài liệu nghiệp vụ (nguồn RAG)
examples/                   Code mẫu nhúng frontend
```

## Tài liệu

| File | Nội dung |
|---|---|
| [INSTALL.md](INSTALL.md) | Cắm module vào project Django của khách (settings / urls / asgi / migrate) |
| [INTEGRATION.md](INTEGRATION.md) | Hợp đồng API cho frontend (chat SSE, voice WS, gọi điện) |
| [MODULE_PLAN.md](MODULE_PLAN.md) | Kiến trúc module & lý do từng quyết định thiết kế |
| [AI_PLATFORM_ARCHITECTURE.md](AI_PLATFORM_ARCHITECTURE.md) | Tầm nhìn multi-tenant (bản thiết kế) |
| [CHANGELOG.md](CHANGELOG.md) | Lịch sử phiên bản |
| [CLAUDE.md](CLAUDE.md) | Quy ước code & hướng dẫn cho người phát triển |

## Ghi chú vận hành

- Chạy **ASGI** (daphne), không chạy WSGI thuần — cần cho SSE và voice WS.
- Bí mật (Gemini/Twilio key) không bao giờ được log; `conf.summary()` đã mask key.
- Khai đúng `TIME_ZONE` + `USE_TZ = True` trong `settings.py` — giờ hẹn parse theo timezone của project; sai timezone là bug hay gặp nhất khi bàn giao.
- Cài chat-only (không có `google-genai`): `routing.py` tự bỏ route voice, app vẫn chạy bình thường.
