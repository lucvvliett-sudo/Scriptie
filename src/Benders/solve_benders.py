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


def solve_benders(graph, routes, station_budget, vehicle_range_km, max_iterations, max_run_time):
    """
    Los het snellaadlocatieprobleem op met logic-based Benders-decompositie.

    In elke iteratie wordt eerst het masterprobleem opgelost. De oplossing van
    het masterprobleem bepaalt welke laadstations zijn geselecteerd en welke
    routes voorlopig als gedekt worden beschouwd. Voor elke geselecteerde route
    wordt vervolgens een route-subprobleem opgelost. Als een route volgens het
    subprobleem niet werkelijk gedekt is, wordt een nieuwe Benders-snede
    toegevoegd.

    Het algoritme stopt wanneer er in een iteratie geen nieuwe sneden worden
    gevonden, wanneer het maximale aantal iteraties is bereikt, wanneer de
    tijdslimiet wordt overschreden, of wanneer de solver een status teruggeeft
    waarmee niet verder wordt gegaan.

    Parameters
    ----------
    graph : networkx.Graph
        Gemeentegraaf waarop het locatieprobleem wordt opgelost.
    routes : list[dict]
        Lijst met OD-routes waarvoor routedekking wordt gemaximaliseerd.
    station_budget : int
        Maximaal aantal laadstations dat geplaatst mag worden.
    vehicle_range_km : float
        Actieradius van het voertuig in kilometers.
    max_iterations : int
        Maximaal aantal Benders-iteraties.
    max_run_time : float
        Maximale rekentijd in seconden.

    Returns
    -------
    dict
        Dictionary met de resultaten van het Benders-algoritme. De belangrijkste
        sleutels zijn:

        ``objective``
            Genormaliseerde doelfunctiewaarde van het laatste masterprobleem.
        ``selected_stations``
            Verzameling geselecteerde laadstationlocaties.
        ``covered_routes``
            Aantal routes dat daadwerkelijk gedekt is.
        ``routes``
            Lijst met gebruikte OD-routes.
        ``cuts``
            Lijst met gegenereerde Benders-sneden.
        ``iterations``
            Aantal uitgevoerde Benders-iteraties.
        ``runtime``
            Totale rekentijd in seconden.
        ``status``
            Solverstatus of stopstatus van het algoritme.
        ``actual_objective``
            Totale ruwe verkeersvraag van de daadwerkelijk gedekte routes.
    """
    cuts = []
    cut_keys = set()
    station_nodes = sorted({node for route in routes for node in route["path"]})
    start_time = time.perf_counter()
    objective_value = 0.0
    actual_objective = 0.0
    status = "UNKNOWN"
    selected_stations = set()
    covered_routes = 0
    iteration = 0

    for iteration in range(1, max_iterations + 1):
        elapsed = time.perf_counter() - start_time
        if elapsed >= max_run_time:
            print(f"Tijdslimiet bereikt na {elapsed:.1f} seconden.")
            status = "TIME_LIMIT"
            break

        remaining_time = max_run_time - elapsed

        if iteration == 1:
            time_limit = max(30, int(remaining_time * 0.1))
            gap_rel = 0.05
        elif iteration==2 or iteration==3:
            time_limit = max(30, int(remaining_time* 0.2))
            gap_rel = 0.02
        else:
            time_limit= max(30, int(remaning_time*0.3))
            gap_rel=0.01

        solver = pulp.PULP_CBC_CMD(
            msg=False,
            timeLimit=time_limit,
            gapRel=gap_rel,
            threads=4,
            warmStart=True,
        )

        model, x, y = build_master_problem(
            station_nodes,
            routes,
            cuts,
            station_budget,
            initial_stations=selected_stations,
        )
        model.solve(solver)

        status = pulp.LpStatus[model.status]

        selected_stations = {
            node
            for node, variable in x.items()
            if pulp.value(variable) > 0.5
        }
        station_values = {
            node: pulp.value(variable) or 0.0
            for node, variable in x.items()
        }

        new_cuts = []
        for route in routes:
            route_selected = (pulp.value(y[route["id"]]) or 0.0) > 0.5
            if not route_selected:
                continue

            subproblem_value, candidate_nodes = route_subproblem_dual_cut(
                route,
                station_values,
                vehicle_range_km
            )
            if subproblem_value >= 1 - 1e-7:
                continue

            candidate_nodes = tuple(candidate_nodes or ())
            cut = (route["id"], candidate_nodes)
            if cut not in cut_keys:
                cut_keys.add(cut)
                new_cuts.append(cut)

        objective_value = pulp.value(model.objective) or 0.0
        covered_routes, actual_objective = evaluate_route_coverage(
            routes,
            selected_stations,
            vehicle_range_km,
        )

        if not new_cuts:
            elapsed = time.perf_counter() - start_time
            return {
                "objective": objective_value,
                "selected_stations": selected_stations,
                "covered_routes": covered_routes,
                "routes": routes,
                "cuts": cuts,
                "iterations": iteration,
                "runtime": elapsed,
                "status": status,
                "actual_objective": actual_objective,
            }

        cuts.extend(new_cuts)

    elapsed = time.perf_counter() - start_time
    return {
        "objective": objective_value,
        "selected_stations": selected_stations,
        "covered_routes": covered_routes,
        "routes": routes,
        "cuts": cuts,
        "iterations": iteration,
        "runtime": elapsed,
        "status": status,
        "actual_objective": actual_objective,
    }
