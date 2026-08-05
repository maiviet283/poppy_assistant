"""
backends.py — Adapter seam cho nghiệp vụ đặt lịch (Trụ #5, MODULE_PLAN §7).

``BookingBackend`` là INTERFACE các thao tác dữ liệu thuần (đọc/ghi lịch, dò trùng,
dò chồng giờ). ``DefaultBookingBackend`` hiện thực trên model Offering/Resource/
Booking của module.

Khách đã có hệ booking riêng (model của họ, Google Calendar, KiotViet...) thì viết
``class MyBackend(BookingBackend)`` trỏ vào hệ đó rồi khai
``POPPY["BOOKING_BACKEND"] = "myapp.backends.MyBackend"``. Guardrails
(booking/service.py) nằm TRÊN backend nên áp cho MỌI backend — kể cả của khách.

Backend KHÔNG chứa luật confirm-before-commit; nó chỉ trả dữ liệu. Máy trạng thái
xác nhận/tóm tắt nằm ở service.py.
"""

from __future__ import annotations

from datetime import timedelta
from functools import lru_cache
from typing import Protocol

from django.db import transaction
from django.utils.module_loading import import_string

from poppy_assistant.models import Booking, Offering, Resource

# Các cách khách nói "ai/cái nào cũng được" -> coi như không chỉ định nguồn lực.
_ANY = {"", "any", "anyone", "any one", "no preference", "bất kỳ", "bat ky"}
_DEFAULT_DURATION = 45


def is_any_resource(name: str) -> bool:
    return (name or "").strip().lower() in _ANY


def overlaps(s1, d1: int, s2, d2: int) -> bool:
    """Hai khoảng [s1, s1+d1) và [s2, s2+d2) có chồng nhau không."""
    return s1 < s2 + timedelta(minutes=d2) and s2 < s1 + timedelta(minutes=d1)


class BookingBackend(Protocol):
    """Hợp đồng adapter — hiện thực để cắm Poppy vào hệ dữ liệu bất kỳ."""

    def offerings(self) -> list[dict]: ...
    def resources(self) -> list[dict]: ...
    def offering_duration(self, name: str) -> int: ...
    def conflicts(self, start, duration: int, resource: str, exclude_id=None) -> list[dict]: ...
    def find_duplicate(self, phone: str, start, time_text: str) -> dict | None: ...
    def bookings_for(self, phone: str) -> list[dict]: ...
    def get(self, phone: str, booking_id) -> dict | None: ...
    def create(self, fields: dict, start, source: str) -> dict: ...
    def update(self, booking_id, changes: dict) -> dict | None: ...
    def cancel(self, booking_id) -> dict | None: ...


class DefaultBookingBackend:
    """Hiện thực mặc định trên ORM của module (SQLite/Postgres của khách)."""

    # --- Đọc danh mục ---
    def offerings(self) -> list[dict]:
        return [
            {
                "name": o.name,
                "price": float(o.price),
                "duration_minutes": o.duration_minutes,
                "description": o.description,
            }
            for o in Offering.objects.filter(is_active=True)
        ]

    def resources(self) -> list[dict]:
        return [
            {"name": r.name, "specialty": r.specialty, "type": r.type_label}
            for r in Resource.objects.filter(is_active=True)
        ]

    def offering_duration(self, name: str) -> int:
        o = Offering.objects.filter(name__iexact=(name or "").strip()).first()
        return o.duration_minutes if o else _DEFAULT_DURATION

    # --- Truy vấn cho guardrails ---
    def _info(self, b: Booking) -> dict:
        return {
            "id": b.id,
            "name": b.customer_name,
            "offering": b.offering,
            "resource": b.resource,
            "time": b.appointment_time_text,
            "phone": b.phone,
            "status": b.status,
        }

    def _active(self):
        return Booking.objects.exclude(status=Booking.Status.CANCELLED)

    def conflicts(self, start, duration: int, resource: str, exclude_id=None) -> list[dict]:
        if not start or is_any_resource(resource):
            return []
        qs = self._active().filter(start_time__isnull=False, resource__iexact=resource.strip())
        if exclude_id is not None:
            qs = qs.exclude(id=exclude_id)
        return [
            self._info(b)
            for b in qs
            if overlaps(start, duration, b.start_time, self.offering_duration(b.offering))
        ]

    def find_duplicate(self, phone: str, start, time_text: str) -> dict | None:
        if not phone:
            return None
        qs = self._active().filter(phone=phone)
        b = qs.filter(start_time=start).first() if start else qs.filter(
            appointment_time_text__iexact=time_text
        ).first()
        return self._info(b) if b else None

    def bookings_for(self, phone: str) -> list[dict]:
        return [self._info(b) for b in self._active().filter(phone=(phone or "").strip())]

    def get(self, phone: str, booking_id) -> dict | None:
        b = self._active().filter(phone=(phone or "").strip(), id=booking_id).first()
        return self._info(b) if b else None

    # --- Ghi (bọc transaction — nền tảng cho chống double-booking) ---
    def create(self, fields: dict, start, source: str) -> dict:
        with transaction.atomic():
            b = Booking.objects.create(
                customer_name=fields["customer_name"],
                phone=fields["phone"],
                offering=fields["offering"],
                resource=fields["resource"],
                appointment_time_text=fields["appointment_time"],
                start_time=start,
                notes=(fields.get("notes") or "").strip(),
                source=source if source in dict(Booking.Source.choices) else "chat",
            )
        return self._info(b)

    def update(self, booking_id, changes: dict) -> dict | None:
        with transaction.atomic():
            b = Booking.objects.select_for_update().filter(id=booking_id).first()
            if b is None:
                return None
            if changes.get("resource"):
                b.resource = changes["resource"]
            if changes.get("time"):
                b.appointment_time_text = changes["time"]
                b.start_time = changes.get("start_time")
            if changes.get("offering"):
                b.offering = changes["offering"]
            if changes.get("name"):
                b.customer_name = changes["name"]
            b.save()
        return self._info(b)

    def cancel(self, booking_id) -> dict | None:
        with transaction.atomic():
            b = Booking.objects.select_for_update().filter(id=booking_id).first()
            if b is None:
                return None
            b.status = Booking.Status.CANCELLED
            b.save()
        return self._info(b)


@lru_cache(maxsize=1)
def get_backend() -> BookingBackend:
    """Nạp backend theo POPPY['BOOKING_BACKEND'] (mặc định DefaultBookingBackend)."""
    from poppy_assistant import conf

    return import_string(conf.BOOKING_BACKEND)()
