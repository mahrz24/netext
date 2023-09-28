# Minimum Spanning Tree Example
import networkx as nx
from netext import ConsoleGraph
from netext.edge_routing.modes import EdgeRoutingMode
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from rich.style import Style
from rich import print

G = nx.hypercube_graph(4)

nx.set_node_attributes(G, Style(color="blue", bold=True), "$content-style")
nx.set_node_attributes(G, Style(color="green"), "$style")

nx.set_edge_attributes(G, EdgeRoutingMode.ORTHOGONAL, "$edge-routing-mode")
nx.set_edge_attributes(
    G, EdgeSegmentDrawingMode.BOX_ROUNDED, "$edge-segment-drawing-mode"
)

print(ConsoleGraph(G))
