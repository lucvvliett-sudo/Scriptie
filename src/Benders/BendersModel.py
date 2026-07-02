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
ORIGIN_DESTINATION_CAN_CHARGE = False


def load_graph(path):
    graph = nx.read_graphml(path)

    for _, data in graph.nodes(data=True):
        data["inwoners"] = int(float(data.get("inwoners", 0)))
        data["latitude"] = float(data.get("latitude", 0))
        data["longitude"] = float(data.get("longitude", 0))

    for _, _, data in graph.edges(data=True):
        data["distance_km"] = float(data.get("distance_km", 0))

    return graph


def top_population_nodes(graph, top_n):
    return sorted(
        graph.nodes,
        key=lambda node: graph.nodes[node].get("inwoners", 0),
        reverse=True,
    )[:top_n]


def path_distance(graph, path):
    return sum(
        graph.edges[from_node, to_node]["distance_km"]
        for from_node, to_node in zip(path, path[1:])
    )


def cumulative_path_distances(graph, path):
    distances = [0]
    total = 0
    for from_node, to_node in zip(path, path[1:]):
        total += graph.edges[from_node, to_node]["distance_km"]
        distances.append(total)
    return distances


def build_od_routes(graph, od_nodes):
    routes = []
    for route_index, (origin, destination) in enumerate(itertools.combinations(od_nodes, 2)):
        try:
            path = nx.shortest_path(
                graph,
                origin,
                destination,
                weight="distance_km",
            )
        except nx.NetworkXNoPath:
            continue

        distance = path_distance(graph, path)
        if distance <= 0:
            continue

        inwoners_origin = graph.nodes[origin]["inwoners"]
        inwoners_destination = graph.nodes[destination]["inwoners"]
        raw_flow = (inwoners_origin * inwoners_destination) / distance

        routes.append({
            "id": f"r{route_index}",
            "label": f"{origin}-{destination}",
            "origin": origin,
            "destination": destination,
            "path": path,
            "cumdist": cumulative_path_distances(graph, path),
            "distance_km": distance,
            "raw_flow": raw_flow,
        })

    return routes



def route_is_covered(route, selected_stations, vehicle_range_km):
    path = route["path"]
    cumdist = route["cumdist"]
    destination_index = len(path) - 1
    station_indices = {
        index
        for index, node in enumerate(path)
        if node in selected_stations
    }

    if ORIGIN_DESTINATION_CAN_CHARGE:
        station_indices.add(0)
        station_indices.add(destination_index)

    if not station_indices:
        return False

    half_range = vehicle_range_km / 2
    reachable_stations = set()

    for index in station_indices:
        distance_from_origin = cumdist[index]
        if distance_from_origin <= half_range:
            reachable_stations.add(index)

    if 0 in station_indices:
        reachable_stations.add(0)

    changed = True

    while changed:
        changed = False
        for index in sorted(station_indices):
            if index in reachable_stations:
                continue

            can_reach_index = any(
                cumdist[index] >= cumdist[reachable_index]
                and cumdist[index] - cumdist[reachable_index] <= vehicle_range_km
                for reachable_index in reachable_stations
            )
            if can_reach_index:
                reachable_stations.add(index)
                changed = True

    if destination_index in station_indices:
        return any(
            cumdist[destination_index] >= cumdist[reachable_index]
            and cumdist[destination_index] - cumdist[reachable_index] <= vehicle_range_km
            for reachable_index in reachable_stations
        )

    return any(
        cumdist[destination_index] >= cumdist[reachable_index]
        and cumdist[destination_index] - cumdist[reachable_index] <= half_range
        for reachable_index in reachable_stations
    )


def evaluate_route_coverage(routes, selected_stations, vehicle_range_km):
    covered_routes = 0
    actual_objective = 0.0

    for route in routes:
        if route_is_covered(route, selected_stations, vehicle_range_km):
            covered_routes += 1
            actual_objective += route["raw_flow"]

    return covered_routes, actual_objective


