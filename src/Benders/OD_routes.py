import itertools
import os
import pulp
import networkx as nx
import time


GRAPH_PATH = os.path.join(os.path.dirname(__file__), "gemeente_graph_length_sorted.graphml")

GEMEENTE_SCENARIOS = (30, 82)
ACTIERADIUS_SCENARIOS = (200,250)
max_iterations = 350
max_run_time = 7200

def OD_routes(graph, od_nodes):
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
        #Maak hier het kortste pad aan de hand van Dijkstra's algoritme.
        path = nx.shortest_path(
            graph,
            origin,
            destination,
            weight="distance_km")

        afstand = sum(
            graph.edges[from_node, to_node]["distance_km"]
            for from_node, to_node in zip(path, path[1:]))

        inwoners_origin = graph.nodes[origin]["inwoners"]
        inwoners_destination = graph.nodes[destination]["inwoners"]
        verkeersvraag = (inwoners_origin * inwoners_destination) / afstand

        cumdist = [0]
        totaal = 0
        for from_node, to_node in zip(path, path[1:]):
            totaal += graph.edges[from_node, to_node]["distance_km"]
            cumdist.append(totaal)

        routes.append({
            "id": f"r{route_index}",
            "label": f"{origin}-{destination}",
            "origin": origin,
            "destination": destination,
            "path": path,
            "cumdist": cumdist,
            "afstand": afstand,
            "verkeersvraag": verkeersvraag})
    return routes
