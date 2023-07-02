from netext.textual.widget import Graph
from textual.app import App, ComposeResult
from typing import cast
from rich.style import Style
from rich import box
from netext.edge_routing.modes import EdgeRoutingMode
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_rendering.arrow_tips import ArrowTip
from textual.containers import Horizontal
import networkx as nx

g = cast(nx.Graph, nx.binomial_tree(4))

nx.set_node_attributes(g, Style(color="blue"), "$content-style")
nx.set_node_attributes(g, box.SQUARE, "$box-type")
nx.set_edge_attributes(g, Style(color="red"), "$style")
nx.set_edge_attributes(g, EdgeRoutingMode.ORTHOGONAL, "$edge-routing-mode")
nx.set_edge_attributes(g, EdgeSegmentDrawingMode.BOX, "$edge-segment-drawing-mode")
nx.set_edge_attributes(g, ArrowTip.ARROW, "$end-arrow-tip")
nx.set_edge_attributes(g, ArrowTip.ARROW, "$start-arrow-tip")


class GraphApp(App):
    CSS_PATH = "textual_playground.css"

    BINDINGS = [
        ("=", "zoom_out()", "Zoom In"),
        ("-", "zoom_in()", "Zoom Out"),
    ]

    def compose(self) -> ComposeResult:
        yield Horizontal(Graph(g, zoom=1))

    def action_zoom_in(self) -> None:
        g = self.query_one(Graph)
        g.zoom = g.zoom / 1.1

    def action_zoom_out(self) -> None:
        g = self.query_one(Graph)
        g.zoom = g.zoom / 0.9


app = GraphApp()

app.run()
