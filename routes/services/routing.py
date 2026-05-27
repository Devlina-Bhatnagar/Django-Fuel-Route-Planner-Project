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
