import itertools
import os
import pulp
import networkx as nx
import time


GRAPH_PATH = os.path.join(os.path.dirname(__file__), "gemeente_graph_length_sorted.graphml")

GEMEENTE_SCENARIOS = (30, 82)
ACTIERADIUS_SCENARIOS = (200,250)
max_iterations = 350
max_runtime = 7200

def subprobleem_en_cuts(route, x_waarden, actieradius):
    """
    Los het subprobleem op per route en voor een gegeven stations configuratie. Hierbij is gebruik gemaakt van
    een max-flow-min-cut constructie op een getransformeerde graaf. Voor elke route waarvoor uit het masterprobleem
    komt dat de route als gedekt staat wordt dit gedaan. Wanneer max-flow<1, wordt er een min-cut gemaakt waarmee
    de knopen worden gegeven die kunnen worden toegevoegd als Benders snede

    Parameters
    ----------
    route : dict
        Routedictionary met ten minste de sleutels ``path`` en ``cumdist``.
    x_waarden : dict[str, float]
        Dictionary met per gemeentecode de huidige waarde van de
        stationvariabele uit het masterprobleem.
    actieradius : float
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
    half_range = actieradius / 2

    network = nx.DiGraph()
    source = "source"
    sink = "sink"
    inf_cap = len(path) + 1

    for i, node in enumerate(path):
        node_cap = float(x_waarden.get(node, 0.0))
        network.add_edge((i, "in"), (i, "uit"), capacity=node_cap)

    des_index = len(path) - 1
    network.add_edge((des_index, "uit"), sink, capacity=inf_cap)

    for to_index in range(1, len(path)):
        if cumdist[to_index] <= half_range:
            network.add_edge(source, (to_index, "in"), capacity=inf_cap)

    network.add_edge(source, (0, "in"), capacity=inf_cap)

    for from_index in range(len(path) - 1):
        for to_index in range(from_index + 1, len(path)):
            distance = cumdist[to_index] - cumdist[from_index]
            if distance > actieradius:
                continue

            network.add_edge(
                (from_index, "uit"),
                (to_index, "in"),
                capacity=inf_cap)

            if to_index == des_index and distance <= half_range:
                network.add_edge(
                    (from_index, "uit"),
                    sink,
                    capacity=inf_cap)
    #Hier wordt de maximale flow berekend met networkx.
    max_flow_value, _ = nx.maximum_flow(network, source, sink, capacity="capacity")
    if max_flow_value >= 1 - 1e-7:
        return max_flow_value, None

    #Hier wordt de minimale cut berekend met networkx.
    min_cut_value, (s_side, t_side) = nx.minimum_cut(
        network,
        source,
        sink)

    cut_nodes = []
    const_cap = 0

    for from_node in s_side:
        for to_node, edge_data in network[from_node].items():
            if to_node not in t_side:
                continue
#Hier wordt gecontroleerd of de edge tussen in en uit knoop zit en niet de sink of source is
            cut_edges = (
                isinstance(from_node, tuple)
                and isinstance(to_node, tuple)
                and from_node[1] == "in"
                and to_node[1] == "uit"
                and from_node[0] == to_node[0])

            if cut_edges:
                route_index = from_node[0]
                cut_nodes.append(path[route_index])
            elif edge_data["capacity"] < inf_cap:
                const_cap += edge_data["capacity"]

    if const_cap >= 1 - 1e-7:
        return min_cut_value, None

    return min_cut_value, sorted(set(cut_nodes))

