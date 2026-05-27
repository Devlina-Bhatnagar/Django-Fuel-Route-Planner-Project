# Fuel Route Planner Django Project - Architecture, Code, Algorithm, API, and CSV Analysis

This document summarizes the complete Django API implementation for the backend assessment. The downloadable project folder contains the same source files.

## 1. Assignment Coverage

- Accepts start and finish locations within the USA.
- Returns a route map as GeoJSON.
- Uses the uploaded fuel-price CSV.
- Assumes 500-mile maximum vehicle range by default.
- Assumes 10 MPG by default.
- Calculates total fuel cost.
- Uses a free routing API with only one route call per request.
- Keeps fuel station geocoding out of the request path for speed.

## 2. Full Project Architecture

```text
fuel_route_planner/
  manage.py
  requirements.txt
  .env.example
  README.md
  data/
    fuel-prices-for-be-assessment.csv
  fuel_route_planner/
    __init__.py
    settings.py
    urls.py
    asgi.py
    wsgi.py
  routes/
    __init__.py
    apps.py
    models.py
    admin.py
    urls.py
    views.py
    services/
      __init__.py
      geo.py
      geocoding.py
      routing.py
      fuel_optimizer.py
    management/commands/
      __init__.py
      import_fuel_prices.py
      geocode_fuel_stations.py
    migrations/
      __init__.py
      0001_initial.py
```

## 3. Component Responsibilities

| Component | Responsibility |
|---|---|
| `routes/views.py` | Validates request body, calls geocoding, routing, and fuel optimizer, returns JSON. |
| `routes/services/geocoding.py` | Geocodes start and finish locations using Nominatim. |
| `routes/services/routing.py` | Calls OSRM once to get route distance, duration, and GeoJSON coordinates. |
| `routes/services/geo.py` | Haversine distance, route cumulative mile calculation, route sampling, bounding box calculation. |
| `routes/services/fuel_optimizer.py` | Finds candidate stations near the route and chooses the lowest-cost reachable fuel plan. |
| `routes/models.py` | Stores fuel station records, prices, and cached coordinates. |
| `import_fuel_prices.py` | Loads CSV data into the database. |
| `geocode_fuel_stations.py` | One-time station geocoding command. |

## 4. API Design

### Health Check
```http
GET /api/health/
```
Response:
```json
{ "status": "ok" }
```

### Plan Route
```http
POST /api/routes/plan/
Content-Type: application/json
```
Request body:
```json
{
  "start": "Chicago, IL",
  "finish": "Atlanta, GA",
  "max_range_miles": 500,
  "initial_range_miles": 500,
  "mpg": 10,
  "corridor_miles": 25
}
```

Required fields: `start`, `finish`. Optional fields: `max_range_miles`, `initial_range_miles`, `mpg`, `corridor_miles`.

Response shape:
```json
{
  "start": { "query": "Chicago, IL", "lat": 41.8755, "lon": -87.6244, "display_name": "..." },
  "finish": { "query": "Atlanta, GA", "lat": 33.7490, "lon": -84.3902, "display_name": "..." },
  "route": { "distance_miles": 716.43, "duration_hours": 11.59 },
  "fuel_plan": {
    "total_fuel_cost": 68.91,
    "currency": "USD",
    "mpg": 10.0,
    "max_range_miles": 500.0,
    "initial_range_miles": 500.0,
    "corridor_miles": 25.0,
    "total_gallons_purchased": 22.72,
    "fuel_stops": []
  },
  "map": { "type": "FeatureCollection", "features": [] },
  "api_call_counts": { "geocoding_calls": 2, "routing_calls": 1 }
}
```

HTTP status behavior:
| Status | Meaning |
|---|---|
| `200` | Route and fuel plan generated. |
| `400` | Invalid JSON, missing fields, bad numeric values, or geocoding failure. |
| `422` | Fuel optimization cannot find a valid reachable plan. |
| `502` | Routing provider failed. |

## 5. Fuel Optimization Algorithm Explanation

