from rich.style import Style
from netext import ConsoleGraph
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from rich import print

import networkx as nx

from netext.properties.shape import JustContent

num_nodes = 6

g = nx.complete_graph(num_nodes)

nx.set_node_attributes(g, "just-content", "$shape")
nx.set_node_attributes(g, Style(color="purple", bold=True), "$content-style")

nx.set_edge_attributes(g, EdgeSegmentDrawingMode.BRAILLE, "$edge-segment-drawing-mode")

print(ConsoleGraph(g))
