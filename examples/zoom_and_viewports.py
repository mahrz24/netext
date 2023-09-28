from typing import cast

import networkx as nx
from rich.console import Console
from rich.color import Color
from rich.panel import Panel
from rich.style import Style
from rich.layout import Layout

from netext import ConsoleGraph
from netext.edge_routing.modes import EdgeRoutingMode
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_rendering.arrow_tips import ArrowTip
from netext.geometry import Region
from netext.node_rasterizer import JustContent
from netext.console_graph import AutoZoom

g = cast(nx.Graph, nx.binomial_tree(5))
nx.set_edge_attributes(g, ArrowTip.ARROW, "$end-arrow-tip")
nx.set_edge_attributes(g, None, "$end-arrow-tip-0")
nx.set_edge_attributes(g, lambda zoom: 0 if zoom < 0.5 else 1, "$lod-map")
nx.set_edge_attributes(
    g, Style(color=Color.from_rgb(red=20, green=80, blue=10), bold=True), "$style-0"
)
nx.set_edge_attributes(
    g, EdgeSegmentDrawingMode.BOX_HEAVY, "$edge-segment-drawing-mode-0"
)


nx.set_edge_attributes(g, EdgeRoutingMode.ORTHOGONAL, "$edge-routing-mode")
nx.set_edge_attributes(
    g, EdgeSegmentDrawingMode.BOX_ROUNDED, "$edge-segment-drawing-mode"
)

nx.set_edge_attributes(g, Style(color="purple", bold=True), "$style")

nx.set_node_attributes(g, Style(color="green"), "$style")
nx.set_node_attributes(g, lambda zoom: 0 if zoom < 0.5 else 1, "$lod-map")
nx.set_node_attributes(g, JustContent(), "$shape-0")
nx.set_node_attributes(g, lambda _, __, ___: "⏺", "$content-renderer-0")


layout = Layout()

layout.split_column(
    Layout(name="top"),
    Layout(name="bottom"),
)

layout["top"].split_row(
    Layout(
        Panel(ConsoleGraph(g), style=Style(color="blue")), name="top_left", size=120
    ),
    Layout(
        Panel(ConsoleGraph(g, zoom=(AutoZoom.FIT)), style=Style(color="blue")),
        name="top_right",
        size=40,
    ),
)

layout["bottom"].split_row(
    Layout(
        Panel(
            ConsoleGraph(g, viewport=Region(-10, -10, 40, 15)),
            style=Style(color="blue"),
        ),
        name="bottom_1",
        size=40,
    ),
    Layout(
        Panel(
            ConsoleGraph(g, viewport=Region(-20, -20, 40, 15)),
            style=Style(color="blue"),
        ),
        name="bottom_1",
        size=40,
    ),
    Layout(
        Panel(
            ConsoleGraph(g, viewport=Region(0, 0, 40, 15)), style=Style(color="blue")
        ),
        name="bottom_1",
        size=40,
    ),
    Layout(
        Panel(
            ConsoleGraph(g, viewport=Region(5, -10, 40, 15)), style=Style(color="blue")
        ),
        name="bottom_1",
        size=40,
    ),
)

console = Console()

console.print(layout, height=30)
