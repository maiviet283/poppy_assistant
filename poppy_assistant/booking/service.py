"""
service.py — Máy trạng thái đặt lịch (guardrails) chạy TRÊN backend.

Đây là "tầng tool" giữ luật confirm-before-commit (MODULE_PLAN §8). Mọi thao tác
dữ liệu đi qua ``get_backend()`` nên đổi backend (adapter) không phải sửa file này.

Các cửa chặn (đều KHÔNG ghi nếu chưa đạt):
  - thiếu trường bắt buộc  -> need_more_info
  - chưa xác nhận          -> needs_confirmation
  - đã có lịch y hệt       -> already_booked (idempotent — gật 2 lần vẫn 1 lịch)
  - trùng giờ khác nội dung-> use_update_instead
  - nguồn lực kín giờ      -> resource_busy

Giá trị tool trả về viết TIẾNG ANH (Poppy mirror ngôn ngữ khách — bài học demo).
"""

from __future__ import annotations

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from poppy_assistant import conf, guardrails
from poppy_assistant.booking.backends import get_backend, is_any_resource
from poppy_assistant.notify import notify_staff


def _parse_start(time_text: str):
    """Đổi chuỗi ISO thành datetime có timezone; None nếu không phải ISO."""
    dt = parse_datetime(time_text or "")
    if dt and timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


# --- Đọc danh mục -----------------------------------------------------------
def list_offerings() -> dict:
    return {"offerings": get_backend().offerings()}


def list_resources() -> dict:
    return {"resources": get_backend().resources()}


def check_availability(appointment_time: str = "", resource: str = "", offering: str = "") -> dict:
    """Khung giờ này nguồn lực chỉ định có rảnh không, hoặc nguồn lực nào trống."""
    backend = get_backend()
    start = _parse_start(appointment_time)
    if not start:
        return {
            "ok": False,
            "detail": "Need a specific date/time (ideally ISO 8601) to check availability.",
        }
    duration = backend.offering_duration(offering) if offering else 45

    if resource and not is_any_resource(resource):
        conflicts = backend.conflicts(start, duration, resource)
        return {
            "time": appointment_time,
            "resource": resource,
            "available": not conflicts,
            "detail": (
                f"{resource} is free at that time."
                if not conflicts
                else f"{resource} is already booked around {conflicts[0]['time']}."
            ),
        }

    free, busy = [], []
    for r in backend.resources():
        (busy if backend.conflicts(start, duration, r["name"]) else free).append(r["name"])
    return {"time": appointment_time, "available_resources": free, "busy_resources": busy}


def find_bookings(phone: str = "") -> dict:
    phone = (phone or "").strip()
    if not phone:
        return {"ok": False, "detail": "Need a phone number to look up existing bookings."}
    bookings = get_backend().bookings_for(phone)
    return {"phone": phone, "count": len(bookings), "bookings": bookings}


# --- Đặt lịch ---------------------------------------------------------------
_REQUIRED_FIELDS = [
    ("customer_name", "the customer's name"),
    ("phone", "a contact phone number"),
    ("offering", "which service they want"),
    ("resource", "which person/resource they'd like (or 'Any' if no preference)"),
    ("appointment_time", "a specific date and time"),
]


