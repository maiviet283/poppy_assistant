"""
booking_tools.py — Đăng ký bộ tool đặt lịch vào registry (tag "booking").

Chỉ KHAI BÁO (schema + trỏ handler sang booking/service.py). Guardrails nằm ở
service; ở đây không có luật nghiệp vụ. Import module này là tự đăng ký.
"""

from __future__ import annotations

from poppy_assistant.booking import service
from poppy_assistant.tools.registry import register

register(
    name="list_offerings",
    description=(
        "Get the business's services/offerings with prices and durations. Use when the "
        "customer asks about services, the price list, or what's offered."
    ),
    parameters={"type": "object", "properties": {}},
    handler=lambda **_: service.list_offerings(),
    tags=["booking"],
)

register(
    name="list_resources",
    description=(
        "Get the people/resources that serve customers (e.g. technicians, doctors, tables) "
        "and their specialties. Use when the customer asks who/what can serve them or wants "
        "to pick one."
    ),
    parameters={"type": "object", "properties": {}},
    handler=lambda **_: service.list_resources(),
    tags=["booking"],
)

register(
    name="check_availability",
    description=(
        "Check whether a time slot is open. If a resource is given, tells whether that "
        "resource is free at that time; otherwise lists which resources are free/busy then. "
        "Use for 'is Linh free on Saturday at 1pm?' or 'who's available then?', and before "
        "booking when the customer picked a specific resource."
    ),
    parameters={
        "type": "object",
        "properties": {
            "appointment_time": {
                "type": "string",
                "description": "The date/time to check, ISO 8601 if possible (e.g. 2026-07-04T13:00).",
            },
            "resource": {
                "type": "string",
                "description": "A specific resource/person to check, or leave empty to check everyone.",
            },
            "offering": {
                "type": "string",
                "description": "The service (optional) — used to estimate how long the slot needs.",
            },
        },
        "required": ["appointment_time"],
    },
    handler=lambda **kw: service.check_availability(**kw),
    tags=["booking"],
)

register(
    name="find_bookings",
    description=(
        "Look up existing appointments by phone number. Use when a customer asks whether "
        "they already have a booking, or before making a new one / changing one."
    ),
    parameters={
        "type": "object",
        "properties": {"phone": {"type": "string", "description": "The customer's phone number."}},
        "required": ["phone"],
    },
    handler=lambda **kw: service.find_bookings(**kw),
    tags=["booking"],
)

register(
    name="create_booking",
    description=(
        "Reserve an appointment and SAVE it. Requires ALL of: customer_name, phone, "
        "offering (the service), resource (the person/thing, or 'Any'), and a specific "
        "appointment_time. Ask for whatever is missing first. Before saving you MUST show "
        "the customer a full summary and get explicit agreement; only then call this with "
        "customer_confirmed=true. If anything is missing or unconfirmed it will tell you "
        "what to do and will NOT save."
    ),
    parameters={
        "type": "object",
        "properties": {
            "customer_name": {"type": "string", "description": "The customer's name."},
            "phone": {"type": "string", "description": "The customer's contact phone number (required)."},
            "offering": {"type": "string", "description": "The service they want (e.g. Gel Manicure)."},
            "resource": {"type": "string", "description": "The resource/person chosen, or 'Any' if no preference."},
            "appointment_time": {
                "type": "string",
                "description": (
                    "A specific date/time. Prefer ISO 8601 (e.g. 2026-07-05T14:00); never "
                    "invent one — if the customer hasn't given a specific time, ask for it."
                ),
            },
            "customer_confirmed": {
                "type": "boolean",
                "description": "Set true ONLY after showing the full summary and the customer agreed.",
            },
            "notes": {"type": "string", "description": "Any extra notes."},
        },
        "required": ["customer_name", "phone", "offering", "resource", "appointment_time"],
    },
    handler=service.create_booking,
    tags=["booking"],
    wants_source=True,
)

register(
    name="update_booking",
    description=(
        "Change an EXISTING booking (resource, time, offering, or name). Find it by phone "
        "(plus booking_id when several exist). Only pass the fields that should change. You "
        "MUST confirm with the customer first, then call with customer_confirmed=true. NEVER "
        "tell the customer a booking was changed unless this returned ok=true."
    ),
    parameters={
        "type": "object",
        "properties": {
            "phone": {"type": "string", "description": "Phone number the booking was made with."},
            "booking_id": {"type": "integer", "description": "Booking id — only if the phone has several bookings."},
            "new_resource": {"type": "string", "description": "New resource/person, if changing."},
            "new_time": {"type": "string", "description": "New date/time (ISO 8601 preferred), if changing."},
            "new_offering": {"type": "string", "description": "New service, if changing."},
            "new_name": {"type": "string", "description": "Corrected customer name, if changing."},
            "customer_confirmed": {"type": "boolean", "description": "True ONLY after the customer agreed to the change."},
        },
        "required": ["phone"],
    },
    handler=lambda **kw: service.update_booking(**kw),
    tags=["booking"],
)

register(
    name="cancel_booking",
    description=(
        "Cancel an EXISTING booking, found by phone (plus booking_id if several). Confirm "
        "with the customer first, then call with customer_confirmed=true. NEVER say a booking "
        "was cancelled unless this returned ok=true."
    ),
    parameters={
        "type": "object",
        "properties": {
            "phone": {"type": "string", "description": "Phone number the booking was made with."},
            "booking_id": {"type": "integer", "description": "Booking id — only if the phone has several bookings."},
            "customer_confirmed": {"type": "boolean", "description": "True ONLY after the customer agreed to cancel."},
        },
        "required": ["phone"],
    },
    handler=lambda **kw: service.cancel_booking(**kw),
    tags=["booking"],
)
