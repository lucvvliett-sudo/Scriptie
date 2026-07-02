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

def top_population_nodes(graph, top_n):
    """
    Geeft de knopen van de ``top_n`` gemeenten op basis van inwonersaantal
    """
    return sorted(
        graph.nodes,
        key=lambda node: graph.nodes[node].get("inwoners", 0),
        reverse=True,
    )[:top_n]


def path_distance(graph, path):
    """
    Telt de afstanden van de edges op het ``path`` van een OD-paar bij elkaar op
    """
    return sum(
        graph.edges[from_node, to_node]["distance_km"]
        for from_node, to_node in zip(path, path[1:])
    )


def cumulative_path_distances(graph, path):
    """
    Bereken per pad de cumulatieve afstand.
    Voor elke knooppositie in het pad wordt de afstand vanaf de oorsprong tot
    die positie berekend. De eerste waarde is altijd 0, omdat de afstand vanaf
    de oorsprong tot zichzelf gelijk is aan 0.
    """
    distances = [0]
    total = 0
    for from_node, to_node in zip(path, path[1:]):
        total += graph.edges[from_node, to_node]["distance_km"]
        distances.append(total)
    return distances