1. Geocode `start` and `finish`.
2. Call OSRM once to get the driving route with full GeoJSON route coordinates.
3. Compute cumulative mile markers along the route.
4. Sample the route every few miles to avoid expensive point-to-line checks against every route vertex.
5. Query only pre-geocoded fuel stations inside a broad route bounding box.
6. For each station, find the nearest sampled route point. If it is within `corridor_miles`, keep it as a candidate.
7. Assign every candidate station a `route_mile`, meaning where it approximately lies along the trip.
8. Compact near-duplicate station buckets by keeping cheaper stations around the same route mile.
9. Build a graph of nodes: `start`, candidate stations, and `finish`.
10. Add an edge from node A to node B if the route-mile distance is reachable within the tank range.
11. Edge cost is `(leg_distance / mpg) * current_station_price`. The first leg from start uses the initial tank, so it costs `0`.
12. Run dynamic programming over sorted route-mile nodes to find the minimum total cost path to the destination.
13. Reconstruct the path and return selected fuel stops, gallons, cost per stop, and total cost.

Why this is fast: station coordinates are cached, route API is called once, stations are prefiltered by bounding box, candidate stations are compacted before dynamic programming, and route distance checks are approximate using route samples.

## 6. CSV Analysis

- Total rows: **8,151**

- Total columns: **7**

- Unique OPIS Truckstop IDs: **6,738**

- Unique truckstop names: **6,550**

- Unique state/province codes: **57**

- Unique city/state pairs: **3,898**

- Retail price min: **$2.6873**

- Retail price max: **$6.3990**

- Retail price average: **$3.4990**

- Retail price median: **$3.4323**

- Missing values by column: `{'OPIS Truckstop ID': 0, 'Truckstop Name': 0, 'Address': 0, 'City': 0, 'State': 0, 'Rack ID': 0, 'Retail Price': 0}`


### Cheapest average state/province codes, minimum 20 records

| State   |   Records |   Avg_Price |   Min_Price |   Max_Price |
|:--------|----------:|------------:|------------:|------------:|
| TX      |  790.0000 |      3.1286 |      2.6873 |      4.2490 |
| OK      |  182.0000 |      3.1733 |      2.8590 |      3.7990 |
| MS      |  141.0000 |      3.2061 |      2.7840 |      4.0990 |
| MO      |  250.0000 |      3.2137 |      2.8990 |      3.7890 |
| SC      |  182.0000 |      3.2354 |      2.8990 |      3.9990 |
| SD      |   62.0000 |      3.2443 |      2.9390 |      3.9990 |
| TN      |  162.0000 |      3.2468 |      2.7857 |      3.8990 |
| LA      |  196.0000 |      3.2584 |      2.7990 |      3.9990 |
| NE      |  111.0000 |      3.2733 |      2.7990 |      3.6990 |
| AR      |  125.0000 |      3.3224 |      2.9990 |      4.1323 |


### Most expensive average state/province codes, minimum 20 records

| State   |   Records |   Avg_Price |   Min_Price |   Max_Price |
|:--------|----------:|------------:|------------:|------------:|
| BC      |  121.0000 |      4.7464 |      4.0094 |      5.1884 |
| SK      |   36.0000 |      4.7290 |      4.5076 |      4.9093 |
| AB      |  180.0000 |      4.3344 |      3.5636 |      5.0210 |
| MB      |   42.0000 |      4.2986 |      3.5610 |      4.6302 |
| WA      |   97.0000 |      4.0871 |      3.4090 |      4.5990 |
| CT      |   27.0000 |      4.0159 |      3.3990 |      5.1990 |
| ON      |  217.0000 |      3.9825 |      3.2269 |      5.3001 |
| PA      |  217.0000 |      3.8909 |      3.2590 |      5.4990 |
| ME      |   30.0000 |      3.8670 |      3.5023 |      4.0990 |
| NY      |  158.0000 |      3.8252 |      2.8990 |      4.6590 |


### Cheapest individual stations

|   OPIS Truckstop ID | Truckstop Name      | Address        | City    | State   |   Retail Price |
|--------------------:|:--------------------|:---------------|:--------|:--------|---------------:|
|               66341 | 7-ELEVEN #218       | I-44, EXIT 4   | Harrold | TX      |         2.6873 |
|               71079 | DK                  | SR-375         | El Paso | TX      |         2.6990 |
|               64422 | Chevron             | I-10, EXIT 858 | Vidor   | TX      |         2.7490 |
|               63669 | One9 #1248          | I-45, EXIT 271 | Wilmer  | TX      |         2.7557 |
|               66689 | ROSCOE TRAVEL PLAZA | I-20, EXIT 235 | Roscoe  | TX      |         2.7590 |


### Most expensive individual stations

