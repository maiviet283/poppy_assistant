from __future__ import annotations

from datetime import timedelta
from functools import lru_cache
from typing import Protocol

from django.db import transaction
from django.utils.module_loading import import_string

from poppy_assistant.models import Booking, Offering, Resource

# Phrases that mean "no preference", treated as no specific resource.
_ANY = {"", "any", "anyone", "any one", "no preference"}
_DEFAULT_DURATION = 45

# Booking fields needed to build a summary dict; used to keep queries lean.
_INFO_FIELDS = (
    "id",
    "customer_name",
    "offering",
    "resource",
    "appointment_time_text",
    "phone",
    "status",
)


def is_any_resource(name: str) -> bool:
    """Return True when the resource name means "no preference"."""
    return (name or "").strip().lower() in _ANY


def overlaps(s1, d1: int, s2, d2: int) -> bool:
    """Return True when intervals [s1, s1+d1) and [s2, s2+d2) overlap."""
    return s1 < s2 + timedelta(minutes=d2) and s2 < s1 + timedelta(minutes=d1)


class BookingBackend(Protocol):
    """Adapter contract for plugging Poppy into any booking data store."""

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
    """Default backend backed by the module's own ORM models.

    This backend only reads and writes data; the confirm-before-commit state
    machine lives in ``service.py`` and applies to every backend.
    """

    def offerings(self) -> list[dict]:
        """Return active offerings with price, duration and description."""
        return [
            {
                "name": o["name"],
                "price": float(o["price"]),
                "duration_minutes": o["duration_minutes"],
                "description": o["description"],
            }
            for o in Offering.objects.filter(is_active=True).values(
                "name", "price", "duration_minutes", "description"
            )
        ]

    def resources(self) -> list[dict]:
        """Return active resources with their specialty and type."""
        return [
            {"name": r["name"], "specialty": r["specialty"], "type": r["type_label"]}
            for r in Resource.objects.filter(is_active=True).values(
                "name", "specialty", "type_label"
            )
        ]

    def offering_duration(self, name: str) -> int:
        """Return an offering's duration in minutes, or a default if unknown."""
        duration = (
            Offering.objects.filter(name__iexact=(name or "").strip())
            .values_list("duration_minutes", flat=True)
            .first()
        )
        return duration if duration is not None else _DEFAULT_DURATION

    def _duration_map(self) -> dict[str, int]:
        """Return a lowercase-name -> duration map to avoid per-booking lookups."""
        return {
            name.strip().lower(): minutes
            for name, minutes in Offering.objects.values_list("name", "duration_minutes")
        }

    @staticmethod
    def _info(b: Booking) -> dict:
        """Serialise a booking to the summary dict used across the service layer."""
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
        """Base queryset of non-cancelled bookings."""
        return Booking.objects.exclude(status=Booking.Status.CANCELLED)

    def conflicts(self, start, duration: int, resource: str, exclude_id=None) -> list[dict]:
        """Return non-cancelled bookings for a resource that overlap the given slot."""
        if not start or is_any_resource(resource):
            return []
        qs = self._active().filter(
            start_time__isnull=False, resource__iexact=resource.strip()
        ).only(*_INFO_FIELDS, "start_time", "offering")
        if exclude_id is not None:
            qs = qs.exclude(id=exclude_id)

        durations = self._duration_map()
        hits = []
        for b in qs:
            other = durations.get((b.offering or "").strip().lower(), _DEFAULT_DURATION)
            if overlaps(start, duration, b.start_time, other):
                hits.append(self._info(b))
        return hits

    def find_duplicate(self, phone: str, start, time_text: str) -> dict | None:
        """Find an existing booking for the same phone at the same time, if any."""
        if not phone:
            return None
        qs = self._active().filter(phone=phone).only(*_INFO_FIELDS)
        b = (
            qs.filter(start_time=start).first()
            if start
            else qs.filter(appointment_time_text__iexact=time_text).first()
        )
        return self._info(b) if b else None

    def bookings_for(self, phone: str) -> list[dict]:
        """Return all non-cancelled bookings for a phone number."""
        return [
            self._info(b)
            for b in self._active().filter(phone=(phone or "").strip()).only(*_INFO_FIELDS)
        ]

    def get(self, phone: str, booking_id) -> dict | None:
        """Return a single non-cancelled booking by phone and id."""
        b = (
            self._active()
            .filter(phone=(phone or "").strip(), id=booking_id)
            .only(*_INFO_FIELDS)
            .first()
        )
        return self._info(b) if b else None

    def create(self, fields: dict, start, source: str) -> dict:
        """Insert a new booking inside a transaction."""
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
        """Apply changes to a booking under a row lock; return None if it's gone."""
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
        """Mark a booking cancelled under a row lock; return None if it's gone."""
        with transaction.atomic():
            b = Booking.objects.select_for_update().filter(id=booking_id).first()
            if b is None:
                return None
            b.status = Booking.Status.CANCELLED
            b.save()
        return self._info(b)


@lru_cache(maxsize=1)
def get_backend() -> BookingBackend:
    """Load the backend named by POPPY['BOOKING_BACKEND'] (cached)."""
    from poppy_assistant import conf

    return import_string(conf.BOOKING_BACKEND)()
