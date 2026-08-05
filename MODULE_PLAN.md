# MODULE_PLAN.md — Đóng gói Poppy thành reusable Django app (Cách A)

> Bản thiết kế thực thi để biến trợ lý AI của demo "Petal & Polish" thành **một
> Django app cắm được vào project Django sẵn có của khách** (Cách A: khách tự host,
> mỗi deploy phục vụ đúng 1 doanh nghiệp).
>
> Tài liệu chị em: `AI_PLATFORM_ARCHITECTURE.md` (bản multi-tenant do MÌNH host —
> Cách B). File này CỐ TÌNH khác nó: mượn **nguyên tắc kỹ thuật**, bỏ **hạ tầng
> multi-tenant**. Xem §1 để hiểu vì sao.

---

## 1. Quyết định kiến trúc (đọc trước, đừng bỏ qua)

**Cách A = thả module vào project của khách, khách tự chạy.** Mỗi deploy chỉ có
đúng 1 "tenant" = chính khách đó. Vì vậy:

| Của `AI_PLATFORM_ARCHITECTURE.md` | Cách A làm gì |
|---|---|
| Bảng `Tenant`, `tenant_id` trên mọi query, custom manager lọc tenant | **BỎ** — 1 deploy = 1 doanh nghiệp, không cần |
| BYOK + mã hóa envelope key | **BỎ** — key nằm trong settings của khách, họ tự giữ |
| Postgres + pgvector bắt buộc | **BỎ** — SQLite + Chroma của khách là đủ; khách nào có Postgres thì Django ORM tự chạy |
| Dashboard đa tenant, channel binding | **BỎ** |
| §2.2 Một lõi agent chung (chat + voice) | **GIỮ** — đã đúng ở demo |
| §2.3 Guardrails ở tầng TOOL, không phải prompt | **GIỮ** — đóng thành decorator |
| §5.4 Tool Registry (khai báo MỘT nơi) | **GIỮ** — xoá mùi "thêm tool sửa 3 file" |
| §4.2 Generalize Resource/Offering/Booking | **GIỮ** — module dùng được đa ngành |
| §2.4 Model-agnostic qua lớp OpenAI-compatible | **GIỮ** — gói thành `gateway.py` |
| §2.1 Config-as-data | **GIỮ** — nhưng là 1 khối config cho 1 doanh nghiệp, không phải bảng Tenant |
| §4.2 `transaction.atomic()` + unique constraint chống double-booking | **GIỮ + BỔ SUNG** (demo đang thiếu — race condition đã xác nhận) |

**Đường nâng cấp sau này:** nếu muốn nhảy sang Cách B (multi-tenant do mình host),
cấu trúc này KHÔNG phải đập đi — chỉ thêm cột `tenant_id` + manager lọc, đúng như
`AI_PLATFORM_ARCHITECTURE.md` §8 GĐ0. Thiết kế dưới đây giữ đường đó mở.

---

## 2. Nguyên tắc bất biến của module

1. **Cài bằng `pip`, KHÔNG copy thư mục.** Một nguồn sự thật, version hoá, fix một
   chỗ cập nhật mọi khách. Đây là thứ tách "reusable app" khỏi "chép file".
2. **Namespace tuyệt đối.** Cài module vào KHÔNG được đổi hành vi bất kỳ thứ gì
   sẵn có của khách (model, url, static, settings).
3. **Config-contract, fail loud.** Thiếu cấu hình bắt buộc → báo lỗi rõ ràng lúc
   khởi động, không chạy nửa vời.
4. **Zero side-effect lúc import.** Không chạm DB, không gọi mạng khi import app.
5. **Guardrails ở tầng tool.** Prompt có thể bị model phớt lờ; cửa chặn trong code
   thì không. Luật "không nói *đã đặt/đã hủy* trừ khi tool trả `ok=true`" là bất biến.
6. **Adapter seam.** Khách đã có hệ booking riêng → tool gọi qua interface, không
   ép khách đổi schema.
7. **Fail loud, degrade gracefully.** Key hết quota → báo chủ quán + trả lời tĩnh /
   handoff, KHÔNG chết im trước mặt khách của họ.

---

## 3. Bảy trụ "chuyên nghiệp" của một drop-in Django app