def route_subproblem_dual_cut(route, station_values, vehicle_range_km):
    path = route["path"]
    cumdist = route["cumdist"]
    destination_index = len(path) - 1
    half_range = vehicle_range_km / 2

    network = nx.DiGraph()
    source = "source"
    sink = "sink"
    inf_capacity = len(path) + 1

    for index, node in enumerate(path):
        node_capacity = float(station_values.get(node, 0.0))
        network.add_edge((index, "in"), (index, "out"), capacity=node_capacity)

    network.add_edge((destination_index, "out"), sink, capacity=inf_capacity)

    for to_index in range(1, len(path)):
        if cumdist[to_index] <= half_range:
            network.add_edge(source, (to_index, "in"), capacity=inf_capacity)

    network.add_edge(source, (0, "in"), capacity=inf_capacity)

    for from_index in range(len(path) - 1):
        for to_index in range(from_index + 1, len(path)):
            distance = cumdist[to_index] - cumdist[from_index]
            if distance > vehicle_range_km:
                continue

            network.add_edge(
                (from_index, "out"),
                (to_index, "in"),
                capacity=inf_capacity,
            )

            if to_index == destination_index and distance <= half_range:
                network.add_edge(
                    (from_index, "out"),
                    sink,
                    capacity=inf_capacity,
                )

    max_flow_value, _ = nx.maximum_flow(network, source, sink, capacity="capacity")
    if max_flow_value >= 1 - 1e-7:
        return max_flow_value, None

    min_cut_value, (reachable_side, unreachable_side) = nx.minimum_cut(
        network,
        source,
        sink
    )

    cut_nodes = []
    constant_capacity = 0.0
    for from_node in reachable_side:
        for to_node, edge_data in network[from_node].items():
            if to_node not in unreachable_side:
                continue

            is_node_capacity_edge = (
                isinstance(from_node, tuple)
                and isinstance(to_node, tuple)
                and from_node[1] == "in"
                and to_node[1] == "out"
                and from_node[0] == to_node[0]
            )
            if is_node_capacity_edge:
                route_index = from_node[0]
                cut_nodes.append(path[route_index])
            elif edge_data["capacity"] < inf_capacity:
                constant_capacity += edge_data["capacity"]

    if constant_capacity >= 1 - 1e-7:
        return min_cut_value, None

    return min_cut_value, sorted(set(cut_nodes))


def build_master_problem(station_nodes, routes, cuts, station_budget, initial_stations=None):
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
        model += pulp.lpSum(route["raw_flow"] * y[route["id"]] for route in routes)/total_flow
    else:
        model+=0
    
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


def solve_benders(graph, routes, station_budget, vehicle_range_km, max_iterations, max_run_time):
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
            time_limit = max(30, int(remaining_time * 0.3))
            gap_rel = 0.05
        elif iteration==2 or iteration==3:
            time_limit = max(30, int(remaining_time*0.2))
            gap_rel = 0.02
        else:
            time_limit= max(30, int(remaining_time*0.1))
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
        if status not in {"Optimal", "Not Solved"}:
            break

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


def main():
    graph = load_graph(GRAPH_PATH)
    for aantal_gemeenten in GEMEENTE_SCENARIOS:
        od_nodes = top_population_nodes(graph, aantal_gemeenten)
        routes = build_od_routes(graph, od_nodes)

        for station_budget in (60, 70):
            for vehicle_range_km in ACTIERADIUS_SCENARIOS:
                print("\n" + "=" * 60)
                print(
                    f"Top {aantal_gemeenten} gemeenten, "
                    f"stations={station_budget}, "
                    f"actieradius={vehicle_range_km}"
                )

                result = solve_benders(
                    graph,
                    routes,
                    station_budget,
                    vehicle_range_km,
                    max_iterations=max_iterations,
                    max_run_time=max_run_time,
                )

                print(f"Master Objective (top {aantal_gemeenten}): {result['objective']}")
                print(f"Actual Objective (top {aantal_gemeenten}): {result['actual_objective']}")
                print(f"Gedekt top {aantal_gemeenten}: {result['covered_routes']}/{len(routes)}")
                print("Stations:", sorted(result["selected_stations"]))
                print(f"geplaatste stations: {len(result['selected_stations'])}")
                print("Aantal cuts:", len(result["cuts"]))
                print(f"Iteraties: {result['iterations']}")
                print(f"Runtime: {result['runtime']:.1f} seconden")
                print(f"Status: {result['status']}")

if __name__ == "__main__":
    main()


