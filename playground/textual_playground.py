from netext.textual.widget import Graph
from netext import AutoZoom
from textual.app import App, ComposeResult
from typing import cast
from rich.style import Style
from rich import box
from netext.edge_routing.modes import EdgeRoutingMode
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_rendering.arrow_tips import ArrowTip
from textual.containers import Horizontal, Container
from textual.widgets import Static
import networkx as nx

g = cast(nx.Graph, nx.binomial_tree(6))

nx.set_node_attributes(g, Style(color="blue"), "$content-style")
nx.set_node_attributes(g, box.SQUARE, "$box-type")
nx.set_edge_attributes(g, Style(color="red"), "$style")
nx.set_edge_attributes(g, EdgeRoutingMode.ORTHOGONAL, "$edge-routing-mode")
nx.set_edge_attributes(g, EdgeSegmentDrawingMode.BOX, "$edge-segment-drawing-mode")
nx.set_edge_attributes(g, ArrowTip.ARROW, "$end-arrow-tip")
nx.set_edge_attributes(g, ArrowTip.ARROW, "$start-arrow-tip")


class GraphApp(App):
    CSS_PATH = "textual_playground.css"

    def compose(self) -> ComposeResult:
        yield Horizontal(Graph(g, zoom=AutoZoom.FIT))

app = GraphApp()

app.run()
