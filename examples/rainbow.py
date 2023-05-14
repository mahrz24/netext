# Minimum Spanning Tree Example
import itertools
import networkx as nx
from netext import TerminalGraph
from rich.style import Style
from rich import print
from netext.edge_rendering.modes import EdgeSegmentDrawingMode

from netext.edge_routing.modes import EdgeRoutingMode

G = nx.star_graph(10)

nx.set_node_attributes(G, Style(color="blue", bold=True), "$content-style")
nx.set_edge_attributes(G, EdgeRoutingMode.ORTHOGONAL, "$edge-routing-mode")
nx.set_edge_attributes(G, EdgeSegmentDrawingMode.BOX, "$edge-segment-drawing-mode")

nx.set_node_attributes(G, Style(color="green"), "$style")
nx.set_node_attributes(G, 2, "$margin")

# Rainbow colors
colors = [
    Style(color="red"),
    Style(color="orange3"),
    Style(color="bright_yellow"),
    Style(color="green"),
    Style(color="blue"),
    Style(color="turquoise2"),
    Style(color="violet"),
]

for edge, color in zip(G.edges, itertools.cycle(colors)):
    G.edges[edge]["$style"] = color

print(TerminalGraph(G))
