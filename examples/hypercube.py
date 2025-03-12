# Minimum Spanning Tree Example
import networkx as nx
from netext import ConsoleGraph, EdgeRoutingMode, EdgeSegmentDrawingMode
from rich.style import Style
from rich import print

from netext.properties.arrow_tips import ArrowTip
import colorsys

G = nx.hypercube_graph(4)

nx.set_node_attributes(G, Style(color="blue", bold=True), "$content-style")
nx.set_node_attributes(G, Style(color="green"), "$style")
nx.set_node_attributes(G, True, "$slots")

nx.set_edge_attributes(G, EdgeRoutingMode.ORTHOGONAL, "$edge-routing-mode")
nx.set_edge_attributes(G, EdgeSegmentDrawingMode.BOX_ROUNDED, "$edge-segment-drawing-mode")

nx.set_edge_attributes(G, ArrowTip.ARROW, "$end-arrow-tip")
nx.set_edge_attributes(G, ArrowTip.ARROW, "$start-arrow-tip")

num_edges = G.number_of_edges()
edge_colors = []
for i in range(num_edges):
    hue = i / num_edges
    r, g, b = colorsys.hsv_to_rgb(hue, 1, 1)
    edge_colors.append(f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}")

for idx, (u, v) in enumerate(G.edges()):
    G[u][v]["$style"] = Style(color=edge_colors[idx])

print(ConsoleGraph(G))
