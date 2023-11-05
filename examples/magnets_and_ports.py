from netext import ConsoleGraph
from netext.edge_rendering.arrow_tips import ArrowTip
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_routing.modes import EdgeRoutingMode
from netext.geometry import Magnet
from rich import print
from rich.style import Style

import networkx as nx

from netext.layout_engines.static import StaticLayout

for routing, drawing in [
    (EdgeRoutingMode.ORTHOGONAL, EdgeSegmentDrawingMode.BOX),
]:
    g = nx.Graph()
    g.add_node(
        "FOOOOOO",
        **{
            "$x": 30,
            "$y": 1,
            "$ports": {
                "a": {
                    "magnet": Magnet.BOTTOM,
                    "label": "A",
                },
                "b": {
                    "magnet": Magnet.BOTTOM,
                    "label": "B",
                },
                "c": {
                    "magnet": Magnet.BOTTOM,
                    "label": "C",
                },
                "d": {
                    "magnet": Magnet.BOTTOM,
                    "label": "D",
                },
            },
        },
    )
    g.add_node(2)

    g.add_node(3)
    g.add_node(4)

    g.add_edge(
        "FOOOOOO",
        2,
        **{
            "$edge-routing-mode": routing,
            "$start-port": "d",
            "$edge-segment-drawing-mode": drawing,
            "$end-arrow-tip": ArrowTip.ARROW,
            "$end-magnet": Magnet.TOP,
            "$style": Style(color="green"),
        },
    )

    g.add_edge(
        "FOOOOOO",
        3,
        **{
            "$edge-routing-mode": routing,
            "$start-port": "b",
            "$edge-segment-drawing-mode": drawing,
            "$end-arrow-tip": ArrowTip.ARROW,
            "$start-magnet": Magnet.LEFT,
            "$end-magnet": Magnet.TOP,
            "$style": Style(color="green"),
        },
    )

    g.add_edge(
        "FOOOOOO",
        4,
        **{
            "$edge-routing-mode": routing,
            "$edge-segment-drawing-mode": drawing,
            "$end-arrow-tip": ArrowTip.ARROW,
            "$start-port": "c",
            "$end-magnet": Magnet.TOP,
            "$style": Style(color="green"),
        },
    )
    g.add_node(5)

    g.add_edge(
        "FOOOOOO",
        5,
        **{
            "$edge-routing-mode": routing,
            "$edge-segment-drawing-mode": drawing,
            "$end-arrow-tip": ArrowTip.ARROW,
            "$start-port": "a",
            "$end-magnet": Magnet.TOP,
            "$style": Style(color="green"),
        },
    )

    print(ConsoleGraph(g, layout_engine=StaticLayout()))