|   OPIS Truckstop ID | Truckstop Name          | Address       | City        | State   |   Retail Price |
|--------------------:|:------------------------|:--------------|:------------|:--------|---------------:|
|               72368 | CHEVRON #352416         | I-8 Exit 73   | Jacumba     | CA      |         6.3990 |
|               70300 | PILOT #1194             | I-10 & US-60  | Phoenix     | AZ      |         6.0390 |
|               70300 | PILOT DEALER #1194      | I-10 & US-60  | Phoenix     | AZ      |         6.0390 |
|               72124 | GET GO #3016            | I-376 & SR-18 | Monaca      | PA      |         5.4990 |
|               67027 | FLYING J FUEL STOP #806 | HWY 11        | Kapuskasing | ON      |         5.3001 |


CSV observations:
- The CSV has no latitude/longitude columns, so the project uses one-time geocoding and caches coordinates.
- There are duplicate OPIS IDs and duplicate names, so the import key includes OPIS ID, name, address, city, state, and rack ID.
- Some codes are Canadian provinces. Since the assignment route inputs are USA-only, the endpoint geocodes start/finish locations with `countrycodes=us`; station records outside the USA will generally not match USA routes.

## 7. Setup Instructions

```bash
cd fuel_route_planner_clean
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py import_fuel_prices data/fuel-prices-for-be-assessment.csv
python manage.py geocode_fuel_stations --limit 200 --sleep 1.1
python manage.py runserver
```

## 8. Complete Django Code

### `manage.py`

```python
#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fuel_route_planner.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

```

### `requirements.txt`

```text
Django==6.0.5
requests==2.32.4
python-dotenv==1.1.1

```

### `.env.example`

```text
DEBUG=True
SECRET_KEY=change-me-for-local-development
ALLOWED_HOSTS=127.0.0.1,localhost
OSRM_BASE_URL=https://router.project-osrm.org
NOMINATIM_BASE_URL=https://nominatim.openstreetmap.org
NOMINATIM_USER_AGENT=fuel-route-planner-demo/1.0 your-email@example.com

```

### `README.md`

```markdown
# Fuel Route Planner API

Django API for the Spotter backend assessment.

## What it does

- Accepts a start and finish location inside the USA.
- Geocodes those locations.
- Calls OSRM once to fetch the driving route.
- Finds fuel stations from the provided CSV that are close to the route.
- Uses a 500-mile max vehicle range and 10 MPG default.
- Returns:
  - route summary,
  - route GeoJSON map,
  - recommended fuel stops,
  - total fuel cost after trip start,
  - assumptions and API call counts.

## Important assumption

The route request assumes the vehicle starts with a full tank by default, so the first 500 miles are already covered and are not included in the fuel cost. The returned `total_fuel_cost` is the amount spent on fuel stops after the trip begins.

You can change this through the request body using:

```json
{
  "initial_range_miles": 0
}
```

For `initial_range_miles = 0`, you must have a geocoded station close to mile 0 of the route.

## Why station geocoding is a separate command

The provided fuel-price CSV contains station address, city, state, and price, but no latitude/longitude. The API must be fast, so station coordinates are not geocoded during every route request. Instead:

1. Import the CSV once.
2. Geocode stations once and cache coordinates in the database.
3. The API request only calls:
   - Nominatim for start/finish geocoding.
   - OSRM once for the route.

For a real production version, replace public Nominatim with a paid/geocoding provider or preloaded geocoded station dataset.

## Setup

```bash
cd fuel_route_planner

python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env

python manage.py migrate
```

## Add the CSV

Copy the uploaded CSV into the `data` folder:

```bash
cp /path/to/fuel-prices-for-be-assessment.csv data/fuel-prices-for-be-assessment.csv
```

Then import it:

```bash
python manage.py import_fuel_prices data/fuel-prices-for-be-assessment.csv
```

## Geocode fuel stations once

This command uses Nominatim and respects a delay between calls.

For a quick local demo, geocode a limited number first:

```bash
python manage.py geocode_fuel_stations --limit 200 --sleep 1.1
```

For a fuller route planner, geocode all stations:

```bash
python manage.py geocode_fuel_stations --sleep 1.1
```

This can take a long time because public Nominatim has strict usage limits.

## Run the server

```bash
python manage.py runserver
```

## API endpoint

### Health check

```http
GET /api/health/
```

### Plan route

```http
POST /api/routes/plan/
Content-Type: application/json
```

Example:

```json
{
  "start": "Chicago, IL",
  "finish": "Atlanta, GA",
  "max_range_miles": 500,
  "initial_range_miles": 500,
  "mpg": 10,
  "corridor_miles": 25
}
```

Example cURL:

```bash
curl -X POST http://127.0.0.1:8000/api/routes/plan/ ^
  -H "Content-Type: application/json" ^
  -d "{\"start\":\"Chicago, IL\",\"finish\":\"Atlanta, GA\",\"corridor_miles\":25}"
