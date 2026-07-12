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