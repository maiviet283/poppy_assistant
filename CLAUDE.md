# CLAUDE.md

Hướng dẫn cho Claude Code (và lập trình viên) khi làm việc trong repo này.

> Ngôn ngữ: **mã & comment bằng tiếng Việt** (theo phong cách sẵn có của dự án).
> Riêng **mô tả tool, giá trị tool trả về, và system prompt viết bằng tiếng Anh** —
> vì Poppy "mirror" ngôn ngữ khách; prompt/tool tiếng Anh giúp model bám luật ổn định
> rồi tự trả lời khách bằng ngôn ngữ của họ. Đừng dịch các chuỗi này sang tiếng Việt.

---

## 0. Quy ước viết code (BẮT BUỘC)

Áp dụng cho mọi file Python trong repo. Khách hàng của dự án là dân IT — code phải sạch,
gọn, và **không lộ dấu vết "sinh bằng AI"**.

**Ngôn ngữ & comment**
- Toàn bộ **comment, docstring, log, và chuỗi chương trình viết bằng tiếng Anh**, súc tích.
- **KHÔNG có docstring/comment tiêu đề ở đầu file.** File bắt đầu ngay bằng `from __future__
  import annotations` (nếu cần) rồi tới import.
- **Mọi class và function/method phải có docstring tiếng Anh một dòng** (tối đa vài dòng nếu
  thật cần) nói *nó làm gì*, không mô tả từng bước hiển nhiên.
- **Không viết comment "kiểu AI"**: không giải thích điều hiển nhiên, không comment lan man,
  không kể lể (`# vector DB cho RAG (embedding local ONNX)`, `# bài học đổ máu #5`…). Chỉ
  comment khi lý do *không* đọc được từ code (một quyết định trái trực giác, một cạm bẫy).
- Không dùng emoji trong code trừ khi là nội dung thông báo cho người dùng cuối.

