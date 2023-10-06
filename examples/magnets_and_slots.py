from netext import ConsoleGraph
from netext.edge_rendering.arrow_tips import ArrowTip
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_routing.modes import EdgeRoutingMode
from netext.geometry import Magnet
from netext.layout_engines.static import StaticLayout
from rich import print
from rich.style import Style

import networkx as nx

for routing, drawing in [
    (EdgeRoutingMode.ORTHOGONAL, EdgeSegmentDrawingMode.BOX),
]:
    g = nx.Graph()
    g.add_node(
        1,
        **{
            "$x": 1,
            "$y": 1,
        }
    )
    g.add_node(2, **{"$x": 15, "$y": 1})

    g.add_node(3, **{"$x": 1, "$y": 10})
    g.add_node(4, **{"$x": 15, "$y": 10})

    g.add_edge(
        1,
        2,
        **{
            "$edge-routing-mode": routing,
            "$edge-segment-drawing-mode": drawing,
            "$end-arrow-tip": ArrowTip.ARROW,
            "$start-magnet": Magnet.LEFT,
            "$end-magnet": Magnet.TOP,
            "$style": Style(color="green"),
        }
    )

    g.add_edge(
        3,
        4,
        **{
            "$edge-routing-mode": routing,
            "$edge-segment-drawing-mode": drawing,
            "$end-arrow-tip": ArrowTip.ARROW,
            "$start-magnet": Magnet.TOP,
            "$end-magnet": Magnet.BOTTOM,
            "$style": Style(color="green"),
        }
    )

    print(ConsoleGraph(g, layout_engine=StaticLayout()))
