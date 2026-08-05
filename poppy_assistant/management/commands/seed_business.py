from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand

from poppy_assistant.models import Offering, Resource

OFFERINGS = [
    ("Classic Manicure", "25.00", 30, "Shape, cuticle care, and a polish of your choice."),
    ("Gel Manicure", "40.00", 45, "Long-lasting gel color with two-week chip-free wear."),
    ("Classic Pedicure", "35.00", 45, "Soak, scrub, and polish for happy feet."),
    ("Gel Pedicure", "50.00", 60, "Spa pedicure finished with durable gel color."),
    ("Press-On Application", "30.00", 30, "Custom-fit press-on set applied in minutes."),
    ("Nail Art (per nail)", "5.00", 10, "Hand-painted designs, from minimal to bold."),
    ("Soak-Off / Removal", "15.00", 20, "Gentle gel or press-on removal."),
]

RESOURCES = [
    ("Mai", "technician", "Gel & intricate nail art"),
    ("Linh", "technician", "Spa pedicures & nail care"),
    ("Ngoc", "technician", "Press-ons & quick sets"),
    ("Trang", "technician", "Classic mani/pedi & natural nails"),
]


class Command(BaseCommand):
    help = "Seed sample offerings and resources."

    def handle(self, *args, **options) -> None:
        """Insert the sample catalogue idempotently via get_or_create."""
        for name, price, minutes, desc in OFFERINGS:
            _, created = Offering.objects.get_or_create(
                name=name,
                defaults={"price": Decimal(price), "duration_minutes": minutes, "description": desc},
            )
            self.stdout.write(("+ " if created else "= ") + f"Offering: {name}")

        for name, type_label, specialty in RESOURCES:
            _, created = Resource.objects.get_or_create(
                name=name, defaults={"type_label": type_label, "specialty": specialty}
            )
            self.stdout.write(("+ " if created else "= ") + f"Resource: {name}")

        self.stdout.write(self.style.SUCCESS("\nSample data seeded."))