```

macOS/Linux:

```bash
curl -X POST http://127.0.0.1:8000/api/routes/plan/ \
  -H "Content-Type: application/json" \
  -d '{"start":"Chicago, IL","finish":"Atlanta, GA","corridor_miles":25}'
```

## Response shape

```json
{
  "start": {
    "query": "Chicago, IL",
    "lat": 41.8755616,
    "lon": -87.6244212
  },
  "finish": {
    "query": "Atlanta, GA",
    "lat": 33.7489924,
    "lon": -84.3902644
  },
  "route": {
    "distance_miles": 716.43,
    "duration_hours": 11.59
  },
  "fuel_plan": {
    "total_fuel_cost": 68.91,
    "currency": "USD",
    "mpg": 10.0,
    "max_range_miles": 500.0,
    "initial_range_miles": 500.0,
    "fuel_stops": [
      {
        "sequence": 1,
        "route_mile": 489.25,
        "station": {
          "id": 123,
          "opis_truckstop_id": "12345",
          "name": "Example Truck Stop",
          "address": "123 Main St",
          "city": "Nashville",
          "state": "TN",
          "retail_price": 3.109
        },
        "gallons_to_buy": 22.72,
        "fuel_cost": 70.63,
        "next_stop_route_mile": 716.43
      }
    ]
  },
  "map": {
    "type": "FeatureCollection",
    "features": []
  },
  "api_call_counts": {
    "geocoding_calls": 2,
    "routing_calls": 1
  }
}
```

## Core algorithm

1. Route start to finish with one OSRM route call.
2. Sample route points every few miles.
3. Keep geocoded fuel stations within `corridor_miles` of the route.
4. Project each candidate station to an approximate mile marker along the route.
5. Build a DAG:
   - start node,
   - candidate fuel station nodes,
   - destination node.
6. Add an edge between two nodes if the distance along the route is within the vehicle range.
7. Edge cost:
   - start to first station uses the initial tank and costs 0,
   - station to next station/destination costs `(miles / mpg) * station_price`.
8. Run dynamic programming on the sorted nodes to find the lowest-cost reachable plan.

## Notes

- `map.features[0]` is the driving route LineString.
- Fuel stops are returned as Point features.
- Increase `corridor_miles` if the API cannot find enough geocoded stations near the selected route.
- Public Nominatim is okay for demos but not production-scale traffic.

```

### `fuel_route_planner/settings.py`

```python
from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "local-dev-secret-key")
DEBUG = os.getenv("DEBUG", "True").lower() in {"1", "true", "yes"}

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "routes",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "fuel_route_planner.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "fuel_route_planner.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

OSRM_BASE_URL = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org").rstrip("/")
NOMINATIM_BASE_URL = os.getenv(
    "NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org"
).rstrip("/")
NOMINATIM_USER_AGENT = os.getenv(
    "NOMINATIM_USER_AGENT",
    "fuel-route-planner-demo/1.0 your-email@example.com",
)

```

### `fuel_route_planner/urls.py`

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("routes.urls")),
]

```

### `fuel_route_planner/asgi.py`

```python
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fuel_route_planner.settings")

application = get_asgi_application()

```

### `fuel_route_planner/wsgi.py`

```python
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fuel_route_planner.settings")

application = get_wsgi_application()

```

### `routes/apps.py`

```python
from django.apps import AppConfig


class RoutesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "routes"

```

### `routes/models.py`

```python
from django.db import models


class FuelStation(models.Model):
    opis_truckstop_id = models.CharField(max_length=50, db_index=True)
    truckstop_name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120)
    state = models.CharField(max_length=2, db_index=True)
    rack_id = models.CharField(max_length=50, blank=True)
    retail_price = models.DecimalField(max_digits=8, decimal_places=4)

    latitude = models.FloatField(null=True, blank=True, db_index=True)
    longitude = models.FloatField(null=True, blank=True, db_index=True)
    geocoded_address = models.TextField(blank=True)
    geocoding_status = models.CharField(
        max_length=30,
        default="pending",
        choices=[
            ("pending", "Pending"),
            ("success", "Success"),
            ("failed", "Failed"),
        ],
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["state", "city"]),
            models.Index(fields=["latitude", "longitude"]),
            models.Index(fields=["retail_price"]),
        ]

    def __str__(self) -> str:
        return f"{self.truckstop_name} - {self.city}, {self.state}"

