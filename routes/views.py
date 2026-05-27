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
