import cbsodata
import os
import math
import requests
import networkx as nx
import matplotlib.pyplot as plt
from shapely.geometry import LineString, Point


TOLERANCE = 0.03
MAX_EDGE_LENGTE = 30
GEEN_KRIUSENDE_EDGES = True


def haversine(lat1, lon1, lat2, lon2):
    """
    Bereken de hemelsbrede afstand tussen twee geografische coördinaten.
    De afstand wordt berekend met de Haversine-formule.

    Parameters
    ----------
    lat1 : float
        Breedtegraad van het eerste punt in decimale graden.
    lon1 : float
        Lengtegraad van het eerste punt in decimale graden.
    lat2 : float
        Breedtegraad van het tweede punt in decimale graden.
    lon2 : float
        Lengtegraad van het tweede punt in decimale graden.

    Returns
    -------
    float
        De hemelsbrede afstand tussen beide punten in kilometers.
    """
    radius = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def knoop_afstand(graph, from_node, to_node):
    """
    Bereken de hemelsbrede afstand tussen twee knopen in een graaf.
    De functie haalt de latitude en longitude van beide knopen uit de
    knoopattributen van de NetworkX-graaf. Vervolgens wordt de afstand tussen
    deze twee geografische punten berekend met de Haversine-formule.

    Parameters
    ----------
    graph : networkx.Graph
        Graaf waarvan de knopen de attributen ``latitude`` en ``longitude``
        bevatten.
    from_node : str
        CBS-gemeentecode van de eerste knoop waarvoor de afstand wordt berekend.
    to_node : str
        CBS-gemeentecode van de tweede knoop waarvoor de afstand wordt berekend.
    Returns
    -------
    float
        De hemelsbrede afstand tussen de twee knopen in kilometers.
    """
    van_data = graph.nodes[from_node]
    naar_data = graph.nodes[to_node]
    return haversine(
        float(van_data["latitude"]),
        float(van_data["longitude"]),
        float(naar_data["latitude"]),
        float(naar_data["longitude"]),
    )



def knopen_op_route(graph, origin, destination, tolerance):
    """
        Bepaal welke knopen dicht bij de rechte lijn tussen twee knopen liggen.
        Voor een gegeven oorsprong en bestemming wordt een rechte lijn geconstrueerd.
        Vervolgens wordt voor elke andere knoop in de graaf gecontroleerd of deze binnen een 
        tolerantieafstand van deze lijn ligt. Alleen knopen die daadwerkelijk tussen
        oorsprong en bestemming liggen, worden meegenomen.

        Parameters
        ----------
        graph : networkx.Graph
            Graaf waarvan de knopen de attributen ``latitude`` en ``longitude``
            bevatten.
        origin : str
            De CBS-gemeentecode van de oorsprongsknoop van de route.
        destination : hashable
            De CBS-gemeentecode van de bestemmingsknoop van de route.
        tolerance : float
            Maximale toegestane afstand tot de rechte lijn, gemeten in radialen
        Returns
        -------
        list
            Lijst met tussenliggende knopen die binnen de tolerantie van de rechte
            lijn liggen. De knopen worden geordend volgens hun projectie op de lijn
            van oorsprong naar bestemming.
        """
    
    def knoop_positie(node):
        """
            Geef de geografische positie van een knoop als ``(longitude, latitude)``.
        """
        data = graph.nodes[node]
        return float(data["longitude"]), float(data["latitude"])
    line = LineString([knoop_positie(origin), knoop_positie(destination)])
    line_length = line.length
    tussen_knopen = []

    for node in graph.nodes:
        if node in (origin, destination):
            continue
        point = Point(knoop_positie(node))
        projection = line.project(point)
        if tolerance < projection < line_length - tolerance and point.distance(line) <= tolerance:
            tussen_knopen.append((projection, node))

    return [node for _, node in sorted(tussen_knopen)]


def coordinaten_ophalen(gemeente_code):
    """
    Haal de centrumcoördinaten van een gemeente op via de PDOK Locatieserver.
    De functie zoekt op basis van een gemeentecode naar een gemeenteobject in
    de PDOK Locatieserver. Wanneer een resultaat wordt gevonden, wordt het
    geografische middelpunt uit het veld ``centroide_ll`` gehaald. Dit punt
    wordt omgezet naar latitude en longitude.

    Parameters
    ----------
    gemeente_code : str
        CBS-gemeentecode waarmee de gemeente wordt opgezocht.

    Returns
    -------
    tuple[float,float]
        Tuple ``(latitude, longitude)`` wanneer coördinaten worden gevonden.
        Als geen geldig resultaat beschikbaar is, wordt ``(None, None)``
        teruggegeven.
    """

    url = "https://api.pdok.nl/bzk/locatieserver/search/v3_1/free"
    params = {
        "q": gemeente_code,
        "fq": "type:gemeente",
        "fl": "gemeentenaam,centroide_ll",
        "rows": 1,
    }
    response = requests.get(url, params=params, timeout=10)
    data = response.json()
    if data['response']['numFound'] > 0:
        centroide = data['response']['docs'][0].get('centroide_ll', '')
        if centroide.startswith('POINT('):
            coords = centroide.replace('POINT(', '').replace(')', '').split()
            return float(coords[1]), float(coords[0])
    return None, None