```

### `routes/admin.py`

```python
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

```

### `routes/urls.py`

```python
from django.urls import path

from .views import health_check, plan_route

urlpatterns = [
    path("health/", health_check, name="health_check"),
    path("routes/plan/", plan_route, name="plan_route"),
]

```

### `routes/views.py`

```python
import json
from json import JSONDecodeError

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .services.fuel_optimizer import FuelOptimizationError, build_fuel_plan
from .services.geocoding import GeocodingError, geocode_location
from .services.routing import RoutingError, get_driving_route


@require_GET
def health_check(request):
    return JsonResponse({"status": "ok"})


@csrf_exempt
@require_POST
def plan_route(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, JSONDecodeError):
        return JsonResponse({"error": "Invalid JSON request body."}, status=400)

    start_query = str(payload.get("start", "")).strip()
    finish_query = str(payload.get("finish", "")).strip()

    if not start_query or not finish_query:
        return JsonResponse(
            {"error": "Both 'start' and 'finish' are required."},
            status=400,
        )

    try:
        max_range_miles = float(payload.get("max_range_miles", 500))
        initial_range_miles = float(payload.get("initial_range_miles", 500))
        mpg = float(payload.get("mpg", 10))
        corridor_miles = float(payload.get("corridor_miles", 25))
    except (TypeError, ValueError):
        return JsonResponse(
            {
                "error": (
                    "'max_range_miles', 'initial_range_miles', 'mpg', and "
                    "'corridor_miles' must be numeric."
                )
            },
            status=400,
        )

    if max_range_miles <= 0 or initial_range_miles < 0 or mpg <= 0 or corridor_miles <= 0:
        return JsonResponse(
            {
                "error": (
                    "'max_range_miles', 'mpg', and 'corridor_miles' must be > 0. "
                    "'initial_range_miles' must be >= 0."
                )
            },
            status=400,
        )

    try:
        start = geocode_location(start_query)
        finish = geocode_location(finish_query)

        route = get_driving_route(
            start_lon=start["lon"],
            start_lat=start["lat"],
            finish_lon=finish["lon"],
            finish_lat=finish["lat"],
        )

        fuel_plan = build_fuel_plan(
            route_coordinates=route["coordinates"],
            route_distance_miles=route["distance_miles"],
            max_range_miles=max_range_miles,
            initial_range_miles=initial_range_miles,
            mpg=mpg,
            corridor_miles=corridor_miles,
        )
    except GeocodingError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except RoutingError as exc:
        return JsonResponse({"error": str(exc)}, status=502)
    except FuelOptimizationError as exc:
        return JsonResponse({"error": str(exc)}, status=422)

    route_feature = {
        "type": "Feature",
        "properties": {
            "kind": "route",
            "distance_miles": route["distance_miles"],
            "duration_hours": route["duration_hours"],
        },
        "geometry": {
            "type": "LineString",
            "coordinates": route["coordinates"],
        },
    }

    stop_features = []
    for stop in fuel_plan["fuel_stops"]:
        station = stop["station"]
        stop_features.append(
            {
                "type": "Feature",
                "properties": {
                    "kind": "fuel_stop",
                    "sequence": stop["sequence"],
                    "route_mile": stop["route_mile"],
                    "station_id": station["id"],
                    "name": station["name"],
                    "retail_price": station["retail_price"],
                    "gallons_to_buy": stop["gallons_to_buy"],
                    "fuel_cost": stop["fuel_cost"],
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [station["longitude"], station["latitude"]],
                },
            }
        )

    response = {
        "start": {
            "query": start_query,
            "lat": start["lat"],
            "lon": start["lon"],
            "display_name": start["display_name"],
        },
        "finish": {
            "query": finish_query,
            "lat": finish["lat"],
            "lon": finish["lon"],
            "display_name": finish["display_name"],
        },
        "route": {
            "distance_miles": route["distance_miles"],
            "duration_hours": route["duration_hours"],
        },
        "fuel_plan": fuel_plan,
        "map": {
            "type": "FeatureCollection",
            "features": [route_feature, *stop_features],
        },
        "api_call_counts": {
            "geocoding_calls": 2,
            "routing_calls": 1,
        },
    }

    return JsonResponse(response, json_dumps_params={"indent": 2})

