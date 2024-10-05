# Minimum Spanning Tree Example
from netext import ConsoleGraph
from netext.edge_rendering.arrow_tips import ArrowTip
from netext.edge_routing.modes import EdgeRoutingMode
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from rich.style import Style
import networkx as nx

from rich import print

# Create a graph
G = nx.Graph()
G.add_edges_from(
    [
        (0, 1, {"weight": 4}),
        (0, 7, {"weight": 8}),
        (1, 7, {"weight": 11}),
        (1, 2, {"weight": 8}),
        (2, 8, {"weight": 2}),
        (2, 5, {"weight": 4}),
        (2, 3, {"weight": 7}),
        (3, 4, {"weight": 9}),
        (3, 5, {"weight": 14}),
        (4, 5, {"weight": 10}),
        (5, 6, {"weight": 2}),
        (6, 8, {"weight": 6}),
        (7, 8, {"weight": 7}),
    ]
)

# Find the minimum spanning tree
T = nx.minimum_spanning_tree(G)



nx.set_node_attributes(G, Style(color="blue", bold=True), "$content-style")
nx.set_node_attributes(G, Style(color="green"), "$style")
nx.set_node_attributes(G, True, "$show")

nx.set_edge_attributes(G, ArrowTip.ARROW, "$end-arrow-tip")
nx.set_edge_attributes(G, EdgeRoutingMode.ORTHOGONAL, "$edge-routing-mode")
nx.set_edge_attributes(G, EdgeSegmentDrawingMode.BOX, "$edge-segment-drawing-mode")

for edge in G.edges:
    if edge in T.edges:
        G.edges[edge]["$style"] = Style(color="red")
    else:
        G.edges[edge]["$style"] = Style(color="blue")

print(ConsoleGraph(G))
