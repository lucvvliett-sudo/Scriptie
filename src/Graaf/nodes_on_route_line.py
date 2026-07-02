import cbsodata
import os
import math
import requests
import networkx as nx
from shapely.geometry import LineString, Point

LINE_CORRIDOR_TOLERANCE = 0.03
MAX_EDGE_LENGTH_KM = 30
PREVENT_CROSSING_EDGES = True

def nodes_on_route_line(graph, origin, destination, tolerance):
    """
        Bepaal welke knopen dicht bij de rechte lijn tussen twee knopen liggen.

        Voor een gegeven oorsprong en bestemming wordt een rechte lijn geconstrueerd
        op basis van de geografische coördinaten van beide knopen. Vervolgens wordt
        voor elke andere knoop in de graaf gecontroleerd of deze binnen een gegeven
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

    def node_position(node):
        """
            Geef de geografische positie van een knoop als ``(longitude, latitude)``.

            Parameters
            ----------
            node : str
                De CBS-gemeentecode van de knoop waarvan de positie wordt opgehaald.

            Returns
           -------
           tuple[float, float]
               Tuple bestaande uit lengtegraad en breedtegraad.
           """
        data = graph.nodes[node]
        return float(data["longitude"]), float(data["latitude"])

    line = LineString([node_position(origin), node_position(destination)])
    line_length = line.length
    intermediate_nodes = []

    for node in graph.nodes:
        if node in (origin, destination):
            continue
        point = Point(node_position(node))
        projection = line.project(point)
        if tolerance < projection < line_length - tolerance and point.distance(line) <= tolerance:
            intermediate_nodes.append((projection, node))

    return [node for _, node in sorted(intermediate_nodes)]