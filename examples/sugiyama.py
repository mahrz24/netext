from netext import ConsoleGraph
from rich import print

import networkx as nx

from netext.edge_rendering.arrow_tips import ArrowTip
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_routing.modes import EdgeRoutingMode

# g = nx.DiGraph()
# g.add_node(0)
# g.add_node(1)
# g.add_edge(0, 1)

# print(ConsoleGraph(g))

# g = nx.DiGraph()
# g.add_node(0)
# g.add_node(1)
# g.add_node(2)
# g.add_edge(0, 1)
# g.add_edge(0, 2)

# print(ConsoleGraph(g))

# g = nx.DiGraph()
# g.add_node(0)
# g.add_node(1)
# g.add_node(2)
# g.add_edge(0, 1)
# g.add_edge(0, 2)
# g.add_edge(1, 2)

# print(ConsoleGraph(g))

g = nx.DiGraph()
g.add_node(0)
g.add_node(1)
g.add_node(2)
g.add_node(3)
# g.add_node(4)
# g.add_node(5)

g.add_edge(0,1)
g.add_edge(1,2)
g.add_edge(2,3)
g.add_edge(3,0)

# g.add_edge(3,4)
# g.add_edge(4,5)
# g.add_edge(5,0)

nx.set_edge_attributes(g, ArrowTip.ARROW, "$end-arrow-tip")
nx.set_edge_attributes(g, EdgeRoutingMode.ORTHOGONAL, "$edge-routing-mode")
nx.set_edge_attributes(g, EdgeSegmentDrawingMode.BOX, "$edge-segment-drawing-mode")


print(ConsoleGraph(g))