### Trụ 1 — Package cài bằng pip
```bash
pip install git+https://github.com/ban/poppy-assistant@v1.2.0
```
- `pyproject.toml` khai tên gói `poppy-assistant`, app label `poppy_assistant`.
- Fix bug → `v1.2.1` → khách `pip install -U poppy-assistant`. Hết cảnh phân kỳ.
- `extras`: `[voice]` (google-genai), `[phone]` (twilio) — khách không dùng thì
  khỏi cài.

### Trụ 2 — Namespace tuyệt đối (không đụng gì của khách)
- **Table prefix:** mọi model đặt `db_table = "poppy_*"` (KHÔNG để `booking`,
  `service` trần — sẽ đụng bảng của khách).
- **URL namespace:** `app_name = "poppy"`; khách
  `include("poppy_assistant.urls", namespace="poppy")`.
- **Settings 1 khối:** tất cả nằm trong dict `POPPY = {...}`, không rải biến global.
- **Static/JS mẫu:** dưới `static/poppy/`.
- **Session key riêng:** lịch sử chat lưu ở `request.session["poppy_chat_messages"]`
  (không phải `chat_messages` trần).

### Trụ 3 — Config-contract, validate khi khởi động
`AppConfig.ready()` kiểm `POPPY` đủ key bắt buộc chưa; thiếu → `ImproperlyConfigured`
với thông báo chỉ rõ cần thêm gì. Không đọc `.env` lén trong app (khác demo hiện tại).

### Trụ 4 — Zero side-effect lúc import
- Warmup RAG (nạp ONNX + mở Chroma) chạy **lazy, nền, nuốt lỗi** — thiếu index
  không được làm chết `manage.py` của khách.
- Không query DB / gọi mạng ở top-level module.

### Trụ 5 — Adapter seam cho khách đã có hệ booking
Interface chuẩn (xem §7). Mặc định dùng model của module; khách có hệ riêng
(model của họ, Google Calendar, KiotViet…) thì viết adapter, khai
`POPPY["BOOKING_BACKEND"] = "myapp.adapters.MyBackend"`. Tool KHÔNG biết dưới là
DB của ai.

### Trụ 6 — Migrations & tests đi kèm
- App ship migration riêng; table prefixed nên không clash.
- Guardrails có **unit test không tốn token** (logic thuần) chạy trong CI trước
  mỗi release.

### Trụ 7 — Public API + SemVer
- `__init__.py` phơi đúng thứ khách được dùng; `CHANGELOG.md`; version SemVer.
- Khách chỉ phụ thuộc 4 điểm nối: `urls`, `routing`, dict `POPPY`, management
  commands. Mọi thứ khác là nội bộ, đổi thoải mái.

---

## 4. Cấu trúc package

```
poppy-assistant/
  pyproject.toml            # tên gói, deps, extras [voice]/[phone], version
  README.md
  CHANGELOG.md
  INTEGRATION.md            # hợp đồng API cho FE của khách (§9)
  INSTALL.md                # 4 bước cài (§10)
  examples/
    poppy-embed-example.html   # template test API — đi kèm repo này
  poppy_assistant/
    __init__.py             # __version__, public API
    apps.py                 # AppConfig: validate config + warmup lazy
    conf.py                 # (mới) đọc & validate dict POPPY -> object cấu hình
    gateway.py              # (mới) LLM call + retry 503 + failover model
    orchestrator.py         # (đổi tên chatbot.py) ask()/ask_stream(), giữ bẫy #4
    prompts.py              # system prompt dựng từ business profile (config-as-data)
    rag.py                  # ChromaDB + embedding local ONNX (giữ nguyên)
    models.py               # Resource, Offering, Booking (db_table="poppy_*")
    admin.py                # đăng ký 3 model vào /admin/ của khách
    urls.py                 # /chat, /call  (app_name="poppy")
    routing.py              # websocket_urlpatterns: /ws/voice, /ws/twilio
    views.py                # chat_api (JSON/SSE), call_api
    consumers.py            # VoiceConsumer (online)
    twilio_consumer.py      # TwilioVoiceConsumer (gọi số ĐT) — optional [phone]
    telephony.py            # place_call qua Twilio REST — optional [phone]
    notify.py               # (đổi tên telegram_notify) báo nhân viên; pluggable
    booking/
      backends.py           # BookingBackend interface + DefaultBookingBackend
    tools/
      registry.py           # (mới) @register: schema + handler + mô tả EN — MỘT nơi
      booking_tools.py      # list_offerings/check_availability/find/create/update/cancel
      knowledge_tools.py    # search_knowledge (RAG as tool)
    guardrails.py           # (mới) decorator confirm-before-commit, idempotency
    management/commands/
      ingest.py             # build vector DB từ DOCS_DIR
      seed_business.py      # (đổi tên seed_salon) nạp Offering/Resource mẫu
    migrations/
    static/poppy/
      poppy-embed.js        # code mẫu vanilla JS nối API (giao khách)
    tests/
      test_guardrails.py    # không tốn token — logic thuần
      test_registry.py
```