```

### `routes/services/geo.py`

```python
import math
from typing import Iterable

EARTH_RADIUS_MILES = 3958.7613


def haversine_miles(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    lon1_rad = math.radians(lon1)
    lat1_rad = math.radians(lat1)
    lon2_rad = math.radians(lon2)
    lat2_rad = math.radians(lat2)

    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    return EARTH_RADIUS_MILES * c


def cumulative_route_miles(coordinates: list[list[float]]) -> list[float]:
    cumulative = [0.0]
    total = 0.0

    for previous, current in zip(coordinates, coordinates[1:]):
        total += haversine_miles(previous[0], previous[1], current[0], current[1])
        cumulative.append(total)

    return cumulative


def sample_route_by_distance(
    coordinates: list[list[float]],
    cumulative_miles: list[float],
    step_miles: float = 5.0,
) -> list[dict]:
    if not coordinates:
        return []

    samples = []
    next_target = 0.0

    for coord, route_mile in zip(coordinates, cumulative_miles):
        if route_mile >= next_target:
            samples.append(
                {
                    "lon": coord[0],
                    "lat": coord[1],
                    "route_mile": route_mile,
                }
            )
            next_target = route_mile + step_miles

    last = {
        "lon": coordinates[-1][0],
        "lat": coordinates[-1][1],
        "route_mile": cumulative_miles[-1],
    }

    if not samples or samples[-1]["route_mile"] != last["route_mile"]:
        samples.append(last)

    return samples


def bounds_for_coordinates(
    coordinates: Iterable[list[float]],
    padding_degrees: float = 0.5,
) -> dict[str, float]:
    lons = [coord[0] for coord in coordinates]
    lats = [coord[1] for coord in coordinates]

    return {
        "min_lon": min(lons) - padding_degrees,
        "max_lon": max(lons) + padding_degrees,
        "min_lat": min(lats) - padding_degrees,
        "max_lat": max(lats) + padding_degrees,
    }

```

### `routes/services/geocoding.py`

```python
import requests
from django.conf import settings


class GeocodingError(Exception):
    pass


def geocode_location(query: str) -> dict:
    """
    Geocode a free-form USA location with Nominatim.

    This is used only for the request start and finish locations.
    Fuel station geocoding is done separately and cached in the DB.
    """
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": 1,
        "countrycodes": "us",
        "addressdetails": 1,
    }

    headers = {
        "User-Agent": settings.NOMINATIM_USER_AGENT,
    }

    try:
        response = requests.get(
            f"{settings.NOMINATIM_BASE_URL}/search",
            params=params,
            headers=headers,
            timeout=15,
        )
    except requests.RequestException as exc:
        raise GeocodingError(f"Geocoding service request failed: {exc}") from exc

    if response.status_code != 200:
        raise GeocodingError(
            f"Geocoding service returned HTTP {response.status_code}: {response.text[:200]}"
        )

    data = response.json()
    if not data:
        raise GeocodingError(f"No USA geocoding result found for '{query}'.")

    result = data[0]
    return {
        "lat": float(result["lat"]),
        "lon": float(result["lon"]),
        "display_name": result.get("display_name", query),
    }

```

### `routes/services/routing.py`

```python
import requests
from django.conf import settings


class RoutingError(Exception):
    pass


def get_driving_route(
    start_lon: float,
    start_lat: float,
    finish_lon: float,
    finish_lat: float,
) -> dict:
    """
    Calls OSRM once and returns a full GeoJSON route.
    """
    coordinates = f"{start_lon},{start_lat};{finish_lon},{finish_lat}"
    url = f"{settings.OSRM_BASE_URL}/route/v1/driving/{coordinates}"

    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "false",
    }

    try:
        response = requests.get(url, params=params, timeout=30)
    except requests.RequestException as exc:
        raise RoutingError(f"Routing service request failed: {exc}") from exc

    if response.status_code != 200:
        raise RoutingError(
            f"Routing service returned HTTP {response.status_code}: {response.text[:200]}"
        )

    data = response.json()
    if data.get("code") != "Ok" or not data.get("routes"):
        raise RoutingError(f"No route found. OSRM response: {data}")

    route = data["routes"][0]
    return {
        "coordinates": route["geometry"]["coordinates"],
        "distance_miles": round(route["distance"] / 1609.344, 2),
        "duration_hours": round(route["duration"] / 3600, 2),
    }

