# Generated for the fuel route planner assessment project.

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="FuelStation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("opis_truckstop_id", models.CharField(db_index=True, max_length=50)),
                ("truckstop_name", models.CharField(max_length=255)),
                ("address", models.CharField(blank=True, max_length=255)),
                ("city", models.CharField(max_length=120)),
                ("state", models.CharField(db_index=True, max_length=2)),
                ("rack_id", models.CharField(blank=True, max_length=50)),
                ("retail_price", models.DecimalField(decimal_places=4, max_digits=8)),
                ("latitude", models.FloatField(blank=True, db_index=True, null=True)),
                ("longitude", models.FloatField(blank=True, db_index=True, null=True)),
                ("geocoded_address", models.TextField(blank=True)),
                ("geocoding_status", models.CharField(choices=[("pending", "Pending"), ("success", "Success"), ("failed", "Failed")], db_index=True, default="pending", max_length=30)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddIndex(
            model_name="fuelstation",
            index=models.Index(fields=["state", "city"], name="routes_fuel_state_6d6fc4_idx"),
        ),
        migrations.AddIndex(
            model_name="fuelstation",
            index=models.Index(fields=["latitude", "longitude"], name="routes_fuel_latitud_3e4cb6_idx"),
        ),
        migrations.AddIndex(
            model_name="fuelstation",
            index=models.Index(fields=["retail_price"], name="routes_fuel_retail__1a2444_idx"),
        ),
    ]
