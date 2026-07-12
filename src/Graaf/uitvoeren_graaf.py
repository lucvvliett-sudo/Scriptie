import cbsodata
import os
import math
import requests
import networkx as nx
import matplotlib.pyplot as plt
from shapely.geometry import LineString, Point


TOLERANCE = 0.03
MAX_EDGE_LENGTE = 30
GEEN_KRUISENDE_EDGES = True

def main():
    """
    Voer de volledige constructie van het maken van de gemeentegraaf uit. Haal hierbij de
    inwonersaantallen en de gemeente_code op vanuit de CBS-dataset. Vervolgens wordt vanuit
    een centrumpunt de latitute en longitude uit de PDOK server gehaald. Hierna wordt de
    gemeentegraaf gegenereerd. Tot slot wordt de graaf opgeslagen in een GraphML bestand en
    wordt er voor de visuele representatie een Matplotlib gemaakt en een samenvatting geprint.

    Returns
    -------
    None

    """
    # Haal CBS-data op
    data = cbsodata.get_data(
        "86165NED",
        filters="startswith(WijkenEnBuurten,'GM')",
        select=["WijkenEnBuurten", "AantalInwoners_5"]
    )

    # Haal coordinaten op voor elke gemeente
    results = []
    for row in data:
        gemeente_code = row['WijkenEnBuurten']
        inwoners = row['AantalInwoners_5']
        lat, lon = get_gemeente_coords(gemeente_code)
        results.append({
            'gemeente_code': gemeente_code,
            'inwoners': inwoners,
            'latitude': lat,
            'longitude': lon
        })

    print(f"\nTotaal verwerkt: {len(results)} gemeenten")

    # Bouw graaf
    length_sorted_graph = build_gemeente_graph(results)

    print("\nLengte-gesorteerde graaf")
    if length_sorted_graph.number_of_nodes() > 0:
        print(f"Max degree: {max(dict(length_sorted_graph.degree()).values())}")
    print(f"Aantal nodes: {length_sorted_graph.number_of_nodes()}")
    print(f"Aantal edges: {length_sorted_graph.number_of_edges()}")

    if length_sorted_graph.number_of_edges() > 0:
        max_edge_length = max(
            edge_data["distance_km"]
            for _, _, edge_data in length_sorted_graph.edges(data=True)
        )
        print(f"Langste edge: {max_edge_length:.1f} km")

    # Sla graaf op
    output_path = os.path.join(os.path.dirname(__file__), "gemeente_graph_length_sorted.graphml")
    nx.write_graphml(length_sorted_graph, output_path)
    print(f"Graaf opgeslagen als: {output_path}")

    # Visualiseer graaf
    pos = {
        node: (float(data["longitude"]), float(data["latitude"]))
        for node, data in length_sorted_graph.nodes(data=True)
        if "longitude" in data and "latitude" in data
    }

    plt.figure(figsize=(10, 12))
    nx.draw(
        length_sorted_graph,
        pos=pos,
        node_size=2,
        width=0.3,
        arrows=False,
        with_labels=False,
    )
    plt.title("Lengte-gesorteerde NetworkX-graaf")
    plt.axis("equal")
    plt.show()


if __name__ == "__main__":
    main()