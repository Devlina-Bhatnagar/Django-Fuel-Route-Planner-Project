# Fuel Route Planner API

Django API for the Spotter backend

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

We can change this through the request body using:

```json
{
  "initial_range_miles": 0
}
```

For `initial_range_miles = 0`, we must have a geocoded station close to mile 0 of the route.

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
