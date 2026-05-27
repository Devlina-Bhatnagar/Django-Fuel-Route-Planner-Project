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