```

### `routes/services/fuel_optimizer.py`

```python
from dataclasses import dataclass
from decimal import Decimal
from math import inf
from typing import Optional

from routes.models import FuelStation

from .geo import (
    bounds_for_coordinates,
    cumulative_route_miles,
    haversine_miles,
    sample_route_by_distance,
)


class FuelOptimizationError(Exception):
    pass


@dataclass
class CandidateStation:
    id: int
    opis_truckstop_id: str
    name: str
    address: str
    city: str
    state: str
    retail_price: float
    latitude: float
    longitude: float
    route_mile: float
    distance_from_route_miles: float


@dataclass
class Node:
    kind: str
    route_mile: float
    station: Optional[CandidateStation] = None


def _station_to_dict(station: CandidateStation) -> dict:
    return {
        "id": station.id,
        "opis_truckstop_id": station.opis_truckstop_id,
        "name": station.name,
        "address": station.address,
        "city": station.city,
        "state": station.state,
        "retail_price": round(station.retail_price, 4),
        "latitude": station.latitude,
        "longitude": station.longitude,
        "distance_from_route_miles": round(station.distance_from_route_miles, 2),
    }


def _find_candidate_stations(
    route_coordinates: list[list[float]],
    corridor_miles: float,
) -> list[CandidateStation]:
    cumulative_miles = cumulative_route_miles(route_coordinates)
    route_samples = sample_route_by_distance(
        route_coordinates,
        cumulative_miles,
        step_miles=5.0,
    )
    bounds = bounds_for_coordinates(route_coordinates, padding_degrees=1.0)

    # Initial DB bounding-box filter is intentionally broad and fast.
    stations = (
        FuelStation.objects.filter(
            geocoding_status="success",
            latitude__isnull=False,
            longitude__isnull=False,
            latitude__gte=bounds["min_lat"],
            latitude__lte=bounds["max_lat"],
            longitude__gte=bounds["min_lon"],
            longitude__lte=bounds["max_lon"],
        )
        .only(
            "id",
            "opis_truckstop_id",
            "truckstop_name",
            "address",
            "city",
            "state",
            "retail_price",
            "latitude",
            "longitude",
        )
        .order_by("retail_price")
    )

    candidates_by_station_id: dict[int, CandidateStation] = {}

    for station in stations:
        nearest_sample = None
        nearest_distance = inf

        for sample in route_samples:
            distance = haversine_miles(
                station.longitude,
                station.latitude,
                sample["lon"],
                sample["lat"],
            )
            if distance < nearest_distance:
                nearest_distance = distance
                nearest_sample = sample

        if nearest_sample is None or nearest_distance > corridor_miles:
            continue

        # If duplicate records exist for the same station, keep the lower price.
        existing = candidates_by_station_id.get(station.id)
        if existing and existing.retail_price <= float(station.retail_price):
            continue

        candidates_by_station_id[station.id] = CandidateStation(
            id=station.id,
            opis_truckstop_id=station.opis_truckstop_id,
            name=station.truckstop_name,
            address=station.address,
            city=station.city,
            state=station.state,
            retail_price=float(station.retail_price),
            latitude=float(station.latitude),
            longitude=float(station.longitude),
            route_mile=float(nearest_sample["route_mile"]),
            distance_from_route_miles=float(nearest_distance),
        )

    # Remove near-duplicate candidates at almost the same route mile by keeping
    # cheaper options first. This keeps DP quick and the result cleaner.
    bucket_size_miles = 2
    candidates = sorted(
        candidates_by_station_id.values(),
        key=lambda item: (int(item.route_mile // bucket_size_miles), item.retail_price),
    )

    compact: list[CandidateStation] = []
    occupied_buckets: set[int] = set()

    for candidate in candidates:
        bucket = int(candidate.route_mile // bucket_size_miles)
        if bucket in occupied_buckets:
            continue
        occupied_buckets.add(bucket)
        compact.append(candidate)

    return sorted(compact, key=lambda item: item.route_mile)


def build_fuel_plan(
    route_coordinates: list[list[float]],
    route_distance_miles: float,
    max_range_miles: float,
    initial_range_miles: float,
    mpg: float,
    corridor_miles: float,
) -> dict:
    """
    Dynamic-programming fuel optimization.

    Assumption:
    - The vehicle starts with `initial_range_miles` of fuel.
    - Fuel bought at a selected station powers the leg from that station
      to the next selected station or destination.
    - The first leg from start uses existing fuel and has zero purchase cost.
    """
    if route_distance_miles <= initial_range_miles:
        return {
            "total_fuel_cost": 0.0,
            "currency": "USD",
            "mpg": float(mpg),
            "max_range_miles": float(max_range_miles),
            "initial_range_miles": float(initial_range_miles),
            "corridor_miles": float(corridor_miles),
            "total_gallons_purchased": 0.0,
            "fuel_stops": [],
            "assumptions": [
                "Vehicle starts with the requested initial fuel range.",
                "Because the destination is reachable with initial fuel, no fuel stop is required.",
            ],
        }

    candidates = _find_candidate_stations(
        route_coordinates=route_coordinates,
        corridor_miles=corridor_miles,
    )

    if not candidates:
        raise FuelOptimizationError(
            "No geocoded fuel stations were found near this route. "
            "Run geocode_fuel_stations first or increase corridor_miles."
        )

    nodes: list[Node] = [Node(kind="start", route_mile=0.0)]
    nodes.extend(Node(kind="station", route_mile=c.route_mile, station=c) for c in candidates)
    nodes.append(Node(kind="finish", route_mile=route_distance_miles))
    nodes.sort(key=lambda node: node.route_mile)

    start_index = next(index for index, node in enumerate(nodes) if node.kind == "start")
    finish_index = next(index for index, node in enumerate(nodes) if node.kind == "finish")

    dp = [inf] * len(nodes)
    parent: list[Optional[int]] = [None] * len(nodes)
    dp[start_index] = 0.0

    for i, current in enumerate(nodes):
        if dp[i] == inf:
            continue

        for j in range(i + 1, len(nodes)):
            next_node = nodes[j]
            leg_distance = next_node.route_mile - current.route_mile

            if current.kind == "start":
                if leg_distance > initial_range_miles:
                    break
                leg_cost = 0.0
            else:
                if leg_distance > max_range_miles:
                    break
                if current.station is None:
                    continue
                leg_cost = (leg_distance / mpg) * current.station.retail_price

            new_cost = dp[i] + leg_cost
            if new_cost < dp[j]:
                dp[j] = new_cost
                parent[j] = i

    if dp[finish_index] == inf:
        raise FuelOptimizationError(
            "No valid fuel plan found. Try increasing corridor_miles or geocoding more stations."
        )

    path_indexes = []
    cursor = finish_index
    while cursor is not None:
        path_indexes.append(cursor)
        cursor = parent[cursor]
    path_indexes.reverse()

    fuel_stops = []
    total_gallons = 0.0
    sequence = 1

    for path_pos, node_index in enumerate(path_indexes):
        node = nodes[node_index]
        if node.kind != "station" or node.station is None:
            continue

        next_node = nodes[path_indexes[path_pos + 1]]
        leg_distance = next_node.route_mile - node.route_mile
        gallons = leg_distance / mpg
        cost = gallons * node.station.retail_price
        total_gallons += gallons

        fuel_stops.append(
            {
                "sequence": sequence,
                "route_mile": round(node.route_mile, 2),
                "station": _station_to_dict(node.station),
                "gallons_to_buy": round(gallons, 2),
                "fuel_cost": round(cost, 2),
                "next_stop_route_mile": round(next_node.route_mile, 2),
            }
        )
        sequence += 1

    return {
        "total_fuel_cost": round(dp[finish_index], 2),
        "currency": "USD",
        "mpg": float(mpg),
        "max_range_miles": float(max_range_miles),
        "initial_range_miles": float(initial_range_miles),
        "corridor_miles": float(corridor_miles),
        "total_gallons_purchased": round(total_gallons, 2),
        "fuel_stops": fuel_stops,
        "candidate_station_count": len(candidates),
        "assumptions": [
            "Vehicle starts with the requested initial fuel range.",
            "Fuel station coordinates are pre-geocoded and cached from the CSV.",
            "Fuel bought at a stop is calculated only for the distance to the next chosen stop or destination.",
            "Fuel stations are considered only when they are within corridor_miles of the route.",
        ],
    }

```

### `routes/management/commands/import_fuel_prices.py`

```python
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

```

### `routes/management/commands/geocode_fuel_stations.py`

```python
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

```

### `routes/migrations/0001_initial.py`

```python
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

```
