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

def main():
        """
        Voer de analyses uit voor de ingestelde scenario's.
        De functie leest eerst de gemeentegraaf in en doorloopt daarna de ingestelde
        scenario's voor het aantal gemeenten, het stationsbudget en de actieradius.
        Voor elk scenario worden OD-routes opgebouwd, wordt het Benders-algoritme
        uitgevoerd en worden de belangrijkste resultaten naar de console geprint.

        De resultaten omvatten onder andere percentage van de maximale doelfunctie, de daadwerkelijke
        gedekte verkeersvraag, het aantal gedekte routes, de geselecteerde stations,
        het aantal gegenereerde Benders-sneden, het aantal iteraties, de rekentijd
        en de solverstatus.

        Returns
        -------
        None
            Deze functie geeft geen waarde terug. De resultaten worden geprint naar
            de console.
        """
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