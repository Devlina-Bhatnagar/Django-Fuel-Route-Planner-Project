import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from routes.models import FuelStation


class Command(BaseCommand):
    help = "Import fuel price CSV into FuelStation table."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str)

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"])

        if not csv_path.exists():
            raise CommandError(f"CSV file not found: {csv_path}")

        required_columns = {
            "OPIS Truckstop ID",
            "Truckstop Name",
            "Address",
            "City",
            "State",
            "Rack ID",
            "Retail Price",
        }

        created = 0
        updated = 0
        skipped = 0

        with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            missing = required_columns - set(reader.fieldnames or [])

            if missing:
                raise CommandError(f"CSV is missing columns: {', '.join(sorted(missing))}")

            for row in reader:
                try:
                    price = Decimal(str(row["Retail Price"]).strip())
                except (InvalidOperation, TypeError):
                    skipped += 1
                    continue

                opis_id = str(row["OPIS Truckstop ID"]).strip()
                name = str(row["Truckstop Name"]).strip()
                address = str(row["Address"]).strip()
                city = str(row["City"]).strip()
                state = str(row["State"]).strip().upper()
                rack_id = str(row["Rack ID"]).strip()

                if not opis_id or not name or not city or not state:
                    skipped += 1
                    continue

                station, was_created = FuelStation.objects.update_or_create(
                    opis_truckstop_id=opis_id,
                    truckstop_name=name,
                    address=address,
                    city=city,
                    state=state,
                    rack_id=rack_id,
                    defaults={
                        "retail_price": price,
                    },
                )

                if was_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Import complete. created={created}, updated={updated}, skipped={skipped}"
            )
        )
