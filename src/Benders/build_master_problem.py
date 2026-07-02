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


def build_master_problem(station_nodes, routes, cuts, station_budget, initial_stations=None):
    """
    Maak het masterprobleem voor de Benders decompositie aan de hand van de pulp package.
    Het masterprobleem kiest laadstationlocaties en routevariabelen. Voor elke
    kandidaatlocatie wordt een binaire variabele ``x`` aangemaakt. Voor elke
    route wordt een continue variabele ``y`` tussen 0 en 1 aangemaakt, die
    aangeeft of de route door het masterprobleem als gedekt wordt beschouwd.

    De doelfunctie maximaliseert de genormaliseerde gedekte verkeersvraag.
    Daarnaast bevat het model een budgetrestrictie op het aantal te plaatsen
    laadstations en alle Benders-sneden die tot dat moment zijn gegenereerd.

     Parameters
    ----------
    station_nodes : list[str]
        Lijst met gemeentecodes die als kandidaatlocatie voor een laadstation
        kunnen dienen.
    routes : list[dict]
        Lijst met routedictionaries. Elke route bevat ten minste de sleutels
        ``id`` en ``raw_flow``.
    cuts : list[tuple[str, tuple[str, ...]]]
        Lijst met Benders-sneden. Elke snede bestaat uit een route-id en een
        verzameling kandidaatknopen die de route kunnen dekken.
    station_budget : int
        Maximaal aantal laadstations dat geplaatst mag worden.
    initial_stations : set[str] | None, optional
        Eventuele startoplossing voor de stationvariabelen. Wanneer deze wordt
        meegegeven, worden de beginwaarden van de ``x``-variabelen ingesteld
        op basis van deze stationselectie.

    Returns
    -------
    tuple[pulp.LpProblem, dict[str, pulp.LpVariable], dict[str, pulp.LpVariable]]
        Tuple ``(model, x, y)`` bestaande uit het PuLP-masterprobleem, de
        dictionary met stationvariabelen en de dictionary met routevariabelen.
    """
    model = pulp.LpProblem("FRLM_Benders_Master", pulp.LpMaximize)

    x = {
        node: pulp.LpVariable(f"x_{node}", cat="Binary")
        for node in station_nodes
    }
    y = {
        route["id"]: pulp.LpVariable(f"y_{route['id']}", lowBound=0, upBound=1, cat="Continuous")
        for route in routes
    }

    total_flow = sum(route["raw_flow"] for route in routes)
    if initial_stations is not None:
        for node, variable in x.items():
            variable.setInitialValue(1 if node in initial_stations else 0)
    if total_flow > 0:
        model += pulp.lpSum(route["raw_flow"] * y[route["id"]] for route in routes) / total_flow
    else:
        model += 0

    model += pulp.lpSum(x.values()) <= station_budget

    for cut_index, (route_id, candidate_nodes) in enumerate(cuts):
        if candidate_nodes:
            model += (
                pulp.lpSum(x[node] for node in candidate_nodes) >= y[route_id],
                f"benders_cut_{cut_index}",
            )
        else:
            model += y[route_id] <= 0, f"benders_no_cover_cut_{cut_index}"

    return model, x, y