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

def route_subproblem_dual_cut(route, station_values, vehicle_range_km):
    """
    Los het subprobleem op per route en voor een gegeven stations configuratie. Hierbij is gebruik gemaakt van
    een max-flow-min-cut constructie op een getransformeerde graaf. Voor elke route waarvoor uit het masterprobleem
    komt dat de route als gedekt staat wordt dit gedaan. Wanneer max-flow<1, wordt er een min-cut gemaakt waarmee
    de knopen worden gegeven die kunnen worden toegevoegd als Benders snede

    Parameters
    ----------
    route : dict
        Routedictionary met ten minste de sleutels ``path`` en ``cumdist``.
    station_values : dict[str, float]
        Dictionary met per gemeentecode de huidige waarde van de
        stationvariabele uit het masterprobleem.
    vehicle_range_km : float
        Actieradius van het voertuig in kilometers.

    Returns
    -------
    tuple[float, list[str] | None]
        Tuple ``(subproblem_value, cut_nodes)``. Hierbij is
        ``subproblem_value`` de waarde van het max-flow/min-cut-subprobleem.
        Als de route al gedekt is, of als geen bruikbare snede wordt gevonden,
        is ``cut_nodes`` gelijk aan ``None``. Anders bevat ``cut_nodes`` de
        gemeentecodes die de Benders-snede definiëren.
    """

    path = route["path"]
    cumdist = route["cumdist"]
    destination_index = len(path) - 1
    half_range = vehicle_range_km / 2

    network = nx.DiGraph()
    source = "source"
    sink = "sink"
    inf_capacity = len(path) + 1

    #Splits elke knoop in 2 knopen en voeg een interne boog ertussen toe
    for index, node in enumerate(path):
        node_capacity = float(station_values.get(node, 0.0))
        network.add_edge((index, "in"), (index, "out"), capacity=node_capacity)

    network.add_edge((destination_index, "out"), sink, capacity=inf_capacity)

    #Voeg bogen toe vanaf de source naar haalbare knopen
    for to_index in range(1, len(path)):
        if cumdist[to_index] <= half_range:
            network.add_edge(source, (to_index, "in"), capacity=inf_capacity)

    network.add_edge(source, (0, "in"), capacity=inf_capacity)
    #Voeg knopen toe tussen knopen waarvoor de afstand kleiner is dan vehicle_range_km
    for from_index in range(len(path) - 1):
        for to_index in range(from_index + 1, len(path)):
            distance = cumdist[to_index] - cumdist[from_index]
            if distance > vehicle_range_km:
                continue

            network.add_edge(
                (from_index, "out"),
                (to_index, "in"),
                capacity=inf_capacity,
            )

            if to_index == destination_index and distance <= half_range:
                network.add_edge(
                    (from_index, "out"),
                    sink,
                    capacity=inf_capacity,
                )

    max_flow_value, _ = nx.maximum_flow(network, source, sink, capacity="capacity")
    if max_flow_value >= 1 - 1e-7:
        return max_flow_value, None

    min_cut_value, (reachable_side, unreachable_side) = nx.minimum_cut(
        network,
        source,
        sink
    )

    cut_nodes = []
    constant_capacity = 0.0
    #Bepaal welke knopen in de Benders snede moeten komen
    for from_node in reachable_side:
        for to_node, edge_data in network[from_node].items():
            if to_node not in unreachable_side:
                continue

            is_node_capacity_edge = (
                isinstance(from_node, tuple)
                and isinstance(to_node, tuple)
                and from_node[1] == "in"
                and to_node[1] == "out"
                and from_node[0] == to_node[0]
            )
            if is_node_capacity_edge:
                route_index = from_node[0]
                cut_nodes.append(path[route_index])
            elif edge_data["capacity"] < inf_capacity:
                constant_capacity += edge_data["capacity"]

    if constant_capacity >= 1 - 1e-7:
        return min_cut_value, None

    return min_cut_value, sorted(set(cut_nodes))
