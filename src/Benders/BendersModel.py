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


def laad_graph(path):
    graph = nx.read_graphml(path)

    for _, data in graph.nodes(data=True):
        data["inwoners"] = int(float(data.get("inwoners", 0)))
        data["latitude"] = float(data.get("latitude", 0))
        data["longitude"] = float(data.get("longitude", 0))

    for _, _, data in graph.edges(data=True):
        data["distance_km"] = float(data.get("distance_km", 0))

    return graph


def top_gemeenten(graph, top_n):
    return sorted(
        graph.nodes,
        key=lambda node: graph.nodes[node].get("inwoners", 0),
        reverse=True,
    )[:top_n]

def OD_routes(graph, od_nodes):
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


def route_gedekt(route, selected_stat, actieradius):
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
    covered_routes = 0
    somverkeer = 0.0

    for route in routes:
        if route_gedekt(route, selected_stat, actieradius):
            covered_routes += 1
            somverkeer += route["verkeersvraag"]

    return covered_routes, somverkeer


def subprobleem_en_cuts(route, x_waarden, actieradius):
    path = route["path"]
    cumdist = route["cumdist"]
    half_range = actieradius / 2

    network = nx.DiGraph()
    source = "source"
    sink = "sink"
    inf_cap = len(path) + 1

    for i, node in enumerate(path):
        node_cap = float(x_waarden.get(node, 0.0))
        network.add_edge((i, "in"), (i, "uit"), capacity=node_cap)

    des_index = len(path) - 1
    network.add_edge((des_index, "uit"), sink, capacity=inf_cap)

    for to_index in range(1, len(path)):
        if cumdist[to_index] <= half_range:
            network.add_edge(source, (to_index, "in"), capacity=inf_cap)

    network.add_edge(source, (0, "in"), capacity=inf_cap)

    for from_index in range(len(path) - 1):
        for to_index in range(from_index + 1, len(path)):
            distance = cumdist[to_index] - cumdist[from_index]
            if distance > actieradius:
                continue

            network.add_edge(
                (from_index, "uit"),
                (to_index, "in"),
                capacity=inf_cap)

            if to_index == des_index and distance <= half_range:
                network.add_edge(
                    (from_index, "uit"),
                    sink,
                    capacity=inf_cap)
    #Hier wordt de maximale flow berekend met networkx.
    max_flow_value, _ = nx.maximum_flow(network, source, sink, capacity="capacity")
    if max_flow_value >= 1 - 1e-7:
        return max_flow_value, None

    #Hier wordt de minimale cut berekend met networkx.
    min_cut_value, (s_side, t_side) = nx.minimum_cut(
        network,
        source,
        sink)

    cut_nodes = []
    const_cap = 0

    for from_node in s_side:
        for to_node, edge_data in network[from_node].items():
            if to_node not in t_side:
                continue
#Hier wordt gecontroleerd of de edge tussen in en uit knoop zit en niet de sink of source is
            cut_edges = (
                isinstance(from_node, tuple)
                and isinstance(to_node, tuple)
                and from_node[1] == "in"
                and to_node[1] == "uit"
                and from_node[0] == to_node[0])

            if cut_edges:
                route_index = from_node[0]
                cut_nodes.append(path[route_index])
            elif edge_data["capacity"] < inf_cap:
                const_cap += edge_data["capacity"]

    if const_cap >= 1 - 1e-7:
        return min_cut_value, None

    return min_cut_value, sorted(set(cut_nodes))


def master_probleem(nodes, routes, cuts, budget, initial_stat):
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


def run_benders(routes, budget, actieradius, max_iterations, max_runtime):
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


def main():
    graph = laad_graph(GRAPH_PATH)
    for aantal_gemeenten in GEMEENTE_SCENARIOS:
        od_nodes = top_gemeenten(graph, aantal_gemeenten)
        routes = OD_routes(graph, od_nodes)

        #pas hier de stationbudget aan voor gewenste aantal te plaatsen stations
        for station_budget in range(1,11):
            for actieradius in ACTIERADIUS_SCENARIOS:
                print("\n" + "=" * 60)
                print(
                    f"Top {aantal_gemeenten} gemeenten, "
                    f"stations={station_budget}, "
                    f"actieradius={actieradius}")

                result = run_benders(
                    routes,
                    station_budget,
                    actieradius,
                    max_iterations=max_iterations,
                    max_runtime=max_runtime)

                print(f"Master Objective (top {aantal_gemeenten}): {result['objective']}")
                print(f"Som verkeersvraag (top {aantal_gemeenten}): {result['sum_obj']}")
                print(f"Gedekt top {aantal_gemeenten}: {result['covered_routes']}/{len(routes)}")
                print("Stations:", sorted(result["selected_stations"]))
                print(f"geplaatste stations: {len(result['selected_stations'])}")
                print("Aantal cuts:", len(result["cuts"]))
                print(f"Iteraties: {result['iterations']}")
                print(f"Runtime: {result['runtime']:.1f} seconden")
                print(f"Status: {result['status']}")

if __name__ == "__main__":
    main()


