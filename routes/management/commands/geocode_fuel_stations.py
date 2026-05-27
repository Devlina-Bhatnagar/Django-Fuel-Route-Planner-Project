import time

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from routes.models import FuelStation


class Command(BaseCommand):
    help = "Geocode fuel stations once and store coordinates in the database."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument("--sleep", type=float, default=1.1)
        parser.add_argument(
            "--retry-failed",
            action="store_true",
            help="Retry stations previously marked as failed.",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        sleep_seconds = options["sleep"]
        retry_failed = options["retry_failed"]

        statuses = ["pending"]
        if retry_failed:
            statuses.append("failed")

        queryset = FuelStation.objects.filter(
            geocoding_status__in=statuses,
            latitude__isnull=True,
            longitude__isnull=True,
        ).order_by("state", "city", "truckstop_name")

        if limit:
            queryset = queryset[:limit]

        headers = {"User-Agent": settings.NOMINATIM_USER_AGENT}

        success = 0
        failed = 0

        for station in queryset:
            query = f"{station.address}, {station.city}, {station.state}, USA"

            params = {
                "q": query,
                "format": "jsonv2",
                "limit": 1,
                "countrycodes": "us",
                "addressdetails": 1,
            }

            try:
                response = requests.get(
                    f"{settings.NOMINATIM_BASE_URL}/search",
                    params=params,
                    headers=headers,
                    timeout=20,
                )

                if response.status_code != 200:
                    raise RuntimeError(
                        f"HTTP {response.status_code}: {response.text[:200]}"
                    )

                results = response.json()
                if not results:
                    # Fall back to city/state when exact street address is not found.
                    params["q"] = f"{station.city}, {station.state}, USA"
                    response = requests.get(
                        f"{settings.NOMINATIM_BASE_URL}/search",
                        params=params,
                        headers=headers,
                        timeout=20,
                    )
                    results = response.json()

                if not results:
                    station.geocoding_status = "failed"
                    station.save(update_fields=["geocoding_status", "updated_at"])
                    failed += 1
                    self.stdout.write(self.style.WARNING(f"FAILED: {query}"))
                else:
                    result = results[0]
                    station.latitude = float(result["lat"])
                    station.longitude = float(result["lon"])
                    station.geocoded_address = result.get("display_name", "")
                    station.geocoding_status = "success"
                    station.save(
                        update_fields=[
                            "latitude",
                            "longitude",
                            "geocoded_address",
                            "geocoding_status",
                            "updated_at",
                        ]
                    )
                    success += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"OK: {station.truckstop_name} -> "
                            f"{station.latitude}, {station.longitude}"
                        )
                    )

            except Exception as exc:
                station.geocoding_status = "failed"
                station.save(update_fields=["geocoding_status", "updated_at"])
                failed += 1
                self.stdout.write(self.style.ERROR(f"ERROR: {query}: {exc}"))

            time.sleep(sleep_seconds)

        self.stdout.write(
            self.style.SUCCESS(f"Geocoding complete. success={success}, failed={failed}")
        )