Đổi tên so với demo: `chatbot.py→orchestrator.py`, `salon.py→tools/booking_tools.py`
+ `booking/backends.py`, `telegram_notify.py→notify.py`, `seed_salon→seed_business`.
Model `Service/Technician/Appointment → Offering/Resource/Booking`.

---

## 5. Config-contract: dict `POPPY`

Khách khai **một** dict trong `settings.py`. `conf.py` đọc, điền default, validate.

```python
POPPY = {
    # --- Bắt buộc ---
    "GEMINI_API_KEY": "...",              # thiếu -> ImproperlyConfigured lúc ready()
    "BUSINESS_NAME": "Tiệm nail X",       # chèn vào system prompt (config-as-data)

    # --- Model (có default an toàn; đổi phải test bằng key thật — bẫy #5/#11) ---
    "CHAT_MODEL": "gemini-3.1-flash-lite",
    "CHAT_MODEL_FALLBACK": "gemini-2.5-flash-lite",
    "VOICE_MODEL": "gemini-3.1-flash-live-preview",
    "GEMINI_BASE_URL": "https://generativelanguage.googleapis.com/v1beta/openai/",

    # --- Nhân cách & luật riêng (config-as-data, không sửa code) ---
    "ASSISTANT_NAME": "Poppy",
    "TONE": "thân thiện, ngắn gọn",
    "CUSTOM_RULES": "",                   # luật riêng chủ quán, chèn vào prompt
    "TIMEZONE": "Asia/Ho_Chi_Minh",

    # --- Tool bật/tắt (registry lọc theo đây) ---
    "ENABLED_TOOLS": ["booking", "faq"],  # bỏ "booking" -> bot chỉ FAQ, không ghi DB
    "MAX_TOOL_ROUNDS": 5,

    # --- RAG (đường dẫn GHI ĐƯỢC, không mặc định vào trong package) ---
    "DOCS_DIR": BASE_DIR / "poppy_docs",
    "CHROMA_DB_DIR": BASE_DIR / "poppy_chroma",
    "CHROMA_COLLECTION": "poppy_docs",
    "RAG_TOP_K": 4,

    # --- Adapter (mặc định dùng model của module) ---
    "BOOKING_BACKEND": "poppy_assistant.booking.backends.DefaultBookingBackend",

    # --- Thông báo nhân viên (để trống -> chế độ giả lập, in log) ---
    "TELEGRAM_BOT_TOKEN": "",
    "TELEGRAM_CHAT_ID": "",

    # --- Twilio (optional [phone]) ---
    "TWILIO_ACCOUNT_SID": "",
    "TWILIO_AUTH_TOKEN": "",
    "TWILIO_FROM_NUMBER": "",
    "PUBLIC_BASE_URL": "",
}
```

`conf.py` — quy tắc:
- Key bắt buộc: `GEMINI_API_KEY`, `BUSINESS_NAME`. Thiếu → fail loud.
- Mọi thứ khác có default. `TWILIO_*` đủ bộ mới bật `TWILIO_ENABLED`.
- Không đọc `os.environ` bên trong nghiệp vụ — chỉ `conf.py` được phép, và cũng chỉ
  như lớp fallback cho dev.

---

## 6. Mô hình dữ liệu (generalize, table-prefixed)

