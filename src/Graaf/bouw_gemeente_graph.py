import cbsodata
import os
import math
import requests
import networkx as nx
from shapely.geometry import LineString, Point

TOLERANCE = 0.03
MAX_EDGE_LENGTE = 30
GEEN_KRIUSENDE_EDGES = True

def bouw_gemeente_graph(results, tolerance=TOLERANCE):
    """
    Bouw een gemeentegraaf op basis van inwonersaantallen en coördinaten.
    Eerst worden alle gemeenten als knopen toegevoegd aan een NetworkX-graaf. 
    Daarna worden kandidaatverbindingen bepaald door voor elk paar gemeenten 
    te kijken welke tussenliggende knopen
    dicht bij de rechte lijn tussen beide gemeenten liggen. Een kandidaatroute
    wordt alleen gebruikt als alle opeenvolgende segmenten korter zijn dan de
    maximale toegestane segmentlengte. De resulterende graaf bevat dezelfde knopen
    als de initiële gemeentegraaf, maar alleen de geselecteerde verbindingen.
    Deze verbindingen worden in oplopende volgorde van lengte toegevoegd. Indien
    ``GEEN_KRIUSENDE_EDGES`` gelijk is aan ``True``, worden verbindingen die
    bestaande verbindingen kruisen overgeslagen.

    results: list[dict]
        Lijst met gemeentelijke gegevens per knoop. Hierin zijn ''gemeente_code'' ''latitude'',
        ''longitude'', ''inwoners'' opgeslagen.
    tolerance: float
        Maximale afstand waarbinnen een knoop als tussenliggende knoop op een
        rechte route tussen twee gemeenten wordt beschouwd. De standaardwaarde
        is ``TOLERANCE``

    Returns
    -------
    networkx.Graph
        Ongerichte gemeentegraaf met gemeenten als knopen en geselecteerde
        verbindingen als edges. Elke knoop bevat de attributen ``gemeente_code``, ``inwoners``,
        ``latitude`` en ``longitude``. Elke edge bevat het attribuut
        ``distance_km``, waarin de hemelsbrede afstand tussen de twee verbonden
        gemeenten in kilometers is opgeslagen.

    """
    graph = nx.Graph()
    for row in results:
        if row["latitude"] is not None and row["longitude"] is not None:
            graph.add_node(
                row["gemeente_code"],
                inwoners=row["inwoners"],
                latitude=row["latitude"],
                longitude=row["longitude"],
            )
    
    nodes = list(graph.nodes)
    candidates = {}

    # Verzamel alle kandidaat-segmenten tussen alle knopenparen
    for origin_index, origin in enumerate(nodes):
        for destination in nodes[origin_index + 1:]:
            tussen_knopen = knopen_op_route(graph, origin, destination, tolerance)
            path_nodes = [origin, *tussen_knopen, destination]

            # Controleer of alle segmenten kort genoeg zijn
            valid = all(
                knoop_afstand(graph, path_nodes[i], path_nodes[i + 1]) <= MAX_EDGE_LENGTE
                for i in range(len(path_nodes) - 1)
            )
            if not valid:
                continue

            # Voeg kandidaat-edges toe
            for from_node, to_node in zip(path_nodes, path_nodes[1:]):
                if from_node == to_node:
                    continue
                edge_key = frozenset((from_node, to_node))
                if edge_key not in candidates:
                    candidates[edge_key] = knoop_afstand(graph, from_node, to_node)

    # Voeg edges toe in volgorde van lengte
    route_graph = nx.Graph()
    route_graph.add_nodes_from(graph.nodes(data=True))
    def knoop_positie(node):
        """
            Geef de geografische positie van een knoop als ``(longitude, latitude)``.
        """
        data = graph.nodes[node]
        return float(data["longitude"]), float(data["latitude"])
    for (from_node, to_node), distance in sorted(candidates.items(), key=lambda x: x[1]):
        if route_graph.has_edge(from_node, to_node):
            continue
        
        # Voeg edge toe als hij kort genoeg is
        if distance <= MAX_EDGE_LENGTE:
            if GEEN_KRIUSENDE_EDGES:
                # Controleer of edge bestaande edges kruist
                new_line = LineString([knoop_positie(from_node), knoop_positie(to_node)])
                crosses = False
                for edge_from, edge_to in route_graph.edges:
                    if from_node in (edge_from, edge_to) or to_node in (edge_from, edge_to):
                        continue
                    existing_line = LineString([knoop_positie(edge_from), knoop_positie(edge_to)])
                    if new_line.crosses(existing_line):
                        crosses = True
                        break
                if crosses:
                    continue
            
            route_graph.add_edge(from_node, to_node, distance_km=distance)

    return route_graph