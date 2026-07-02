import cbsodata
import os
import math
import requests
import networkx as nx
from shapely.geometry import LineString, Point


def haversine_km(lat1, lon1, lat2, lon2):
    """
    Bereken de hemelsbrede afstand tussen twee geografische coördinaten.
    De afstand wordt berekend met de Haversine-formule. Hierbij worden de
    coördinaten geïnterpreteerd als punten op een bolvormig aardoppervlak.
    De uitkomst is daardoor een benadering van de kortste afstand over het
    aardoppervlak tussen beide punten.

    Parameters
    ----------
    lat1 : float
        Breedtegraad van het eerste punt in decimale graden.
    lon1 : float
        Lengtegraad van het eerste punt in decimale graden.
    lat2 : float
        Breedtegraad van het tweede punt in decimale graden.
    lon2 : float
        Lengtegraad van het tweede punt in decimale graden.

    Returns
    -------
    floaat
        De hemelsbrede afstand tussen beide punten in kilometers.
    """
    radius = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def node_distance_km(graph, from_node, to_node):
    """
    Bereken de hemelsbrede afstand tussen twee knopen in een graaf.

    De functie haalt de latitude en longitude van beide knopen uit de
    knoopattributen van de NetworkX-graaf. Vervolgens wordt de afstand tussen
    deze twee geografische punten berekend met de Haversine-formule.

    Parameters
    ----------
    graph : networkx.Graph
        Graaf waarvan de knopen de attributen ``latitude`` en ``longitude``
        bevatten.
    from_node : str
        CBS-gemeentecode van de eerste knoop waarvoor de afstand wordt berekend.
    to_node : str
        CBS-gemeentecode van de tweede knoop waarvoor de afstand wordt berekend.
    Returns
    -------
    float
        De hemelsbrede afstand tussen de twee knopen in kilometers.
    """
    from_data = graph.nodes[from_node]
    to_data = graph.nodes[to_node]
    return haversine_km(
        float(from_data["latitude"]),
        float(from_data["longitude"]),
        float(to_data["latitude"]),
        float(to_data["longitude"]),
    )