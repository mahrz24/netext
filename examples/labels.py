from netext import ConsoleGraph
from netext.edge_rendering.arrow_tips import ArrowTip
from netext.edge_routing.modes import EdgeRoutingMode
from netext.edge_rendering.modes import EdgeSegmentDrawingMode

from rich import print

import networkx as nx

g = nx.Graph()
g.add_node("Chunky")
g.add_node("Bacon")
g.add_edge("Chunky", "Bacon", **{"$label": "Yum yuuuum!"})

nx.set_edge_attributes(g, ArrowTip.ARROW, "$end-arrow-tip")
nx.set_edge_attributes(g, EdgeRoutingMode.ORTHOGONAL, "$edge-routing-mode")
nx.set_edge_attributes(g, EdgeSegmentDrawingMode.BOX, "$edge-segment-drawing-mode")

print(ConsoleGraph(g))
