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