```
Offering   (db_table="poppy_offering")   # "dịch vụ gì": làm gel, khám tổng quát...
  name, price, duration_minutes, description, is_active

Resource   (db_table="poppy_resource")   # "ai/cái gì phục vụ": thợ, bàn, bác sĩ
  name, type_label, capacity(=1), specialty, is_active, work_hours(JSON)

Booking    (db_table="poppy_booking")    # lịch hẹn bot ghi vào
  customer_name, customer_phone
  offering (FK, null), resource (FK, null = "Any")
  offering_text, resource_text            # nguyên văn phòng khi không map được
  appointment_time_text, start_time(datetime)
  status(pending|confirmed|cancelled|completed|no_show)
  source(chat|voice), created_by(ai|human), notes, created_at
  Meta: UNIQUE (resource, start_time)     # chống double-booking Ở TẦNG DB
```

> Kiểm trống lịch = so overlap `start_time + duration` như demo, NHƯNG bọc trong
> `transaction.atomic()` + bắt `IntegrityError` từ unique constraint. Demo thiếu
> cái này — `AI_PLATFORM_ARCHITECTURE.md` §4.2 đã ghi race condition xác nhận.

Giữ tên hiển thị tiếng Việt trong `verbose_name` để /admin/ của khách dễ đọc.

---

## 7. Adapter seam — `BookingBackend`

```python
# poppy_assistant/booking/backends.py
class BookingBackend(Protocol):
    def list_offerings(self) -> list[dict]: ...
    def list_resources(self) -> list[dict]: ...
    def check_availability(self, *, offering, resource, start_time) -> dict: ...
    def create_booking(self, *, customer_name, phone, offering,
                       resource, start_time, source) -> dict: ...
    def update_booking(self, *, booking_id, **changes) -> dict: ...
    def cancel_booking(self, *, booking_id) -> dict: ...
    def find_bookings(self, *, phone) -> list[dict]: ...

class DefaultBookingBackend(BookingBackend):
    """Dùng model Offering/Resource/Booking của module (SQLite/Postgres khách)."""
```

- Tool trong `tools/booking_tools.py` gọi qua backend được nạp từ
  `POPPY["BOOKING_BACKEND"]` (import string) — KHÔNG import model trực tiếp.
- Khách đã có hệ riêng: viết `class MyBackend(BookingBackend)` trỏ vào model của
  họ / gọi API KiotViet / Google Calendar, khai vào config. Bot chạy y hệt.
- **Guardrails nằm ở tầng tool (trên backend), nên áp cho MỌI backend** — kể cả
  backend của khách cũng được bảo vệ confirm-before-commit + idempotency.

---

## 8. Tool Registry + Guardrails

**Registry (khai báo MỘT nơi):**
```python
# tools/registry.py
@register(name="create_booking", schema={...}, tags=["booking"])
@needs_confirmation                      # guardrails decorator
@idempotent(key=("phone", "start_time"))
def create_booking(args, ctx): ...
```
- Chat (`orchestrator.py`) và voice (`consumers.py`) **cùng đọc** registry, lọc
  theo `POPPY["ENABLED_TOOLS"]`. Thêm tool = thêm 1 hàm + `@register`, KHÔNG sửa
  4 chỗ như demo.
- Mô tả tool + giá trị tool trả về viết **TIẾNG ANH** (giữ bài học demo: text
  tiếng Việt trong tool ép model trả lời tiếng Việt với khách nói tiếng Anh).

**Guardrails (decorator, máy trạng thái từ demo):**
- thiếu trường → `need_more_info`
- chưa xác nhận → `needs_confirmation` (tóm tắt để khách gật)
- trùng khách + giờ → `already_booked` (idempotent — gật 2 lần vẫn 1 booking)
- trùng giờ khác nội dung → `use_update_instead` (ok=false)
- tài nguyên kín giờ → `resource_busy`
- chỉ khi `customer_confirmed=true` và qua hết cửa → ghi DB (trong transaction)
  + notify chủ quán.
- Prompt vẫn giữ luật cứng "không nói đã-đặt/sửa/hủy trừ khi tool trả `ok=true`"
  (2 lớp: prompt + guardrails code).

---

## 9. Hợp đồng API cho FE của khách (INTEGRATION.md)

Module chỉ làm BE; khách tự nối FE của họ vào contract ổn định sau:

