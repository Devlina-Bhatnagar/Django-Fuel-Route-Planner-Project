from django.contrib import admin

from .models import FuelStation


@admin.register(FuelStation)
class FuelStationAdmin(admin.ModelAdmin):
    list_display = (
        "truckstop_name",
        "city",
        "state",
        "retail_price",
        "geocoding_status",
        "latitude",
        "longitude",
    )
    list_filter = ("state", "geocoding_status")
    search_fields = ("truckstop_name", "address", "city", "state", "opis_truckstop_id")
