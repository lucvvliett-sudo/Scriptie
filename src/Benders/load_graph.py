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


def load_graph(path):
        """
        Lees een gemeentegraaf in vanuit een GraphML-bestand.
        De graaf wordt ingelezen met NetworkX. Omdat GraphML-attributen vaak als
        strings worden opgeslagen, worden de relevante knoop- en edge-attributen
        expliciet omgezet naar numerieke waarden. Voor knopen gaat het om
        ``inwoners``, ``latitude`` en ``longitude``. Voor edges gaat het om
        ``distance_km``.

        Parameters
        ----------
        path : str
            Pad naar het GraphML-bestand waarin de gemeentegraaf is opgeslagen.

        Returns
        -------
        networkx.Graph
            Ingelezen gemeentegraaf met numerieke knoop- en edge-attributen.
            De knopen bevatten onder andere ``inwoners``, ``latitude`` en
            ``longitude``. De edges bevatten het attribuut ``distance_km``.
        """
    graph = nx.read_graphml(path)

    for _, data in graph.nodes(data=True):
        data["inwoners"] = int(float(data.get("inwoners", 0)))
        data["latitude"] = float(data.get("latitude", 0))
        data["longitude"] = float(data.get("longitude", 0))

    for _, _, data in graph.edges(data=True):
        data["distance_km"] = float(data.get("distance_km", 0))

    return graph