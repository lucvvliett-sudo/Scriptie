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

def route_gedekt(route, selected_stat, actieradius):
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
    selected_stat : set[str]
        Verzameling gemeentecodes waar een laadstation is geplaatst.
    actieradius : float
        Actieradius van het voertuig in kilometers.

    Returns
    -------
    bool
        ``True`` als de route gedekt is door de geselecteerde laadstations,
        anders ``False``.
    """
    path = route["path"]
    cumdist = route["cumdist"]
    station_indices = {index for index, node in enumerate(path) 
    if node in selected_stat}

    if not station_indices:
        return False

    half_range = actieradius / 2
    haalbaar = set()

    for index in station_indices:
        afst_origin = cumdist[index]
        if afst_origin <= half_range:
            haalbaar.add(index)

    for index in sorted(station_indices):
        if index in haalbaar:
            continue

        for vorige_index in sorted(haalbaar):
            afstand = cumdist[index] - cumdist[vorige_index]

            if 0 <= afstand <= actieradius:
                haalbaar.add(index)
                break

    D_index = len(path) - 1
    #rekening houden met de 50% aanname wanneer er geen station op D staat
    if D_index in station_indices:
        return any(
            cumdist[D_index] >= cumdist[index]
            and cumdist[D_index] - cumdist[index] <= actieradius
            for index in haalbaar
        )

    return any(
        cumdist[D_index] >= cumdist[index]
        and cumdist[D_index] - cumdist[index] <= half_range
        for index in haalbaar
    )


def info_dekking(routes, selected_stat, actieradius):
    """
    Helpfunctie die voor het overzicht handig is. Deze functie geeft voor gekozen laadstations weer
    hoeveel routes gedekt zijn en wat de waarde van de doelfunctie is.
    """
    covered_routes = 0
    somverkeer = 0.0

    for route in routes:
        if route_gedekt(route, selected_stat, actieradius):
            covered_routes += 1
            somverkeer += route["verkeersvraag"]

    return covered_routes, somverkeer