**Clean code**
- Đặt tên rõ nghĩa; hàm làm một việc; tránh lặp (DRY); early-return thay vì lồng sâu.
- Giữ public API ổn định (§8 Hợp đồng API). Đổi hành vi phải có lý do.
- Không thêm phụ thuộc mới ở tầng lõi (chat/RAG). Voice import phải **lazy** (Trụ #1).

**Truy vấn DB — bắt buộc**
- **Tránh N+1 query.** Không gọi DB trong vòng lặp trên một queryset. Nếu cần dữ liệu phụ
  thuộc (VD thời lượng offering cho từng booking) → nạp **một map/dict một lần** rồi tra cứu
  trong bộ nhớ (xem `DefaultBookingBackend.conflicts` + `_duration_map`).
- **Chỉ lấy đúng cột cần** — dùng `.values()` / `.values_list()` khi chỉ cần dữ liệu thô, hoặc
  `.only(*fields)` khi cần model instance. Không nạp cả row nếu chỉ dùng vài trường; cũng
  không thiếu trường khiến Django lazy-load gây thêm query.
- Dùng `select_related` / `prefetch_related` khi truy cập quan hệ. Bọc thao tác ghi nhiều
  bước trong `transaction.atomic()`; dùng `select_for_update()` cho update/cancel.

**Verify sau khi sửa** (không tốn token):
```powershell
python manage.py check
python manage.py makemigrations --check --dry-run   # models & migrations đồng bộ
python manage.py test poppy_assistant
```

---

## 1. Poppy là gì

Poppy là **trợ lý AI lễ tân** cho doanh nghiệp dịch vụ (mẫu demo: tiệm nail "Petal &
Polish"). Nó trả lời khách qua **chat (text)** và **gọi điện (voice)**, kết hợp:

- **RAG** — trả lời câu hỏi sự thật (giờ mở cửa, chính sách, giá) từ tài liệu `docs/*.md`.
- **Function calling** — đặt / sửa / hủy lịch hẹn ghi thẳng vào DB, có guardrails.

Nhà cung cấp AI: **thuần Google Gemini** (chat qua API tương thích OpenAI, voice qua
Gemini Live). **Embedding RAG chạy local** bằng ONNX MiniLM (miễn phí, không quota,
không cần key) — đây là lựa chọn thiết kế quan trọng: RAG không bao giờ "chết key".

### Repo gồm 2 phần — đừng lẫn lộn

| Thư mục | Vai trò |
|---|---|
| `poppy_assistant/` | ★ **MODULE** — sản phẩm thật, đóng gói pip được, đem cắm vào project khách. **Mọi thay đổi logic nằm ở đây.** |
| `config/` + `manage.py` | Project **host demo** đóng vai "project Django của khách" để chạy & test. Khi giao khách thì **bỏ** thư mục này. |

Mô hình phân phối: **Cách A** — khách tự host, mỗi deploy phục vụ 1 doanh nghiệp
(single-tenant). Bản multi-tenant (Cách B) chỉ là tài liệu thiết kế, chưa hiện thực.

### Tài liệu thiết kế (đọc khi cần chiều sâu)
- `README.md` — tổng quan + chạy thử nhanh.
- `MODULE_PLAN.md` — kiến trúc module & lý do từng quyết định ("các Trụ", "các bẫy demo").
- `AI_PLATFORM_ARCHITECTURE.md` — tầm nhìn multi-tenant (Cách B).
- `INSTALL.md` — cắm module vào project khách (settings/urls/asgi/migrate).
- `INTEGRATION.md` — hợp đồng API cho frontend (SSE chat, WS voice, `/call`).
- `CHANGELOG.md` — lịch sử phiên bản.

---

## 2. Lệnh thường dùng

Chạy từ thư mục gốc repo. Windows PowerShell:

```powershell
# --- Thiết lập lần đầu ---
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env          # rồi điền GEMINI_API_KEY

# --- Khởi tạo dữ liệu ---
python manage.py migrate             # tạo bảng poppy_offering / poppy_resource / poppy_booking
python manage.py createsuperuser     # tài khoản vào /admin/
python manage.py seed_business       # nạp dữ liệu mẫu (Offering + Resource), idempotent
python manage.py ingest              # build vector DB từ docs/*.md (chạy LẠI mỗi khi sửa docs)

# --- Chạy server (ASGI — cần cho SSE streaming + voice WS) ---
python manage.py runserver 8000
#   http://localhost:8000/        trang test tích hợp (chat SSE chạy thật)
#   http://localhost:8000/admin/  quản lý Dịch vụ / Nguồn lực / Lịch hẹn

# --- Kiểm thử (KHÔNG tốn token — logic thuần) ---
python manage.py test poppy_assistant
python manage.py check
```

> ⚠ Đổi `.env` phải **restart server** mới có hiệu lực.
> ⚠ `ingest` phải chạy lại sau mỗi lần thêm/sửa file trong `docs/`, nếu không RAG dùng index cũ.

Voice qua số điện thoại thật cần extras `[phone]` + Twilio + một public tunnel
(`PUBLIC_BASE_URL`, ví dụ ngrok) để Twilio nối ngược `/ws/twilio`.

---

## 3. Kiến trúc & luồng dữ liệu

### Hai kênh, một bộ não

```
                       ┌─────────────── tools/registry.py ───────────────┐
                       │   khai báo tool MỘT NƠI (booking + knowledge)     │
                       └──────────────────────────────────────────────────┘
                              ▲ openai_schemas()          ▲ genai_tool()
                              │ execute_tool()            │ run_tool()
   CHAT (text)                │                           │           VOICE (audio)
   POST /api/chat  ──► orchestrator.py                 voice_config.py ◄── WS /ws/voice   (online, consumers.py)
   (views.py, SSE) ──►  (RAG + function calling)       (Gemini Live)   ◄── WS /ws/twilio  (điện thoại, twilio_consumer.py)
                              │                           │
                              └──► gateway.py (LLM) ──► Gemini (OpenAI-compat API)
                              └──► rag.py (ChromaDB, embedding local)
                                          │
                       booking/service.py (guardrails: confirm-before-commit)
                                          │
                       booking/backends.py (adapter seam) ──► models.py (poppy_*)
                                          │
                                    notify.py (Telegram báo nhân viên)
```

### Đường đi một lượt chat
1. `views.chat_api` nhận `{message, stream}`, lấy lịch sử từ **session Django**
   (key `poppy_chat_messages`), tạo `Orchestrator`.
2. `Orchestrator.ask` / `ask_stream`: `rag.search(question)` → ghép RAG + ngày giờ +
   câu hỏi thành user context (`prompts.build_user_context`).
3. Gọi model qua `gateway.LLMGateway.create` (retry 503/429 → failover model dự phòng).
4. Nếu model gọi tool → `tool_registry.execute_tool` → `booking/service.py` (qua backend)
   → trả JSON kết quả → lặp tối đa `MAX_TOOL_ROUNDS` lượt.
5. Trả text (JSON `{reply}` hoặc SSE `{delta}`/`{reset}`/`{done}`), lưu lại lịch sử vào session.

### Đường đi voice
`consumers.py` (online, PCM) và `twilio_consumer.py` (điện thoại, µ-law 8k ↔ PCM qua
`audioop`) là **hai đường ống audio khác nhau nhưng chung "bộ não"**: cùng
`voice_config.build_live_config()` + `run_tool()` + registry. Key Gemini chỉ nằm ở server.

---

## 4. Các trụ thiết kế — GIỮ khi sửa code

Vi phạm các nguyên tắc này sẽ phá tính "cắm được vào project khách". Đọc `MODULE_PLAN.md`
để biết đầy đủ; tóm tắt:

1. **Cài chọn lọc (extras).** Lõi = chat + RAG. Voice/phone là optional
   (`pip install poppy-assistant[voice,phone]`). `routing.py` **nuốt lỗi import** nếu
   thiếu `google-genai` → cài chat-only vẫn chạy. Đừng `import google.genai` ở tầng lõi;
   voice import phải **lazy**.
2. **Namespace `poppy_*`.** Mọi bảng đặt `db_table = "poppy_offering/resource/booking"`,
   session key `poppy_chat_messages`, URL namespace `poppy`. **Không đụng** bảng/khoá sẵn
   có của khách.
3. **Config-contract tập trung (`conf.py`).** Mọi cấu hình đọc **từ `conf`**, không rải
   `os.getenv` khắp nơi. Khách khai **một dict `settings.POPPY`**. Thêm cấu hình mới = thêm
   dòng vào `_SPEC` trong `conf.py`. Thiếu key cấu trúc bắt buộc (`BUSINESS_NAME`) → fail
   loud lúc khởi động; thiếu `GEMINI_API_KEY` → chỉ cảnh báo (lỗi runtime).
4. **Zero side-effect lúc import.** `conf` dùng PEP 562 `__getattr__` (đọc lười). `apps.ready`
   chỉ validate + warmup RAG **chạy nền, nuốt lỗi** — không được làm chậm/chết
   `manage.py` của khách.
5. **Adapter seam cho booking.** `booking/backends.py` định nghĩa interface
   `BookingBackend`; `DefaultBookingBackend` chạy trên model của module. Khách có hệ booking
   riêng (Google Calendar, KiotViet…) thì viết `class MyBackend(BookingBackend)` và khai
   `POPPY["BOOKING_BACKEND"]`. **Guardrails nằm TRÊN backend** (`service.py`) nên áp cho
   mọi backend.
6. **Config-as-data cho nhân cách.** System prompt (`prompts.py`, `voice_config.py`) ghép
   từ `BUSINESS_NAME / ASSISTANT_NAME / TONE / CUSTOM_RULES`. Đổi tính cách/tên doanh nghiệp
   **không cần sửa code**. System prompt dựng LẠI mỗi request (session sống lâu không giữ prompt cũ).
7. **Registry tool một nơi.** Thêm tool = một lần `register(...)` trong `tools/*.py`. Cả chat
   và voice cùng đọc. Đừng khai lại schema tool ở chỗ khác.

---

## 5. Guardrails đặt lịch — bất biến quan trọng nhất

`booking/service.py` là **máy trạng thái confirm-before-commit**. Nguyên tắc: *prompt có
thể bị model phớt lờ; cửa chặn trong code thì không.* Các cửa (đều KHÔNG ghi DB nếu chưa đạt):

| Trạng thái | Điều kiện | Ý nghĩa |
|---|---|---|
| `need_more_info` | thiếu trường bắt buộc | chưa đủ name/phone/offering/resource/time |
| `needs_confirmation` | `customer_confirmed` chưa true | phải cho khách xác nhận tóm tắt trước |
| `already_booked` (ok=true) | trùng y hệt lịch đã có | **idempotent** — gật 2 lần vẫn 1 lịch |
| `use_update_instead` | trùng SĐT+giờ nhưng khác nội dung | phải `update_booking`, không tạo mới |
| `resource_busy` | nguồn lực kín giờ | báo khách, đề nghị giờ/nguồn lực khác |

Khi sửa logic đặt lịch: **tuyệt đối không trả `ok=true` khi chưa thực sự ghi**, và giữ
tính idempotent. Test guard ở `tests/test_guardrails.py` chạy trên backend giả (không
đụng DB, không tốn token) — **thêm test ở đó khi thêm cửa chặn**.

Helper thuần logic (`guardrails.py`): `is_true()` chuẩn hóa cờ xác nhận (model gửi bool
hoặc "true"/"yes"/"1"), `missing_fields()`.

---

## 6. Mô hình dữ liệu (`models.py`)

Trừu tượng chung cho nhiều ngành:
- **`Offering`** — "dịch vụ gì" (tên, giá, thời lượng). VD: làm gel, khám tổng quát.
- **`Resource`** — "ai/cái gì phục vụ" (thợ, bác sĩ, bàn, phòng).
- **`Booking`** — lịch hẹn Poppy ghi vào. Lưu offering/resource dưới dạng **TEXT** (không
  FK) để lịch cũ không hỏng khi khách sửa danh mục. Có `source` (chat/voice) và `status`
  (new/confirmed/done/cancelled). Hủy = đổi status, **không xóa cứng**.

---

## 7. Cấu hình (`settings.POPPY` → `conf.py`)

Khách khai một dict `POPPY`; `conf.py` điền default + cho fallback biến môi trường (tiện
dev). Các key đáng chú ý (xem `_SPEC` để đủ):

| Key | Mặc định | Ghi chú |
|---|---|---|
| `GEMINI_API_KEY` | — | bắt buộc runtime (thiếu → cảnh báo, lỗi ở lượt chat đầu) |
| `BUSINESS_NAME` | — | **bắt buộc cấu trúc** — thiếu là fail loud |
| `CHAT_MODEL` / `CHAT_MODEL_FALLBACK` | `gemini-3.1-flash-lite` / `gemini-2.5-flash-lite` | failover khi 503 |
| `VOICE_MODEL` | `gemini-3.1-flash-live-preview` | Gemini Live |
| `ASSISTANT_NAME` / `TONE` / `CUSTOM_RULES` | Poppy / warm… / "" | config-as-data cho prompt |
| `ENABLED_TOOLS` | `None` (bật hết) | hoặc list tag: `["booking", "faq"]` |
| `MAX_TOOL_ROUNDS` | `5` | số vòng tool tối đa/lượt |
| `BOOKING_BACKEND` | `DefaultBookingBackend` | dotted path adapter của khách |
| `DOCS_DIR` / `CHROMA_DB_DIR` | `poppy_docs` / `poppy_chroma` | RAG |
| `RAG_TOP_K` | `4` | số đoạn tài liệu lấy về |
| `TELEGRAM_*` | "" | trống → notify chạy **giả lập in log** |
| `TWILIO_*` / `PUBLIC_BASE_URL` | "" | optional `[phone]` — gọi đi |

Model ID (`gemini-3.1-flash-lite`, `gemini-3.1-flash-live-preview`, …) là giá trị của
riêng dự án — **giữ nguyên**, đừng đổi trừ khi được yêu cầu.

---

## 8. Hợp đồng API (cho frontend — xem `INTEGRATION.md`)

- **`POST /api/chat`** — `{message, stream}`. `stream:true` → SSE
  (`{delta}` chữ hiện dần → có thể `{reset}` khi lưới an toàn kích hoạt → `{done, text}`
  bản đầy đủ đã bỏ Markdown). **FE phải gửi cookie session** (`credentials:"include"`) và
  **xử lý `reset`** (xóa buffer đã render). Không stream → JSON `{reply}`.
- **`WS /ws/voice`** — voice online: client gửi mic PCM 16kHz; server trả bot PCM 24kHz +
  event JSON (`user_text`/`bot_text`/`tool`/`interrupt`). **FE phải xử lý `interrupt`** (dừng loa ngay).
- **`WS /ws/twilio`** — Twilio Media Stream (server-to-server, không phải FE).
- **`POST /api/call`** — `{phone}` → AI gọi đi qua Twilio (optional `[phone]`).

Câu trả lời chat được **strip Markdown** (`views._to_plain_text`) — khách muốn text thuần
như người nhắn tin, không có `**` `##`.

---

## 9. Bẫy đã đổ máu — ĐỪNG phá khi refactor

Các đoạn code trông "thừa" nhưng cố ý; comment trong file ghi rõ `# bẫy #N`:

- **Streaming câu-cụt / nuốt tool** (`orchestrator.ask_stream`): stream đôi khi trả câu cụt
  hoặc mất `thought_signature` → **rollback về non-stream** và phát `{reset}`. Giữ nguyên
  logic tách slot tool-call theo `id`/`index` và gộp `arguments`.
- **SSE trên ASGI** (`views._as_async_iterator`): generator đồng bộ phải bọc thành async
  iterator để stream thật; tạo session **trước** khi stream (Set-Cookie chốt lúc gửi headers).
- **Failover model, không chỉ retry** (`gateway.py`): spike 503 bám theo TỪNG model — đổi
  model mới thoát, nên có cả retry lẫn failover.
- **Voice: phiên Gemini chết giữa chừng → tự đóng WebSocket** (`consumers.py`,
  `twilio_consumer.py`), đừng bỏ mặc, nếu không FE treo cuộc gọi im lặng.
- **Cắt lịch sử tại ranh giới `user`** (`views._trim_history`) để không tách cặp
  assistant→tool (API sẽ lỗi nếu tool message mồ côi).

---

## 10. Thêm tính năng — công thức

- **Thêm một tool mới:** viết handler (thường ở `booking/service.py` hoặc module riêng),
  rồi `register(name, description_EN, parameters, handler, tags=[...])` trong `tools/*.py`.
  Nếu tool cần biết kênh gọi (chat/voice) → `wants_source=True`. Không cần sửa chỗ nào khác;
  chat và voice tự thấy.
- **Thêm cấu hình:** thêm một dòng vào `_SPEC` trong `conf.py` (kèm default + caster). Truy
  cập qua `conf.TÊN`. Nếu là path → xử lý trong `__getattr__` như `DOCS_DIR`.
- **Đổi nhân cách/luật riêng của khách:** sửa `settings.POPPY` (`TONE`, `CUSTOM_RULES`),
  **không sửa `prompts.py`** trừ khi đổi khung prompt chung.
- **Khách có hệ booking riêng:** hiện thực `BookingBackend`, khai `POPPY["BOOKING_BACKEND"]`.
  Guardrails tự áp — không đụng `service.py`.
- **Sửa kiến thức doanh nghiệp:** sửa `docs/*.md` rồi **chạy lại `python manage.py ingest`**.

---

## 11. Môi trường & lưu ý

- Python **≥ 3.12** (dùng `audioop` cho chuyển mã audio Twilio — module này bị bỏ ở 3.13+,
  cân nhắc khi nâng Python).
- Chạy **ASGI** (daphne) — cần cho SSE streaming và voice WS, không chạy WSGI thuần.
- DB demo là **SQLite** (`db.sqlite3`); khách production nên Postgres. `chroma_db/` là vector
  store đã build — có thể xóa và `ingest` lại.
- Repo này **không phải git repo**. Không có CI. Kiểm tra chất lượng = `manage.py check` +
  `manage.py test poppy_assistant`.
- Bí mật (Gemini/Twilio key) **không bao giờ log**; `conf.summary()` đã mask key.