def bouw_gemeente_graph(results, tolerance=TOLERANCE):
    """
    Bouw een gemeentegraaf op basis van inwonersaantallen en coördinaten.
    Eerst worden alle gemeenten als knopen toegevoegd aan een NetworkX-graaf. 
    Daarna worden kandidaatverbindingen bepaald door voor elk paar gemeenten 
    te kijken welke tussenliggende knopen
    dicht bij de rechte lijn tussen beide gemeenten liggen. Een kandidaatroute
    wordt alleen gebruikt als alle opeenvolgende segmenten korter zijn dan de
    maximale toegestane segmentlengte. De resulterende graaf bevat dezelfde knopen
    als de initiële gemeentegraaf, maar alleen de geselecteerde verbindingen.
    Deze verbindingen worden in oplopende volgorde van lengte toegevoegd. Indien
    ``GEEN_KRIUSENDE_EDGES`` gelijk is aan ``True``, worden verbindingen die
    bestaande verbindingen kruisen overgeslagen.

    results: list[dict]
        Lijst met gemeentelijke gegevens per knoop. Hierin zijn ''gemeente_code'' ''latitude'',
        ''longitude'', ''inwoners'' opgeslagen.
    tolerance: float
        Maximale afstand waarbinnen een knoop als tussenliggende knoop op een
        rechte route tussen twee gemeenten wordt beschouwd. De standaardwaarde
        is ``TOLERANCE``

    Returns
    -------
    networkx.Graph
        Ongerichte gemeentegraaf met gemeenten als knopen en geselecteerde
        verbindingen als edges. Elke knoop bevat de attributen ``gemeente_code``, ``inwoners``,
        ``latitude`` en ``longitude``. Elke edge bevat het attribuut
        ``distance_km``, waarin de hemelsbrede afstand tussen de twee verbonden
        gemeenten in kilometers is opgeslagen.

    """
    graph = nx.Graph()
    for row in results:
        if row["latitude"] is not None and row["longitude"] is not None:
            graph.add_node(
                row["gemeente_code"],
                inwoners=row["inwoners"],
                latitude=row["latitude"],
                longitude=row["longitude"],
            )
    
    nodes = list(graph.nodes)
    candidates = {}

    # Verzamel alle kandidaat-segmenten tussen alle knopenparen
    for origin_index, origin in enumerate(nodes):
        for destination in nodes[origin_index + 1:]:
            tussen_knopen = knopen_op_route(graph, origin, destination, tolerance)
            path_nodes = [origin, *tussen_knopen, destination]

            # Controleer of alle segmenten kort genoeg zijn
            valid = all(
                knoop_afstand(graph, path_nodes[i], path_nodes[i + 1]) <= MAX_EDGE_LENGTE
                for i in range(len(path_nodes) - 1)
            )
            if not valid:
                continue

            # Voeg kandidaat-edges toe
            for from_node, to_node in zip(path_nodes, path_nodes[1:]):
                if from_node == to_node:
                    continue
                edge_key = frozenset((from_node, to_node))
                if edge_key not in candidates:
                    candidates[edge_key] = knoop_afstand(graph, from_node, to_node)

    # Voeg edges toe in volgorde van lengte
    route_graph = nx.Graph()
    route_graph.add_nodes_from(graph.nodes(data=True))
    def knoop_positie(node):
        """
            Geef de geografische positie van een knoop als ``(longitude, latitude)``.
        """
        data = graph.nodes[node]
        return float(data["longitude"]), float(data["latitude"])
    for (from_node, to_node), distance in sorted(candidates.items(), key=lambda x: x[1]):
        if route_graph.has_edge(from_node, to_node):
            continue
        
        # Voeg edge toe als hij kort genoeg is
        if distance <= MAX_EDGE_LENGTE:
            if GEEN_KRIUSENDE_EDGES:
                # Controleer of edge bestaande edges kruist
                new_line = LineString([knoop_positie(from_node), knoop_positie(to_node)])
                crosses = False
                for edge_from, edge_to in route_graph.edges:
                    if from_node in (edge_from, edge_to) or to_node in (edge_from, edge_to):
                        continue
                    existing_line = LineString([knoop_positie(edge_from), knoop_positie(edge_to)])
                    if new_line.crosses(existing_line):
                        crosses = True
                        break
                if crosses:
                    continue
            
            route_graph.add_edge(from_node, to_node, distance_km=distance)

    return route_graph


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
        lat, lon = coordinaten_ophalen(gemeente_code)
        results.append({
            'gemeente_code': gemeente_code,
            'inwoners': inwoners,
            'latitude': lat,
            'longitude': lon
        })

    print(f"\nTotaal verwerkt: {len(results)} gemeenten")

    # Bouw graaf
    length_sorted_graph = bouw_gemeente_graph(results)
    
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
