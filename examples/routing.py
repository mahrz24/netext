from netext import TerminalGraph
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_routing.modes import EdgeRoutingMode
from netext.layout_engines.static import StaticLayout
from rich import print

import networkx as nx

g = nx.Graph()
g.add_node(1, **{"$x": 1, "$y": 1})
g.add_node(2, **{"$x": 1, "$y": 10})
g.add_node(3, **{"$x": 10, "$y": 10})

g.add_edge(
    1,
    3,
    **{
        "$edge-routing-mode": EdgeRoutingMode.orthogonal,
        "$edge-segment-drawing-mode": EdgeSegmentDrawingMode.box,
    }
)

print(TerminalGraph(g, layout_engine=StaticLayout()))
