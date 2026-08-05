"""
models.py — Mô hình dữ liệu TỔNG QUÁT của Poppy (generalize từ demo tiệm nail).

Trừu tượng chung cho nhiều ngành (MODULE_PLAN §6, AI_PLATFORM §4.2):
  - Offering  : "dịch vụ gì"  — làm gel, khám tổng quát, bàn 4 người...
  - Resource  : "ai/cái gì phục vụ" — thợ, bác sĩ, bàn, phòng...
  - Booking   : lịch hẹn Poppy ghi vào (chat hoặc gọi điện).

Trụ #2 (namespace): mọi bảng đặt db_table = "poppy_*" để KHÔNG đụng bảng sẵn có
của khách (họ có thể đã có bảng ``booking`` / ``service`` riêng).

Booking lưu offering/resource dưới dạng TEXT (như demo) để logic guardrails đối
chiếu theo tên hoạt động độc lập với danh mục — khách sửa danh mục không làm hỏng
lịch cũ. Khách có hệ booking riêng thì viết Adapter (booking/backends.py), không
đụng các model này.
"""

from __future__ import annotations

from django.db import models


class Offering(models.Model):
    """Một dịch vụ/mặt hàng phục vụ (giá + thời lượng) — Poppy đọc để báo giá."""

    name = models.CharField("Tên dịch vụ", max_length=120, unique=True)
    price = models.DecimalField("Giá", max_digits=9, decimal_places=2)
    duration_minutes = models.PositiveIntegerField("Thời lượng (phút)", default=30)
    description = models.CharField("Mô tả ngắn", max_length=255, blank=True)
    is_active = models.BooleanField("Đang phục vụ", default=True)

    class Meta:
        db_table = "poppy_offering"
        ordering = ["name"]
        verbose_name = "Dịch vụ"
        verbose_name_plural = "Dịch vụ"

    def __str__(self) -> str:
        return f"{self.name} — {self.price}"


class Resource(models.Model):
    """Một nguồn lực phục vụ: thợ, bác sĩ, bàn, phòng..."""

    name = models.CharField("Tên", max_length=120, unique=True)
    type_label = models.CharField("Loại (thợ/bàn/bác sĩ...)", max_length=60, blank=True)
    specialty = models.CharField("Chuyên môn", max_length=255, blank=True)
    capacity = models.PositiveIntegerField("Sức chứa", default=1)
    is_active = models.BooleanField("Đang nhận khách", default=True)

    class Meta:
        db_table = "poppy_resource"
        ordering = ["name"]
        verbose_name = "Nguồn lực"
        verbose_name_plural = "Nguồn lực"

    def __str__(self) -> str:
        return self.name


class Booking(models.Model):
    """Lịch hẹn khách đặt qua Poppy (chat hoặc gọi điện)."""

    class Source(models.TextChoices):
        CHAT = "chat", "Chat"
        VOICE = "voice", "Gọi điện"

    class Status(models.TextChoices):
        NEW = "new", "Mới"
        CONFIRMED = "confirmed", "Đã xác nhận"
        DONE = "done", "Hoàn thành"
        CANCELLED = "cancelled", "Đã hủy"

    customer_name = models.CharField("Tên khách", max_length=120)
    phone = models.CharField("Số điện thoại", max_length=40, blank=True)
    # Lưu theo TÊN (text) — độc lập với danh mục Offering/Resource.
    offering = models.CharField("Dịch vụ", max_length=120, blank=True)
    resource = models.CharField("Nguồn lực yêu cầu", max_length=120, blank=True)
    # Nguyên văn thời gian khách nói (phòng khi không parse được ISO)
    appointment_time_text = models.CharField("Thời gian (khách nói)", max_length=120, blank=True)
    start_time = models.DateTimeField("Thời gian hẹn", null=True, blank=True)
    notes = models.TextField("Ghi chú", blank=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.CHAT)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "poppy_booking"
        ordering = ["-created_at"]
        verbose_name = "Lịch hẹn"
        verbose_name_plural = "Lịch hẹn"
        indexes = [models.Index(fields=["phone"]), models.Index(fields=["start_time"])]

    def __str__(self) -> str:
        when = self.appointment_time_text or (
            self.start_time.strftime("%H:%M %d/%m/%Y") if self.start_time else "?"
        )
        return f"{self.customer_name} — {self.offering or 'dịch vụ'} @ {when}"
