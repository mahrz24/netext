from netext import ConsoleGraph
from rich import print
from rich.style import Style
from netext.edge_rendering.arrow_tips import ArrowTip
from netext.edge_routing.modes import EdgeRoutingMode
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
import networkx as nx

G = nx.binomial_tree(3)

nx.set_node_attributes(G, Style(color="blue", bold=True), "$content-style")
nx.set_node_attributes(G, Style(color="green"), "$style")

nx.set_edge_attributes(G, ArrowTip.ARROW, "$start-arrow-tip")
nx.set_edge_attributes(G, EdgeRoutingMode.ORTHOGONAL, "$edge-routing-mode")
nx.set_edge_attributes(G, EdgeSegmentDrawingMode.BOX_ROUNDED, "$edge-segment-drawing-mode")
nx.set_edge_attributes(G, Style(color="red"), "$style")

print(ConsoleGraph(G))
