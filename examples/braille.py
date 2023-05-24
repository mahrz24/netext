from rich.style import Style
from netext import TerminalGraph
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.node_rasterizer import JustContent
from rich import print

import networkx as nx

num_nodes = 6

g = nx.complete_graph(num_nodes)

nx.set_node_attributes(g, JustContent(), "$shape")
nx.set_node_attributes(g, Style(color="purple", bold=True), "$content-style")

nx.set_edge_attributes(g, EdgeSegmentDrawingMode.BRAILLE, "$edge-segment-drawing-mode")

print(TerminalGraph(g))
