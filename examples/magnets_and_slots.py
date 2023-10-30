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
        "FOOOOOO",
        **{
            "$x": 30,
            "$y": 1,
            "$ports": {
                "a": {
                    "magnet": Magnet.LEFT,
                    "label": "A",
                },
                "b": {
                    "magnet": Magnet.LEFT,
                    "label": "B",
                },
                "c": {
                    "magnet": Magnet.LEFT,
                    "label": "C",
                },
                "d": {
                    "magnet": Magnet.LEFT,
                    "label": "D",
                },
                "e": {
                    "magnet": Magnet.LEFT,
                    "label": "E",
                },
                "f": {
                    "magnet": Magnet.LEFT,
                    "label": "F",
                },
            },
        }
    )
    g.add_node(2, **{"$x": 15, "$y": -10})

    g.add_node(3, **{"$x": 1, "$y": 10})
    g.add_node(4, **{"$x": 15, "$y": 10})

    g.add_edge(
        "FOOOOOO",
        2,
        **{
            "$edge-routing-mode": routing,
            "$start-port": "a",
            "$edge-segment-drawing-mode": drawing,
            "$end-arrow-tip": ArrowTip.ARROW,
            "$start-magnet": Magnet.LEFT,
            "$style": Style(color="green"),
        }
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
        }
    )

    g.add_edge(
        "FOOOOOO",
        4,
        **{
            "$edge-routing-mode": routing,
            "$edge-segment-drawing-mode": drawing,
            "$end-arrow-tip": ArrowTip.ARROW,
            "$start-port": "c",
            "$end-magnet": Magnet.BOTTOM,
            "$style": Style(color="green"),
        }
    )
    g.add_node(5, **{"$x": -15, "$y": 5})  # FloatPoint(-15, 5))

    cg = ConsoleGraph(g, layout_engine=StaticLayout())
    print("Graph created")
    cg.add_edge(
        "FOOOOOO",
        5,
        {
            "$edge-routing-mode": routing,
            "$edge-segment-drawing-mode": drawing,
            "$end-arrow-tip": ArrowTip.ARROW,
            "$start-port": "e",
            "$end-magnet": Magnet.TOP,
            "$style": Style(color="green"),
        },
    )
    # cg.update_node("FOOOOOO", data={"$style": Style(color="blue")})
    cg.update_edge("FOOOOOO", 5, data={"$style": Style(color="blue")})

    print(cg)
