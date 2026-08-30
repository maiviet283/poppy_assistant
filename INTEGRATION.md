# INTEGRATION.md — Nối frontend của khách vào Poppy

Module chỉ làm BE. FE của khách (React/Vue/HTML gì cũng được) nói chuyện với module
qua hợp đồng API ổn định dưới đây. Xem `examples/poppy-embed-example.html` để có code
mẫu vanilla JS chạy được ngay (chat SSE + voice WS scaffold).

## 1. Chat — `POST /api/chat` (SSE streaming)

```
Request:  { "message": "mấy giờ mở cửa?", "stream": true }
Header:   Content-Type: application/json
Cookie:   PHẢI gửi kèm session  ->  fetch(..., { credentials: "include" })

Response: text/event-stream
  data: {"delta": "Tiệm "}          ← chữ hiện dần
  data: {"delta": "mở 9h-19h."}
  data: {"reset": true}             ← lưới an toàn câu-cụt: FE PHẢI xoá phần đã render
  data: {"done": true, "text": "..."}  ← bản đầy đủ (đã bỏ markdown) để chốt
```

FE **bắt buộc**:
1. Gửi cookie session (`credentials:"include"`) — lịch sử chat nằm trong session.
2. Xử lý event `reset` — xoá buffer đã hiện của lượt đó.

Không muốn stream? Bỏ `"stream": true` → trả JSON `{ "reply": "..." }`.

Ví dụ tối giản:
```js
const resp = await fetch(API_BASE + "/api/chat", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  credentials: "include",
  body: JSON.stringify({ message, stream: true }),
});
const reader = resp.body.getReader();
const dec = new TextDecoder(); let buf = "", acc = "";
while (true) {
  const { value, done } = await reader.read(); if (done) break;
  buf += dec.decode(value, { stream: true });
  let i; while ((i = buf.indexOf("\n\n")) !== -1) {
    const ev = JSON.parse(buf.slice(0, i).replace(/^data:\s?/, "")); buf = buf.slice(i + 2);
    if (ev.reset) { acc = ""; render(""); }
    if (ev.delta) { acc += ev.delta; render(acc); }
    if (ev.done)  { acc = ev.text ?? acc; render(acc); }
  }
}
```

## 2. Voice online — `WS /ws/voice`

```
Client → Server: audio mic PCM 16kHz (binary)
Server → Client: audio bot PCM 24kHz (binary) + event JSON:
  {"type":"user_text"|"bot_text","text":...}    transcript
  {"type":"tool","name":...,"args":...}          bot đang gọi tool
  {"type":"interrupt"}                           khách chen ngang -> FE DỪNG LOA NGAY
```

FE **bắt buộc** xử lý `interrupt` (dừng phát loa tức thì) — bỏ thì mic bị khoá bán
song công. Pipeline audio (mic PCM 16k lên, phát 24k xuống) tuỳ FE hiện thực; xem
TODO trong `examples/poppy-embed-example.html`.

## 3. Gọi vào số điện thoại — `POST /api/call` (optional [phone])

```
Request:  { "phone": "+61..." }
Response: { "ok": true, "sid": "..." }   |   { "ok": false, "error": "..." }
```

## 3b. Khách gọi ĐẾN — `POST /api/voice/incoming` (optional [phone])

Không phải endpoint cho FE: đây là webhook **Twilio** gọi khi có cuộc gọi đến số của
doanh nghiệp. Trong Twilio Console, phần *Voice → A call comes in* của số điện thoại,
đặt **Webhook / HTTP POST** trỏ tới `<PUBLIC_BASE_URL>/api/voice/incoming`.

Endpoint trả TwiML `<Connect><Stream>` nối audio cuộc gọi vào `wss://…/ws/twilio`, từ
đó dùng chung bộ não voice với `/ws/voice`. Mỗi request được kiểm chữ ký
`X-Twilio-Signature`; chữ ký dựng từ `PUBLIC_BASE_URL` nên **URL trong console phải
khớp đúng `PUBLIC_BASE_URL`**, sai là 403.

## 4. CORS / session (khi FE khác domain với API)

Cùng domain thì bỏ qua. Khác domain (vd FE ở `web.com`, API ở `api.web.com`):

```python
# settings.py của khách
INSTALLED_APPS += ["corsheaders"]                 # pip install django-cors-headers
MIDDLEWARE.insert(0, "corsheaders.middleware.CorsMiddleware")
CORS_ALLOWED_ORIGINS = ["https://web.com"]
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = ["https://web.com"]
SESSION_COOKIE_SAMESITE = "None"                  # cookie xuyên site
SESSION_COOKIE_SECURE = True                       # bắt buộc HTTPS
```

FE khi đó fetch với `credentials:"include"` (đã nêu ở §1). Đây là chỗ dễ vỡ nhất
khi nhúng — test kỹ việc giữ được cookie phiên qua nhiều lượt.

## 5. Chống lạm dụng (khuyến nghị)

`/api/chat` là endpoint công khai: nên thêm rate-limit theo IP/session và giới hạn
độ dài input. `/api/call` (gọi ĐI) nguy hiểm hơn — chỉ mở cho số đã xuất hiện trong
hội thoại đã xác minh + quota chặt/ngày.
