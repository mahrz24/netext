import time
from typing import cast
from textual.app import App, ComposeResult, RenderResult
from textual.containers import Horizontal
from textual.widgets import Header, Footer, Tree
from textual.widget import Widget
from textual.reactive import reactive, Reactive
from textual.message import Message
from textual.geometry import Size

from netext.terminal_graph import GraphProfiler, TerminalGraph

import networkx as nx
from rich import box
from rich.text import Text
from rich.style import Style

from netext.edge_rasterizer import ArrowTip, EdgeRoutingMode, EdgeSegmentDrawingMode

from pyinstrument import Profiler


class Graph(Widget):
    """Display a graph."""

    graph: Reactive[nx.DiGraph | nx.Graph | None] = reactive(None)
    terminal_graph: TerminalGraph | None = None

    class Profiled(Message):
        """Color selected message."""

        def __init__(
            self,
            layout_profiler: Profiler,
            node_render_profiler: Profiler,
            edge_render_profiler: Profiler,
        ) -> None:
            self.layout_profiler = layout_profiler
            self.node_render_profiler = node_render_profiler
            self.edge_render_profiler = edge_render_profiler
            super().__init__()

    def watch_graph(
        self,
        old_graph: nx.DiGraph | nx.Graph | None,
        new_graph: nx.DiGraph | nx.Graph | None,
    ) -> None:
        if new_graph:
            self._render_with_graph(new_graph)

    def graph_mutated(self) -> None:
        if self.graph:
            self._render_with_graph(self.graph)

    def _render_with_graph(self, graph: nx.DiGraph | nx.Graph) -> None:
        layout_profiler = Profiler()
        node_render_profiler = Profiler()
        edge_render_profiler = Profiler()
        self.terminal_graph = TerminalGraph(
            graph,
            layout_profiler=cast(GraphProfiler, layout_profiler),
            node_render_profiler=cast(GraphProfiler, node_render_profiler),
            edge_render_profiler=cast(GraphProfiler, edge_render_profiler),
        )
        self.post_message(
            self.Profiled(layout_profiler, node_render_profiler, edge_render_profiler)
        )
        self.refresh()

    def render(self) -> RenderResult:
        if self.terminal_graph:
            return self.terminal_graph
        else:
            return "Empty graph."

    def get_content_width(self, container: Size, viewport: Size) -> int:
        """Force content width size."""
        return self.terminal_graph.width

    def get_content_height(self, container: Size, viewport: Size, width: int) -> int:
        """Force content width size."""
        return self.terminal_graph.height


def create_graph() -> nx.DiGraph:
    def _render2(n, d, s):
        return Text(f"#N{n}", style=s)

    g = cast(nx.Graph, nx.binomial_tree(5))

    nx.set_node_attributes(g, Style(color="blue"), "$content-style")
    nx.set_node_attributes(g, box.SQUARE, "$box-type")
    nx.set_edge_attributes(g, EdgeRoutingMode.orthogonal, "$edge-routing-mode")
    nx.set_edge_attributes(g, EdgeSegmentDrawingMode.box, "$edge-segment-drawing-mode")
    nx.set_edge_attributes(g, ArrowTip.arrow, "$end-arrow-tip")
    nx.set_edge_attributes(g, ArrowTip.arrow, "$start-arrow-tip")

    # nx.set_edge_attributes(g, "foo", "$label")
    nx.set_node_attributes(g, _render2, "$content-renderer")
    nx.set_node_attributes(g, True, "$show")

    # nx.set_edge_attributes(g, False, "$show")
    g.edges[8, 10]["$show"] = True

    return g


def add_frame(node, frame, total_time) -> None:
    if not frame.group or (
        frame.group.root == frame
        or frame.total_self_time > 0.2 * total_time
        or frame in frame.group.exit_frames
    ):
        percent = frame.time / total_time * 100
        time_percent_str = f"{percent:.0f}%"
        time_str = f"{frame.time:.3f}"

        class_name = frame.class_name
        if class_name:
            name = f"{class_name}.{frame.function}"
        else:
            name = frame.function

        frame_node = node.add(f"{name} ({time_percent_str} {time_str})")

        if frame.group and frame.group.root == frame:
            frame_node = frame_node.add(f"[{len(frame.group.frames)} frames hidden]")

    if frame.children:
        for child in frame.children:
            add_frame(frame_node, child, total_time)


def add_profiler_node(node, profiler: Profiler) -> None:
    """Add a profiler node to a tree."""
    stats = node.add("Stats")
    session = profiler.last_session

    if session is not None:
        stats.add_leaf(f"Program: {session.program}")
        stats.add_leaf(
            "Recorded: {:<9}".format(
                time.strftime("%X", time.localtime(session.start_time))
            )
        )
        stats.add_leaf(f"Samples:  {session.sample_count}")
        stats.add_leaf(f"Duration: {session.duration:<9.3f}")
        stats.add_leaf(f"CPU time: {session.cpu_time:.3f}")

        root_frame = session.root_frame()

        if root_frame:
            frames = node.add("Frames")
            total_time = root_frame.time
            add_frame(frames, root_frame, total_time)


class GraphDebuggerApp(App):
    """A Textual app to debug graph rendering with netext."""

    BINDINGS = [
        ("d", "toggle_dark", "Toggle dark mode"),
        ("n", "toggle_nodes", "Toggle nodes"),
        ("e", "toggle_edges", "Toggle edges"),
    ]
    CSS_PATH = "debugger.css"

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        graph = Graph()
        graph.graph = create_graph()

        yield Header()
        yield Tree("Profiler", id="profiler")
        with Horizontal():
            yield graph
        yield Footer()

    def on_graph_profiled(self, message: Graph.Profiled) -> None:
        tree = cast(Tree, self.query_one("Tree#profiler"))
        tree.clear()

        layout = tree.root.add("Layout")
        add_profiler_node(layout, message.layout_profiler)

        node_render = tree.root.add("Node Render")
        add_profiler_node(node_render, message.node_render_profiler)

        edge_render = tree.root.add("Edge Render")
        add_profiler_node(edge_render, message.edge_render_profiler)

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.dark = not self.dark

    def action_toggle_nodes(self) -> None:
        """An action to toggle nodes."""
        graph_widget = self.query_one(Graph)
        for node in graph_widget.graph.nodes:
            graph_widget.graph.nodes[node]["$show"] = not graph_widget.graph.nodes[
                node
            ]["$show"]

        graph_widget.graph_mutated()


if __name__ == "__main__":
    app = GraphDebuggerApp()
    app.run()
