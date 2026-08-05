"""admin.py — Đăng ký Offering/Resource/Booking vào /admin/ của khách."""

from django.contrib import admin

from poppy_assistant.models import Booking, Offering, Resource


@admin.register(Offering)
class OfferingAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "duration_minutes", "is_active")
    list_editable = ("price", "duration_minutes", "is_active")
    search_fields = ("name",)


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ("name", "type_label", "specialty", "is_active")
    list_editable = ("is_active",)
    search_fields = ("name", "specialty")


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "customer_name",
        "offering",
        "resource",
        "appointment_time_text",
        "phone",
        "source",
        "status",
        "created_at",
    )
    list_filter = ("status", "source", "created_at")
    search_fields = ("customer_name", "phone", "offering", "resource")
    list_editable = ("status",)
    readonly_fields = ("created_at",)