### 9.1. Chat — `POST /api/chat` (SSE streaming)
```
Request:  { "message": "mấy giờ mở cửa?", "stream": true }
Header:   Content-Type: application/json
Cookie:   PHẢI gửi kèm session (fetch: credentials:"include")

Response: text/event-stream
  data: {"delta": "Tiệm "}          ← chữ hiện dần
  data: {"delta": "mở 9h-19h."}
  data: {"reset": true}             ← lưới an toàn câu-cụt: FE PHẢI xoá buffer đã render
  data: {"done": true, "text": "..."}  ← bản đầy đủ (đã bỏ markdown) để chốt
```
FE bắt buộc: (a) gửi cookie session (history nằm trong session — bẫy #1/#3);
(b) xử lý event `reset` (bỏ phần nháp cụt — bẫy #4b).

Không `stream` → trả JSON `{ "reply": "..." }` như thường (fallback đơn giản).

### 9.2. Voice online — `WS /ws/voice`
```
Client → Server: audio mic PCM 16kHz (binary)
Server → Client: audio bot PCM 24kHz (binary) + event JSON:
  {"type":"transcript", ...}
  {"type":"interrupt"}    ← khách chen ngang: FE PHẢI dừng loa NGAY
```
FE bắt buộc xử lý `interrupt` (bẫy #10) — bỏ thì mic khoá bán song công.

### 9.3. Gọi vào số ĐT — `POST /api/call` (optional [phone])
```
Request:  { "phone": "+61..." }
Response: { "ok": true, "sid": "..." }
```

### 9.4. CORS / session (nếu FE khác domain API)
- Bật `django-cors-headers`: `CORS_ALLOWED_ORIGINS=[FE origin]`, `CORS_ALLOW_CREDENTIALS=True`.
- Cookie session: `SESSION_COOKIE_SAMESITE="None"`, `SESSION_COOKIE_SECURE=True` (bắt buộc HTTPS).
- `CSRF_TRUSTED_ORIGINS` thêm origin FE. `/api/chat` đang `csrf_exempt` nên chat OK;
  cân nhắc rate-limit theo IP/session (chống abuse endpoint công khai).

---

## 10. Khách cài như thế nào (INSTALL.md)

```bash
pip install "git+https://github.com/ban/poppy-assistant@v1.2.0"
# hoặc kèm voice/phone:
pip install "poppy-assistant[voice,phone] @ git+...@v1.2.0"
```
```python
# settings.py
INSTALLED_APPS += ["daphne", "channels", "poppy_assistant"]
ASGI_APPLICATION = "config.asgi.application"   # khách đã chạy ASGI
POPPY = { "GEMINI_API_KEY": "...", "BUSINESS_NAME": "Tiệm X",
          "DOCS_DIR": BASE_DIR/"poppy_docs", "CHROMA_DB_DIR": BASE_DIR/"poppy_chroma",
          "ENABLED_TOOLS": ["booking", "faq"] }
```
```python
# urls.py
path("api/", include("poppy_assistant.urls", namespace="poppy")),
```
```python
# asgi.py — ghép websocket của module vào ProtocolTypeRouter của khách
from channels.routing import ProtocolTypeRouter, URLRouter
from poppy_assistant.routing import websocket_urlpatterns
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": URLRouter(websocket_urlpatterns),  # + route WS sẵn có của khách
})
```
```bash
python manage.py migrate
python manage.py seed_business      # nạp Offering/Resource mẫu (idempotent)
# bỏ file .md tài liệu tiệm vào POPPY["DOCS_DIR"], rồi:
python manage.py ingest             # build vector DB (chạy lại khi sửa docs)
```
FE: đọc `INTEGRATION.md` (§9) + dán `static/poppy/poppy-embed.js` (hoặc dùng
`examples/poppy-embed-example.html` để test trước).

---

## 11. Thứ tự thi công

**GĐ0 — Tách & đặt khung package (không đổi hành vi).**
Tạo `pyproject.toml`, đổi app label `poppy_assistant`, thêm `conf.py` validate
`POPPY`, gỡ `load_dotenv` khỏi app. Verify: `manage.py check` sạch trong 1 project
Django trắng chỉ cài module.

**GĐ1 — Config-as-data + namespace.**
Model đổi tên + `db_table="poppy_*"` + migration mới; session key riêng; URL
namespace; prompt dựng từ `BUSINESS_NAME`/`TONE`/`CUSTOM_RULES`. Verify: guardrails
unit test (không tốn token), đặt lịch qua `manage.py shell`.

**GĐ2 — Tool registry + guardrails decorator + adapter seam.**
Chuyển tool sang registry, guardrails thành decorator, thêm `BookingBackend`.
Bọc `create_booking` trong `transaction.atomic()` + unique constraint. Verify:
test registry lọc theo `ENABLED_TOOLS`; test double-booking bị chặn.

**GĐ3 — LLM gateway + fail loud.**
Gói `_create_with_retry` thành `gateway.py`: retry 503 → failover model (bẫy #5).
Key hỏng → degrade gracefully (trả lời tĩnh + notify), không chết im.

**GĐ4 — Đóng gói & docs.**
`INSTALL.md`, `INTEGRATION.md`, `CHANGELOG.md`, extras `[voice]/[phone]`, static
`poppy-embed.js`, ví dụ `examples/`. Đóng tag `v1.0.0`.

Voice (`consumers.py`/`twilio_consumer.py`) port sau cùng — cô lập trong extras,
giữ bài học bẫy #10 (dòng "live", phiên chết tự đóng WS, FE xử lý `interrupt`).

---

## 12. Checklist đóng gói & bàn giao

- [ ] Cài vào 1 project Django **trắng** (chỉ có module) → `manage.py check` sạch,
      `migrate` tạo bảng `poppy_*`, không đụng bảng nào khác.
- [ ] Thiếu `POPPY["GEMINI_API_KEY"]` → báo lỗi rõ ràng lúc khởi động (fail loud).
- [ ] Import `poppy_assistant` KHÔNG chạm DB / mạng (zero side-effect).
- [ ] Guardrails unit test xanh (không tốn token). Double-booking bị chặn ở DB.
- [ ] Chat qua **streaming + cookie**: hỏi giờ mở cửa (RAG), hỏi giá (tool), đặt
      lịch đủ luồng → **có row trong `poppy_booking`**. Nói "yes" 2 lần → vẫn 1 row.
- [ ] Đổi `POPPY["BUSINESS_NAME"]` → bot tự xưng đúng tên, KHÔNG sửa code.
- [ ] `ENABLED_TOOLS=["faq"]` (bỏ booking) → bot không ghi DB, chỉ trả lời FAQ.
- [ ] Adapter: trỏ `BOOKING_BACKEND` sang backend giả → tool chạy qua backend đó.
- [ ] `examples/poppy-embed-example.html` nối được API thật, thấy chữ hiện dần +
      xử lý `reset`.
- [ ] (nếu bật) `/ws/voice` mở phiên Live; FE nhận `interrupt`.
- [ ] `/admin/` của khách thấy Offering/Resource/Booking.

---

## 13. Bài học từ demo phải mang theo (đã đổ máu — đừng học lại)

1. Verify qua ĐÚNG đường UI dùng: chat là **SSE + cookie session**, không tin đường JSON.
2. ASGI gom iterator đồng bộ → stream phải bọc async iterator; `session.create()`
   TRƯỚC khi trả streaming response, save session thủ công trong generator.
3. Streaming + function calling: tách slot tool call theo id/name (không theo index);
   lưới an toàn câu-cụt-nuốt-tool; giữ mọi trường lạ provider (vd `thought_signature`).
4. 503 bám theo TỪNG model → failover **đổi model**, không chỉ retry.
5. Đổi model phải test bằng **key thật** — key mới không gọi được model đời cũ,
   danh sách `/models` không đáng tin.
6. Voice: dòng "live" ổn định tool > "native-audio" giọng hay nhưng tool sập;
   phiên chết tự đóng WS; FE xử lý `interrupt`.
7. Debug bot = đọc hộp đen tool_calls/tool_results trong history, không nghe bot kể.
8. Console Windows cp1252 — ép UTF-8 (`asgi.py`, `manage.py`) nếu dev trên Windows.
9. Test nghiệp vụ thuần (guardrails) không tốn token — unit test hết.
10. Trả lời của bot là TEXT THUẦN — giữ 2 lớp: luật prompt + bộ lọc `_to_plain_text`.

---

*File này là bản gốc thực thi cho Cách A. Cập nhật nó mỗi khi quyết định kiến trúc
module thay đổi. Bản multi-tenant (Cách B) xem `AI_PLATFORM_ARCHITECTURE.md`.*
