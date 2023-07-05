from netext.textual.widget import GraphView
from textual.app import App, ComposeResult
from typing import cast
from rich.style import Style
from rich import box
from netext.edge_routing.modes import EdgeRoutingMode
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_rendering.arrow_tips import ArrowTip
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import ListView, Static, ListItem
from textual.reactive import reactive
import networkx as nx

g = cast(nx.Graph, nx.binomial_tree(4))

nx.set_node_attributes(g, Style(color="blue"), "$content-style")
nx.set_node_attributes(g, box.SQUARE, "$box-type")
nx.set_edge_attributes(g, Style(color="red"), "$style")
nx.set_edge_attributes(g, EdgeRoutingMode.ORTHOGONAL, "$edge-routing-mode")
nx.set_edge_attributes(g, EdgeSegmentDrawingMode.BOX, "$edge-segment-drawing-mode")
nx.set_edge_attributes(g, ArrowTip.ARROW, "$end-arrow-tip")
nx.set_edge_attributes(g, ArrowTip.ARROW, "$start-arrow-tip")


class GraphInspector(Widget):
    graph: reactive[GraphView | None] = reactive(None)

    def __init__(self, graph: GraphView, **kwargs) -> None:
        super().__init__(**kwargs)
        self.graph = graph

    def compose(self) -> ComposeResult:
        yield ListView(id="edge-list")

    def update(self) -> None:
        edge_list: ListView = self.query_one("#edge-list")
        edge_list.clear()
        if self.graph and self.graph._console_graph is not None:
            for (
                key,
                value,
            ) in self.graph._console_graph.edge_buffers_current_lod.items():
                boundary = f"{value.boundary_1} {value.boundary_2}"
                edge_list.append(ListItem(Static(f"{key}: [{boundary}]")))
            for (
                key,
                value,
            ) in self.graph._console_graph.label_buffers_current_lod.items():
                for label in value:
                    boundary = f"{label.bounding_box}"
                    edge_list.append(ListItem(Static(f"{key}: [{boundary}]")))


class GraphApp(App):
    CSS_PATH = "textual_playground.css"

    BINDINGS = [
        ("=", "zoom_out()", "Zoom In"),
        ("-", "zoom_in()", "Zoom Out"),
    ]

    def compose(self) -> ComposeResult:
        graph = GraphView(g, zoom=1)
        yield Horizontal(graph, GraphInspector(graph))

    def action_zoom_in(self) -> None:
        g = self.query_one(GraphView)
        g.zoom = g.zoom / 1.1
        self.query_one(GraphInspector).update()

    def action_zoom_out(self) -> None:
        g = self.query_one(GraphView)
        g.zoom = g.zoom / 0.9
        self.query_one(GraphInspector).update()


app = GraphApp()

app.run()