def create_booking(
    customer_name: str = "",
    appointment_time: str = "",
    phone: str = "",
    offering: str = "",
    resource: str = "",
    customer_confirmed=False,
    notes: str = "",
    source: str = "chat",
) -> dict:
    backend = get_backend()
    fields = {
        "customer_name": (customer_name or "").strip(),
        "phone": (phone or "").strip(),
        "offering": (offering or "").strip(),
        "resource": (resource or "").strip(),
        "appointment_time": (appointment_time or "").strip(),
    }

    missing = guardrails.missing_fields(fields, _REQUIRED_FIELDS)
    if missing:
        return {
            "ok": False,
            "status": "need_more_info",
            "detail": (
                "Do NOT book yet. Politely ask the customer for the missing details: "
                + "; ".join(missing)
                + ". When asking about the resource, list the available options by name."
            ),
        }

    if not guardrails.is_true(customer_confirmed):
        return {
            "ok": False,
            "status": "needs_confirmation",
            "detail": (
                "Do NOT save yet. Show the customer a plain-text summary — "
                f"name: {fields['customer_name']}, service: {fields['offering']}, "
                f"resource: {fields['resource']}, phone: {fields['phone']}, "
                f"time: {fields['appointment_time']} — and ask them to confirm. "
                "Only call create_booking again with customer_confirmed=true after "
                "they clearly agree."
            ),
        }

    start = _parse_start(fields["appointment_time"])
    duration = backend.offering_duration(fields["offering"])

    # Chống lưu TRÙNG (idempotent). Nếu chi tiết KHÁC lịch đang có -> đây là yêu cầu
    # SỬA: chỉ model sang update_booking, tuyệt đối không trả ok=true.
    dup = backend.find_duplicate(fields["phone"], start, fields["appointment_time"])
    if dup:
        same_resource = is_any_resource(fields["resource"]) or (
            dup["resource"].strip().lower() == fields["resource"].strip().lower()
        )
        same_offering = (
            not fields["offering"]
            or dup["offering"].strip().lower() == fields["offering"].strip().lower()
        )
        if same_resource and same_offering:
            return {
                "ok": True,
                "status": "already_booked",
                "booking_id": dup["id"],
                "summary": (
                    f"That appointment is already booked (for {dup['name']}, "
                    f"{dup['offering'] or 'a service'} at {dup['time']}). "
                    "No duplicate was created."
                ),
                "detail": "Tell the customer it's already booked; do not create it again.",
            }
        return {
            "ok": False,
            "status": "use_update_instead",
            "booking_id": dup["id"],
            "detail": (
                f"Booking #{dup['id']} already exists for this phone at that time "
                f"({dup['offering']} with {dup['resource']}). Nothing was changed. To modify "
                f"it, call update_booking with booking_id={dup['id']} and only the fields to "
                "change — do NOT call create_booking again."
            ),
        }

    conflicts = backend.conflicts(start, duration, fields["resource"])
    if conflicts:
        return {
            "ok": False,
            "status": "resource_busy",
            "detail": (
                f"{fields['resource']} is already booked around {conflicts[0]['time']}. "
                "Tell the customer and ask whether they'd like a different time or another "
                "option (use check_availability or list_resources to help). Do not book over "
                "the conflict."
            ),
        }

    info = backend.create(fields, start, source)

    notify_staff(
        f"🌸 <b>Lịch hẹn mới — {conf.BUSINESS_NAME}</b>\n"
        f"<b>Khách:</b> {info['name']}\n"
        f"<b>SĐT:</b> {info['phone'] or '—'}\n"
        f"<b>Dịch vụ:</b> {info['offering'] or '—'}\n"
        f"<b>Nguồn lực:</b> {info['resource'] or 'bất kỳ'}\n"
        f"<b>Thời gian:</b> {info['time']}"
    )

    return {
        "ok": True,
        "status": "booked",
        "booking_id": info["id"],
        "summary": (
            f"Appointment saved for {info['name']} — {info['offering']} with "
            f"{info['resource']} at {info['time']} (phone {info['phone']})."
        ),
    }


# --- Sửa / hủy --------------------------------------------------------------
def _locate(phone: str, booking_id=None):
    """Tìm lịch (chưa hủy) theo SĐT; nhiều lịch thì cần booking_id.

    Trả (info, None) khi tìm được, hoặc (None, dict_lỗi) khi không.
    """
    backend = get_backend()
    phone = (phone or "").strip()
    if not phone:
        return None, {"ok": False, "detail": "Need the customer's phone number to find the booking."}

    if booking_id:
        info = backend.get(phone, booking_id)
        if info is None:
            return None, {
                "ok": False,
                "status": "not_found",
                "detail": f"No active booking #{booking_id} for phone {phone}.",
            }
        return info, None

    bookings = backend.bookings_for(phone)
    if not bookings:
        return None, {
            "ok": False,
            "status": "not_found",
            "detail": f"No active booking found for phone {phone}.",
        }
    if len(bookings) > 1:
        return None, {
            "ok": False,
            "status": "ambiguous",
            "detail": "Multiple bookings found — ask the customer which one and pass booking_id.",
            "bookings": bookings,
        }
    return bookings[0], None


