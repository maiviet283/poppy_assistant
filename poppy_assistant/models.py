from __future__ import annotations

from django.db import models


class Offering(models.Model):
    """A bookable service or item with a price and duration."""

    name = models.CharField("Name", max_length=120, unique=True)
    price = models.DecimalField("Price", max_digits=9, decimal_places=2)
    duration_minutes = models.PositiveIntegerField("Duration (minutes)", default=30)
    description = models.CharField("Description", max_length=255, blank=True)
    is_active = models.BooleanField("Active", default=True)

    class Meta:
        db_table = "poppy_offering"
        ordering = ["name"]
        verbose_name = "Offering"
        verbose_name_plural = "Offerings"

    def __str__(self) -> str:
        return f"{self.name} — {self.price}"


class Resource(models.Model):
    """A person or thing that serves customers (technician, doctor, table, room)."""

    name = models.CharField("Name", max_length=120, unique=True)
    type_label = models.CharField("Type", max_length=60, blank=True)
    specialty = models.CharField("Specialty", max_length=255, blank=True)
    capacity = models.PositiveIntegerField("Capacity", default=1)
    is_active = models.BooleanField("Active", default=True)

    class Meta:
        db_table = "poppy_resource"
        ordering = ["name"]
        verbose_name = "Resource"
        verbose_name_plural = "Resources"

    def __str__(self) -> str:
        return self.name


class Booking(models.Model):
    """An appointment created through Poppy over chat or a phone call.

    Offering and resource are stored as free text rather than foreign keys so that
    existing bookings are unaffected when the catalogue changes.
    """

    class Source(models.TextChoices):
        CHAT = "chat", "Chat"
        VOICE = "voice", "Voice"

    class Status(models.TextChoices):
        NEW = "new", "New"
        CONFIRMED = "confirmed", "Confirmed"
        DONE = "done", "Done"
        CANCELLED = "cancelled", "Cancelled"

    customer_name = models.CharField("Customer name", max_length=120)
    phone = models.CharField("Phone", max_length=40, blank=True)
    offering = models.CharField("Offering", max_length=120, blank=True)
    resource = models.CharField("Requested resource", max_length=120, blank=True)
    # The customer's original wording, kept in case it can't be parsed to a datetime.
    appointment_time_text = models.CharField("Appointment time (as said)", max_length=120, blank=True)
    start_time = models.DateTimeField("Start time", null=True, blank=True)
    notes = models.TextField("Notes", blank=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.CHAT)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "poppy_booking"
        ordering = ["-created_at"]
        verbose_name = "Booking"
        verbose_name_plural = "Bookings"
        indexes = [models.Index(fields=["phone"]), models.Index(fields=["start_time"])]

    def __str__(self) -> str:
        when = self.appointment_time_text or (
            self.start_time.strftime("%H:%M %d/%m/%Y") if self.start_time else "?"
        )
        return f"{self.customer_name} — {self.offering or 'service'} @ {when}"
