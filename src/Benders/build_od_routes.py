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


def build_od_routes(graph, od_nodes):
    """
    Construeer OD-routes tussen alle paren geselecteerde gemeenten.

    Voor elk ongeordend paar gemeenten uit ``od_nodes`` wordt het kortste pad
    in de gemeentegraaf bepaald, waarbij ``distance_km`` als gewicht wordt
    gebruikt. Voor elk geldig pad wordt een routedictionary aangemaakt met
    onder andere een route-id, oorsprong, bestemming, pad, cumulatieve afstanden,
    totale afstand en ruwe verkeersvraag.

    De ruwe verkeersvraag wordt berekend als het product van de inwonersaantallen
    van oorsprong en bestemming, gedeeld door de afstand tussen beide gemeenten.

    Parameters
    ----------
    graph : networkx.Graph
        Gemeentegraaf waarvan de knopen het attribuut ``inwoners`` bevatten en
        de edges het attribuut ``distance_km``.
    od_nodes : list[str]
        Lijst met gemeentecodes die als oorsprong en bestemming gebruikt worden.

    Returns
    -------
    list[dict]
        Lijst met routedictionaries. Elke dictionary bevat de sleutels ``id``,
        ``label``, ``origin``, ``destination``, ``path``, ``cumdist``,
        ``distance_km`` en ``raw_flow``.

    """
    routes = []
    for route_index, (origin, destination) in enumerate(itertools.combinations(od_nodes, 2)):
        try:
            path = nx.shortest_path(
                graph,
                origin,
                destination,
                weight="distance_km",
            )
        except nx.NetworkXNoPath:
            continue

        distance = path_distance(graph, path)
        if distance <= 0:
            continue

        inwoners_origin = graph.nodes[origin]["inwoners"]
        inwoners_destination = graph.nodes[destination]["inwoners"]
        raw_flow = (inwoners_origin * inwoners_destination) / distance

        routes.append({
            "id": f"r{route_index}",
            "label": f"{origin}-{destination}",
            "origin": origin,
            "destination": destination,
            "path": path,
            "cumdist": cumulative_path_distances(graph, path),
            "distance_km": distance,
            "raw_flow": raw_flow,
        })

    return routes