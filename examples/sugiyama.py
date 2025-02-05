from netext import ConsoleGraph, ArrowTip, EdgeSegmentDrawingMode, EdgeRoutingMode
from rich import print

import networkx as nx

from netext.layout_engines import LayoutDirection, SugiyamaLayout

g = nx.binomial_tree(5)

nx.set_edge_attributes(g, ArrowTip.ARROW, "$end-arrow-tip")
nx.set_edge_attributes(g, EdgeRoutingMode.ORTHOGONAL, "$edge-routing-mode")
nx.set_edge_attributes(g, EdgeSegmentDrawingMode.BOX, "$edge-segment-drawing-mode")

layout = SugiyamaLayout(direction=LayoutDirection.LEFT_RIGHT)

print(ConsoleGraph(g, layout_engine=layout))
