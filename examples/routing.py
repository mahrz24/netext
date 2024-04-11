from netext import ConsoleGraph
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_routing.modes import EdgeRoutingMode
from netext.layout_engines.static import StaticLayout
from rich import print
from rich.style import Style

import networkx as nx

g = nx.Graph()
g.add_node(1, **{"$x": 1, "$y": 1})
g.add_node(2, **{"$x": 1, "$y": 15})
g.add_node(3, **{"$x": 15, "$y": 15})
g.add_node(4, **{"$x": 15, "$y": 1})
g.add_node(5, **{"$x": 5, "$y": 7})

g.add_edge(
    1,
    3,
    **{
        "$edge-routing-mode": EdgeRoutingMode.ORTHOGONAL,
        "$edge-segment-drawing-mode": EdgeSegmentDrawingMode.BOX,
        "$style": Style(color="green"),
    },
)

print(ConsoleGraph(g, layout_engine=StaticLayout()))
