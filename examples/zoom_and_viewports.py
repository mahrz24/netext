from typing import cast

import networkx as nx
from rich import print
from rich.panel import Panel
from rich.style import Style
from rich.layout import Layout

from netext import TerminalGraph
from netext.edge_routing.modes import EdgeRoutingMode
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_rendering.arrow_tips import ArrowTip
from netext.node_rasterizer import JustContent
from netext.terminal_graph import AutoZoom

g = cast(nx.Graph, nx.binomial_tree(6))
nx.set_edge_attributes(g, ArrowTip.ARROW, "$end-arrow-tip")
nx.set_edge_attributes(g, EdgeRoutingMode.ORTHOGONAL, "$edge-routing-mode")
nx.set_edge_attributes(
    g, EdgeSegmentDrawingMode.BOX_ROUNDED, "$edge-segment-drawing-mode"
)

nx.set_edge_attributes(g, Style(color="purple", bold=True), "$style")

nx.set_node_attributes(g, Style(color="green"), "$style")
nx.set_node_attributes(g, lambda zoom: 0 if zoom < 0.5 else 1, "$lod-map")
nx.set_node_attributes(g, JustContent(), "$shape-0")
nx.set_node_attributes(g, lambda _, __, ___: ".", "$content-renderer-0")


layout = Layout()

layout.split_column(
    Layout(name="top"),
    Layout(name="bottom"),
)

layout["top"].split_row(
    Layout(Panel(TerminalGraph(g), style=Style(color="blue")), name="top_left"),
    Layout(
        Panel(TerminalGraph(g, zoom=(AutoZoom.FIT)), style=Style(color="blue")),
        name="top_right",
        size=50,
    ),
)

layout["bottom"].split_row(
    Layout(name="bottom_1"),
    Layout(name="bottom_2"),
    Layout(name="bottom_3"),
    Layout(name="bottom_4"),
)

print(layout)
