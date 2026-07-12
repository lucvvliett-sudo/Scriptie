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

def top_gemeenten(graph, top_n):
    """
    Geeft de knopen van de ``top_n`` gemeenten op basis van inwonersaantal
    """
    return sorted(
        graph.nodes,
        key=lambda node: graph.nodes[node].get("inwoners", 0),
        reverse=True,
    )[:top_n]

def main():
    """
    De functie leest eerst de gemeentegraaf in en doorloopt daarna de ingestelde
    scenario's voor het aantal gemeenten, het stationsbudget en de actieradius.
    Voor elk scenario worden OD-routes opgebouwd, wordt het Benders-algoritme
    uitgevoerd en worden de belangrijkste resultaten naar de terminal geprint.

    Returns
    -------
    None
        Deze functie geeft geen waarde terug. De resultaten worden geprint naar
        de terminal.
        """
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