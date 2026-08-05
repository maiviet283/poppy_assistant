# Poppy — trợ lý AI lễ tân (reusable Django app)

Module hoá từ demo "Petal & Polish": trợ lý AI **chat + gọi điện** (RAG + function
calling, đặt/sửa/hủy lịch ghi thẳng DB) đóng gói thành **Django app cắm vào project
Django sẵn có của khách** (Cách A — khách tự host, mỗi deploy phục vụ 1 doanh nghiệp).

- Nhà cung cấp AI: thuần Google Gemini (chat qua API tương thích OpenAI + voice qua
  Gemini Live). Embedding RAG chạy **local** (ONNX MiniLM) — miễn phí, không quota.
- Kiến trúc & lý do thiết kế: xem **[MODULE_PLAN.md](MODULE_PLAN.md)**.
- Bản multi-tenant (Cách B, do mình host): **[AI_PLATFORM_ARCHITECTURE.md](AI_PLATFORM_ARCHITECTURE.md)**.

## Repo này gồm 2 phần

| Thư mục | Vai trò |
|---|---|
| `poppy_assistant/` | ★ **MODULE** — thứ đem cắm vào project khách (đóng gói pip được) |
| `config/` + `manage.py` | Project **host demo** đóng vai "project của khách" để chạy & test |

Khi giao khách: chỉ cần `poppy_assistant/` (cài qua pip) + hướng dẫn trong
[INSTALL.md](INSTALL.md) và [INTEGRATION.md](INTEGRATION.md). Bỏ `config/` — đó là demo.

## Chạy thử nhanh (project host demo)

```bash
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt
copy .env.example .env                               # rồi điền GEMINI_API_KEY

python manage.py migrate
python manage.py createsuperuser                     # tài khoản /admin/
python manage.py seed_business                       # dữ liệu mẫu (Offering/Resource)
python manage.py ingest                              # build vector DB từ docs/*.md

python manage.py runserver 8000
```

- `http://localhost:8000/` — **trang test tích hợp** (chat SSE hoạt động thật).
- `http://localhost:8000/admin/` — quản lý Dịch vụ / Nguồn lực / Lịch hẹn.
- API: `POST /api/chat`, `POST /api/call`; WebSocket `/ws/voice`, `/ws/twilio`.

## Kiểm thử không tốn token

```bash
python manage.py test poppy_assistant        # guardrails (logic thuần)
python manage.py check
```

## Cấu trúc module (tóm tắt)

```
poppy_assistant/
  conf.py            config-contract: đọc & validate settings.POPPY
  gateway.py         gọi LLM + retry 503 + failover model
  orchestrator.py    lõi chat (ask/ask_stream) — giữ lưới an toàn streaming
  prompts.py         system prompt dựng từ business profile (config-as-data)
  rag.py             ChromaDB + embedding local ONNX
  models.py          Offering / Resource / Booking (db_table="poppy_*")
  guardrails.py      helper confirm-before-commit (unit-test được)
  booking/
    backends.py      BookingBackend (adapter seam) + DefaultBookingBackend
    service.py       máy trạng thái đặt lịch (guardrails ở tầng tool)
  tools/
    registry.py      khai báo tool MỘT nơi (chat + voice cùng đọc)
    booking_tools.py / knowledge_tools.py
  consumers.py / twilio_consumer.py / telephony.py / voice_config.py   (voice)
  views.py / urls.py / routing.py
  management/commands/  ingest, seed_business
  tests/             test_guardrails.py
```
