# CHANGELOG

Theo SemVer. Khách chỉ phụ thuộc public API (urls, routing, dict POPPY, management
commands) — mọi thứ khác là nội bộ.

## 1.0.0 — Module hoá từ demo "Petal & Polish" (Cách A)

### Thêm
- Đóng gói thành Django app `poppy_assistant` cài được qua pip (`pyproject.toml`,
  extras `[voice]` / `[phone]`).
- **Config-contract** `settings.POPPY` (`conf.py`) — bỏ đọc `.env`/BASE_DIR cứng;
  fail loud khi thiếu `BUSINESS_NAME`, cảnh báo khi thiếu `GEMINI_API_KEY`.
- **Namespace**: bảng `poppy_offering/poppy_resource/poppy_booking`, URL namespace
  `poppy`, session key `poppy_chat_messages`, static `static/poppy/`.
- **Generalize domain**: `Service→Offering`, `Technician→Resource`,
  `Appointment→Booking` (dùng đa ngành).
- **Tool Registry** (`tools/registry.py`): khai báo tool MỘT nơi; chat (schema
  OpenAI) và voice (google-genai) cùng đọc; lọc theo `POPPY["ENABLED_TOOLS"]`.
- **Adapter seam** `BookingBackend` (`booking/backends.py`) — cắm vào hệ booking
  sẵn có của khách qua `POPPY["BOOKING_BACKEND"]`.
- **LLM Gateway** (`gateway.py`): retry 503 + failover model, tách khỏi orchestrator.
- **Guardrails** (`guardrails.py` + `booking/service.py`) giữ nguyên máy trạng thái
  confirm-before-commit + idempotency; unit test không tốn token (`tests/`).
- `ingest` bỏ nghỉ-giữa-lô (embedding local không có quota); `seed_business` thay
  `seed_salon`.
- Prompt (chat + voice) dựng từ business profile (config-as-data).
- Project host demo (`config/`) + trang test `examples/poppy-embed-example.html`
  phục vụ same-origin (né lỗi cookie khi mở file://).

### Giữ nguyên (bài học demo — không học lại)
- Lưới an toàn streaming (tách slot tool theo id/name; câu-cụt-nuốt-tool → non-stream;
  giữ `thought_signature`), session tạo trước khi stream, ép UTF-8 console Windows,
  voice dùng dòng "live" + tự đóng WS khi phiên chết + FE xử lý `interrupt`.

### Hạn chế đã biết / việc tiếp theo
- **Chống double-booking** hiện ở TẦNG APP (kiểm chồng giờ, bọc `transaction.atomic`).
  Ràng buộc UNIQUE ở TẦNG DB cần model resource dạng FK (hiện resource lưu text +
  "Any") — để lại cho bản sau khi cần chịu tải ghi đồng thời cao.
- `update_booking` khi chỉ đổi nguồn lực (giữ giờ text cũ) bỏ qua kiểm chồng giờ
  (không parse lại được start từ text) — an toàn, không chặn nhầm; cân nhắc lưu
  `start_time` chuẩn hoá để kiểm đầy đủ.
- Guardrails hiện là helper + máy trạng thái trong service (chưa phải decorator
  thuần) — đủ "guardrails ở tầng tool"; gói thành decorator là bước làm đẹp sau.
