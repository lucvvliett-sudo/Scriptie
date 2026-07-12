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


def master_probleem(nodes, routes, cuts, budget, initial_stat):
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
    nodes : list[str]
        Lijst met gemeentecodes die als kandidaatlocatie voor een laadstation
        kunnen dienen.
    routes : list[dict]
        Lijst met routedictionaries. Elke route bevat ten minste de sleutels
        ``id`` en ``raw_flow``.
    cuts : list[tuple[str, tuple[str, ...]]]
        Lijst met Benders-sneden. Elke snede bestaat uit een route-id en een
        verzameling kandidaatknopen die de route kunnen dekken.
    budget : int
        Maximaal aantal laadstations dat geplaatst mag worden.
    initial_stat : set[str] | None, optional
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
        for node in nodes}
    y = {
        route["id"]: pulp.LpVariable(f"y_{route['id']}", lowBound=0, upBound=1, cat="Continuous")
        for route in routes}

    totale_flow = sum(route["verkeersvraag"] for route in routes)
    if initial_stat is not None:
        for node, variable in x.items():
            variable.setInitialValue(1 if node in initial_stat else 0)
    if totale_flow >0:        
        model += pulp.lpSum(route["verkeersvraag"] * y[route["id"]] for route in routes)/totale_flow
    else: 
        model += 0

    model += pulp.lpSum(x.values()) <= budget

    for cut_index, (route_id, candidates) in enumerate(cuts):
        if candidates:
            model += (
                pulp.lpSum(x[node] for node in candidates) >= y[route_id],
                f"benders_cut_{cut_index}")
        else:
            model += y[route_id] <= 0, f"lege_benders_cut_{cut_index}"

    return model, x, y