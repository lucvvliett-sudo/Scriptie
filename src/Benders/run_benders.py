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

def run_benders(routes, budget, actieradius, max_iterations, max_runtime):
    """
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
    routes : list[dict]
        Lijst met OD-routes waarvoor routedekking wordt gemaximaliseerd.
    budget : int
        Maximaal aantal laadstations dat geplaatst mag worden.
    actieradius : float
        Actieradius van het voertuig in kilometers.
    max_iterations : int
        Maximaal aantal Benders-iteraties.
    max_runtime : float
        Maximale rekentijd in seconden.

    Returns
    -------
    dict
        Dictionary met de resultaten van het Benders-algoritme. 
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
        ``sum_obj``
            Totale ruwe verkeersvraag van de daadwerkelijk gedekte routes.
    """
    cuts = []
    cut_check = set()
    nodes = sorted({node for route in routes for node in route["path"]})
    start = time.perf_counter()
    objective = 0.0
    sum_obj= 0.0
    status = "UNKNOWN"
    selected_stat= set()
    covered_routes = 0
    iteration = 0

    for iteration in range(1, max_iterations + 1):
        elapsed = time.perf_counter() - start
        if elapsed >= max_runtime:
            print(f"Tijdslimiet bereikt na {elapsed:.1f} seconden.")
            status = "TIME_LIMIT"
            break

        remaining= max_runtime - elapsed
        #Per model kan hier de tijdslimiet en de gap worden aangepast per iteratie
        if iteration == 1:
            time_limit = max(30, int(remaining * 0.3))
            gap_rel = 0.05
        elif iteration==2 or iteration==3:
            time_limit = max(30, int(remaining * 0.2))
            gap_rel = 0.02
        else:
            time_limit= max(30, int(remaining*0.1))
            gap_rel=0.01
        
        solver = pulp.PULP_CBC_CMD(
            msg=False,
            timeLimit=time_limit,
            gapRel=gap_rel,
            threads=4,
            warmStart=True)

        model, x, y = master_probleem(
            nodes,
            routes,
            cuts,
            budget,
            initial_stat=selected_stat)
        
        model.solve(solver)

        status = pulp.LpStatus[model.status]
        if status not in {"Optimal", "Not Solved"}:
            break

        selected_stat = {
            node
            for node, variable in x.items()
            if pulp.value(variable) > 0.5}
        stat_val = {
            node: pulp.value(variable) or 0.0
            for node, variable in x.items()}

        new_cuts = []
        for route in routes:
            check_gedekt = pulp.value(y[route["id"]] or 0.0) > 0.5
            if not check_gedekt:
                continue
            
            #Check voor het subprobleem of de route gedekt is  met de huidige stationwaarden en actieradius. 
            #Als de waarde van het subprobleem groter is dan 1, wordt er geen cut toegevoegd.
            sub_waarde, kandidaat = subprobleem_en_cuts(
                route,
                stat_val,
                actieradius)
            
            
            if sub_waarde >= 1 - 1e-7:
                continue

            kandidaat = tuple(kandidaat or ()) 
            cut = (route["id"], kandidaat)
            if cut not in cut_check:
                cut_check.add(cut)
                new_cuts.append(cut)

        objective = pulp.value(model.objective) or 0.0
        covered_routes, sum_obj = info_dekking(
            routes,
            selected_stat,
            actieradius,
        )

        if not new_cuts:
            elapsed = time.perf_counter() - start
            return {
                "objective": objective,
                "selected_stations": selected_stat,
                "covered_routes": covered_routes,
                "routes": routes,
                "cuts": cuts,
                "iterations": iteration,
                "runtime": elapsed,
                "status": status,
                "sum_obj": sum_obj}

        cuts.extend(new_cuts)

    elapsed = time.perf_counter() - start
    return {
        "objective": objective,
        "selected_stations": selected_stat,
        "covered_routes": covered_routes,
        "routes": routes,
        "cuts": cuts,
        "iterations": iteration,
        "runtime": elapsed,
        "status": status,
        "sum_obj": sum_obj}