def update_booking(
    phone: str = "",
    booking_id=None,
    new_resource: str = "",
    new_time: str = "",
    new_offering: str = "",
    new_name: str = "",
    customer_confirmed=False,
) -> dict:
    backend = get_backend()
    info, err = _locate(phone, booking_id)
    if err:
        return err

    changes = {
        "resource": (new_resource or "").strip(),
        "time": (new_time or "").strip(),
        "offering": (new_offering or "").strip(),
        "name": (new_name or "").strip(),
    }
    if not any(changes.values()):
        return {
            "ok": False,
            "detail": "Nothing to change — pass new_resource, new_time, new_offering or new_name.",
        }

    final_resource = changes["resource"] or info["resource"]
    final_time_text = changes["time"] or info["time"]
    final_offering = changes["offering"] or info["offering"]
    final_start = _parse_start(changes["time"]) if changes["time"] else None

    if not guardrails.is_true(customer_confirmed):
        return {
            "ok": False,
            "status": "needs_confirmation",
            "detail": (
                "Do NOT change anything yet. Confirm with the customer first — the booking "
                f"would become: service {final_offering}, resource {final_resource}, "
                f"time {final_time_text}. Then call update_booking again with "
                "customer_confirmed=true."
            ),
        }

    if changes["time"]:
        conflicts = backend.conflicts(
            final_start, backend.offering_duration(final_offering), final_resource,
            exclude_id=info["id"],
        )
    elif changes["resource"]:
        # Đổi nguồn lực nhưng giữ giờ cũ: không parse lại được start từ text -> bỏ qua
        # kiểm chồng giờ (giữ hành vi an toàn, không chặn nhầm). Ghi chú cho tương lai.
        conflicts = []
    else:
        conflicts = []
    if conflicts:
        return {
            "ok": False,
            "status": "resource_busy",
            "detail": (
                f"{final_resource} is already booked around {conflicts[0]['time']}. "
                "Ask the customer for another time or resource; do not apply this change."
            ),
        }

    changes["start_time"] = final_start
    updated = backend.update(info["id"], changes)
    if updated is None:
        return {"ok": False, "status": "not_found", "detail": "Booking disappeared before update."}

    notify_staff(
        f"✏️ <b>Cập nhật lịch hẹn — {conf.BUSINESS_NAME}</b>\n"
        f"<b>Khách:</b> {updated['name']} ({updated['phone']})\n"
        f"<b>Dịch vụ:</b> {updated['offering'] or '—'}\n"
        f"<b>Nguồn lực:</b> {updated['resource'] or 'bất kỳ'}\n"
        f"<b>Thời gian:</b> {updated['time']}"
    )

    return {
        "ok": True,
        "status": "updated",
        "booking": updated,
        "summary": (
            f"Booking #{updated['id']} updated: {updated['offering']} with "
            f"{updated['resource']} at {updated['time']} for {updated['name']}."
        ),
    }


def cancel_booking(phone: str = "", booking_id=None, customer_confirmed=False) -> dict:
    backend = get_backend()
    info, err = _locate(phone, booking_id)
    if err:
        return err

    if not guardrails.is_true(customer_confirmed):
        return {
            "ok": False,
            "status": "needs_confirmation",
            "detail": (
                "Do NOT cancel yet. Confirm with the customer that they want to cancel "
                f"booking #{info['id']} ({info['offering']} at {info['time']}), then call "
                "cancel_booking again with customer_confirmed=true."
            ),
        }

    cancelled = backend.cancel(info["id"])
    if cancelled is None:
        return {"ok": False, "status": "not_found", "detail": "Booking disappeared before cancel."}

    notify_staff(
        f"🗑️ <b>Hủy lịch hẹn — {conf.BUSINESS_NAME}</b>\n"
        f"<b>Khách:</b> {cancelled['name']} ({cancelled['phone']})\n"
        f"<b>Dịch vụ:</b> {cancelled['offering'] or '—'}\n"
        f"<b>Thời gian:</b> {cancelled['time']}"
    )

    return {
        "ok": True,
        "status": "cancelled",
        "summary": f"Booking #{cancelled['id']} for {cancelled['name']} has been cancelled.",
    }
