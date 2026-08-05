"""
test_guardrails.py — Test nghiệp vụ THUẦN LOGIC, KHÔNG tốn token (bài học demo #9).

Dùng một backend giả (không đụng DB) để kiểm máy trạng thái confirm-before-commit:
thiếu trường -> need_more_info; chưa xác nhận -> needs_confirmation; trùng ->
already_booked (idempotent). Chạy: ``python manage.py test poppy_assistant``.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from poppy_assistant import guardrails
from poppy_assistant.booking import service


class GuardrailHelpersTests(SimpleTestCase):
    def test_is_true(self):
        self.assertTrue(guardrails.is_true(True))
        self.assertTrue(guardrails.is_true("true"))
        self.assertTrue(guardrails.is_true("YES"))
        self.assertFalse(guardrails.is_true(False))
        self.assertFalse(guardrails.is_true("nope"))
        self.assertFalse(guardrails.is_true(""))

    def test_missing_fields(self):
        required = [("name", "the name"), ("phone", "a phone")]
        self.assertEqual(guardrails.missing_fields({"name": "", "phone": ""}, required),
                         ["the name", "a phone"])
        self.assertEqual(guardrails.missing_fields({"name": "Mai", "phone": "0900"}, required), [])


class _FakeBackend:
    """Backend giả trong RAM — đủ cho create_booking chạy qua các cửa guardrails."""

    def __init__(self, dup=None):
        self._dup = dup
        self.created = []

    def offering_duration(self, name):
        return 45

    def find_duplicate(self, phone, start, time_text):
        return self._dup

    def conflicts(self, start, duration, resource, exclude_id=None):
        return []

    def create(self, fields, start, source):
        info = {"id": 1, "name": fields["customer_name"], "offering": fields["offering"],
                "resource": fields["resource"], "time": fields["appointment_time"],
                "phone": fields["phone"], "status": "new"}
        self.created.append(info)
        return info


class CreateBookingGateTests(SimpleTestCase):
    def setUp(self):
        self._orig_backend = service.get_backend
        self._orig_notify = service.notify_staff
        service.notify_staff = lambda *a, **k: {"ok": True}

    def tearDown(self):
        service.get_backend = self._orig_backend
        service.notify_staff = self._orig_notify

    def _use(self, backend):
        service.get_backend = lambda: backend

    def test_need_more_info_when_missing(self):
        self._use(_FakeBackend())
        r = service.create_booking(customer_name="Mai", phone="", offering="", resource="", appointment_time="")
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "need_more_info")

    def test_needs_confirmation_before_commit(self):
        self._use(_FakeBackend())
        r = service.create_booking(
            customer_name="Mai", phone="0900", offering="Gel Manicure",
            resource="Any", appointment_time="2026-08-10T14:00", customer_confirmed=False,
        )
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "needs_confirmation")

    def test_idempotent_already_booked(self):
        dup = {"id": 7, "name": "Mai", "offering": "Gel Manicure", "resource": "Any",
               "time": "2026-08-10T14:00", "phone": "0900", "status": "new"}
        fake = _FakeBackend(dup=dup)
        self._use(fake)
        r = service.create_booking(
            customer_name="Mai", phone="0900", offering="Gel Manicure",
            resource="Any", appointment_time="2026-08-10T14:00", customer_confirmed=True,
        )
        self.assertTrue(r["ok"])
        self.assertEqual(r["status"], "already_booked")
        self.assertEqual(fake.created, [])  # KHÔNG tạo bản trùng

    def test_commit_when_confirmed_and_unique(self):
        fake = _FakeBackend()
        self._use(fake)
        r = service.create_booking(
            customer_name="Mai", phone="0900", offering="Gel Manicure",
            resource="Any", appointment_time="2026-08-10T14:00", customer_confirmed=True,
        )
        self.assertTrue(r["ok"])
        self.assertEqual(r["status"], "booked")
        self.assertEqual(len(fake.created), 1)
