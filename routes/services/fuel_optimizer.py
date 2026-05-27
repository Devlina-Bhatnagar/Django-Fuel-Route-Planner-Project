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
