import cbsodata
import os
import math
import requests
import networkx as nx
from shapely.geometry import LineString, Point


def get_gemeente_coords(gemeente_code):
    """
    Haal de centrumcoördinaten van een gemeente op via de PDOK Locatieserver.

    De functie zoekt op basis van een gemeentecode naar een gemeenteobject in
    de PDOK Locatieserver. Wanneer een resultaat wordt gevonden, wordt het
    geografische middelpunt uit het veld ``centroide_ll`` gehaald. Dit punt
    wordt omgezet naar latitude en longitude.

    Parameters
    ----------
    gemeente_code : str
        CBS-gemeentecode waarmee de gemeente wordt opgezocht.

    Returns
    -------
    tuple[float | None, float | None]
        Tuple ``(latitude, longitude)`` wanneer coördinaten worden gevonden.
        Als geen geldig resultaat beschikbaar is, wordt ``(None, None)``
        teruggegeven.
    """
    url = "https://api.pdok.nl/bzk/locatieserver/search/v3_1/free"
    params = {
        "q": gemeente_code,
        "fq": "type:gemeente",
        "fl": "gemeentenaam,centroide_ll",
        "rows": 1,
    }
    response = requests.get(url, params=params, timeout=10)
    data = response.json()
    if data['response']['numFound'] > 0:
        centroide = data['response']['docs'][0].get('centroide_ll', '')
        if centroide.startswith('POINT('):
            coords = centroide.replace('POINT(', '').replace(')', '').split()
            return float(coords[1]), float(coords[0])
    return None, None