import itertools
import os
import pulp
import networkx as nx
import time


GRAPH_PATH = os.path.join(os.path.dirname(__file__), "gemeente_graph_length_sorted.graphml")

GEMEENTE_SCENARIOS = (1, 82)
ACTIERADIUS_SCENARIOS = (200,250)
max_iterations = 350
max_run_time = 7200
ORIGIN_DESTINATION_CAN_CHARGE = False


def route_is_covered(route, selected_stations, vehicle_range_km):
    """
    Deze functie controleert of voor de gekozen laadstations in deze iteratie van het masterprobleem
    de route haalbaar is. De functie bepaalt eerst welke stations op het pad liggen en controleert
    vervolgens iteratief welke stations vanaf de oorsprong bereikbaar zijn.
    Daarna wordt gecontroleerd of de bestemming vanaf een bereikbaar station
    kan worden bereikt.

    Parameters
    ----------
    route : dict
        Route dictionary met ten minste de sleutels ``path`` en ``cumdist``.
    selected_stations : set[str]
        Verzameling gemeentecodes waar een laadstation is geplaatst.
    vehicle_range_km : float
        Actieradius van het voertuig in kilometers.

    Returns
    -------
    bool
        ``True`` als de route gedekt is door de geselecteerde laadstations,
        anders ``False``.
    """

    path = route["path"]
    cumdist = route["cumdist"]
    destination_index = len(path) - 1
    station_indices = {
        index
        for index, node in enumerate(path)
        if node in selected_stations
    }

    if ORIGIN_DESTINATION_CAN_CHARGE:
        station_indices.add(0)
        station_indices.add(destination_index)

    if not station_indices:
        return False

    half_range = vehicle_range_km / 2
    reachable_stations = set()

    for index in station_indices:
        distance_from_origin = cumdist[index]
        if distance_from_origin <= half_range:
            reachable_stations.add(index)

    if 0 in station_indices:
        reachable_stations.add(0)

    changed = True

    while changed:
        changed = False
        for index in sorted(station_indices):
            if index in reachable_stations:
                continue

            can_reach_index = any(
                cumdist[index] >= cumdist[reachable_index]
                and cumdist[index] - cumdist[reachable_index] <= vehicle_range_km
                for reachable_index in reachable_stations
            )
            if can_reach_index:
                reachable_stations.add(index)
                changed = True

    if destination_index in station_indices:
        return any(
            cumdist[destination_index] >= cumdist[reachable_index]
            and cumdist[destination_index] - cumdist[reachable_index] <= vehicle_range_km
            for reachable_index in reachable_stations
        )

    return any(
        cumdist[destination_index] >= cumdist[reachable_index]
        and cumdist[destination_index] - cumdist[reachable_index] <= half_range
        for reachable_index in reachable_stations
    )


def evaluate_route_coverage(routes, selected_stations, vehicle_range_km):
    """
    Helpfunctie die voor het overzicht handig is. Deze functie geeft voor gekozen laadstations weer
    hoeveel routes gedekt zijn en wat de waarde van de doelfunctie is.
    """
    covered_routes = 0
    actual_objective = 0.0

    for route in routes:
        if route_is_covered(route, selected_stations, vehicle_range_km):
            covered_routes += 1
            actual_objective += route["raw_flow"]

    return covered_routes, actual_objective