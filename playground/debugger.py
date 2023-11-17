import time
from typing import Any, Callable, cast
from textual.app import App, ComposeResult, RenderResult
from textual.containers import Vertical
from textual.widgets import Header, Footer, Tree, OptionList, Input, TabbedContent
from textual.widget import Widget
from textual.reactive import reactive, Reactive
from textual.message import Message
from textual.geometry import Size
from textual.screen import ModalScreen, Screen
from textual.events import Key
from netext.edge_rendering.arrow_tips import ArrowTip
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.layout_engines.grandalf import GrandalfSugiyamaLayout
from netext.layout_engines.static import StaticLayout
from pyinstrument.processors import aggregate_repeated_calls

from netext.console_graph import GraphProfiler, ConsoleGraph

import networkx as nx
from rich import box
from rich.text import Text
from rich.style import Style
from rich.pretty import Pretty

from netext.edge_routing.modes import EdgeRoutingMode

from pyinstrument import Profiler


class Graph(Widget):
    """Display a graph."""

    graph: Reactive[nx.DiGraph | nx.Graph | None] = reactive(None)
    console_graph: ConsoleGraph | None = None

    class Profiled(Message):
        """Color selected message."""

        def __init__(
            self,
            layout_profiler: Profiler,
            node_render_profiler: Profiler,
            edge_render_profiler: Profiler,
            buffer_render_profiler: Profiler,
        ) -> None:
            self.layout_profiler = layout_profiler
            self.node_render_profiler = node_render_profiler
            self.edge_render_profiler = edge_render_profiler
            self.buffer_render_profiler = buffer_render_profiler
            super().__init__()

    def watch_graph(
        self,
        old_graph: nx.DiGraph | nx.Graph | None,
        new_graph: nx.DiGraph | nx.Graph | None,
    ) -> None:
        if new_graph:
            self._render_with_graph(new_graph)

    def graph_mutated(self) -> None:
        if self.graph is not None:
            self._render_with_graph(self.graph)

    def _render_with_graph(self, graph: nx.DiGraph | nx.Graph) -> None:
        layout_profiler = Profiler()
        node_render_profiler = Profiler()
        edge_render_profiler = Profiler()
        buffer_render_profiler = Profiler(async_mode=False)

        # If the graph has coordinates use a static layout, otherwise use the grandalf engine
        engine = GrandalfSugiyamaLayout()
        if nx.get_node_attributes(graph, "$x") and nx.get_node_attributes(graph, "$y"):
            engine = StaticLayout()

        self.console_graph = ConsoleGraph(
            graph,
            layout_engine=engine,
            layout_profiler=cast(GraphProfiler, layout_profiler),
            node_render_profiler=cast(GraphProfiler, node_render_profiler),
            edge_render_profiler=cast(GraphProfiler, edge_render_profiler),
            buffer_render_profiler=cast(GraphProfiler, buffer_render_profiler),
        )

        self.console_graph._profile_render()

        for node, pos in self.console_graph.node_layout.items():
            graph.nodes[node]["$x"] = pos[0]
            graph.nodes[node]["$y"] = pos[1]

        self.post_message(
            self.Profiled(
                layout_profiler,
                node_render_profiler,
                edge_render_profiler,
                buffer_render_profiler,
            )
        )
        self.refresh(layout=False)

    def render(self) -> RenderResult:
        if self.console_graph:
            return self.console_graph
        else:
            return "Empty graph."

    def get_content_width(self, container: Size, viewport: Size) -> int:
        """Force content width size."""
        return self.console_graph.width

    def get_content_height(self, container: Size, viewport: Size, width: int) -> int:
        """Force content width size."""
        return self.console_graph.height


def create_graph() -> nx.DiGraph:
    def _render2(n, d, s):
        return Text(f"#N{n}", style=s)

    g = cast(nx.Graph, nx.binomial_tree(5))

    nx.set_node_attributes(g, Style(color="blue"), "$content-style")
    nx.set_node_attributes(g, box.SQUARE, "$box-type")
    nx.set_edge_attributes(g, EdgeRoutingMode.ORTHOGONAL, "$edge-routing-mode")
    nx.set_edge_attributes(g, EdgeSegmentDrawingMode.BOX, "$edge-segment-drawing-mode")
    nx.set_edge_attributes(g, ArrowTip.ARROW, "$end-arrow-tip")
    nx.set_edge_attributes(g, ArrowTip.ARROW, "$start-arrow-tip")

    # nx.set_edge_attributes(g, "foo", "$label")
    nx.set_node_attributes(g, _render2, "$content-renderer")
    nx.set_node_attributes(g, True, "$show")

    nx.set_edge_attributes(g, True, "$show")

    # nx.set_edge_attributes(g, False, "$show")
    g.edges[8, 10]["$show"] = True

    return g


def add_frame(node, frame, total_time) -> None:
    if not frame.group or (
        frame.group.root == frame or frame.total_self_time > 0.2 * total_time or frame in frame.group.exit_frames
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
        stats.add_leaf("Recorded: {:<9}".format(time.strftime("%X", time.localtime(session.start_time))))
        stats.add_leaf(f"Samples:  {session.sample_count}")
        stats.add_leaf(f"Duration: {session.duration:<9.3f}")
        stats.add_leaf(f"CPU time: {session.cpu_time:.3f}")

        root_frame = aggregate_repeated_calls(session.root_frame(), {})

        if root_frame:
            frames = node.add("Frames")
            total_time = root_frame.time
            add_frame(frames, root_frame, total_time)


class ModalDialog(ModalScreen):
    BINDINGS = [
        ("escape", "close", "Close node select screen"),
    ]

    def __init__(
        self,
        callback: Callable[[Any], None],
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name, id, classes)
        self.callback = callback

    def action_close(self) -> None:
        self.app.pop_screen()


class SelectDialog(ModalDialog):
    """Option select dialog."""

    def __init__(
        self,
        options: list[str],
        callback: Callable[[Any], None],
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(callback, name, id, classes)
        self.options = options

    def compose(self) -> ComposeResult:
        yield OptionList(*[str(s) for s in self.options], id="option-list").focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.app.pop_screen()
        self.callback(self.options[event.option_index])


class InputDialog(ModalDialog):
    """Option select dialog."""

    def __init__(
        self,
        default: str,
        callback: Callable[[Any], None],
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(callback, name, id, classes)
        self.default = default

    def compose(self) -> ComposeResult:
        yield Input(placeholder=self.default).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.app.pop_screen()
        self.callback(event.value)


class NodeView(Widget):
    node: Reactive[dict] = reactive(dict())

    def render(self) -> RenderResult:
        return Pretty(self.node)


class MainScreen(Screen):
    """A Textual app to debug graph rendering with netext."""

    BINDINGS = [
        ("d", "toggle_dark", "Toggle dark mode"),
        ("o", "load_graph", "Load graph"),
        ("n", "toggle_nodes", "Toggle nodes"),
        ("e", "toggle_edges", "Toggle edges"),
        ("s", "select_node", "Select node"),
        ("ctrl+a", "add_node", "Add node"),
        ("ctrl+e", "add_edge", "Add edge"),
        ("ctrl+l", "layout", "Layout"),
    ]

    selected_node: Reactive[Any | None] = reactive(None)
    graph: nx.DiGraph | nx.Graph | None = None

    def watch_selected_node(self, old_node: Any, new_node: Any):
        graph_widget = self.query_one(Graph)
        if new_node in graph_widget.graph.nodes:
            node = graph_widget.graph.nodes[new_node]
            self.query_one(NodeView).node = node

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        graph = Graph()
        graph.graph = create_graph()

        yield Header()
        with Vertical(id="sidebar"):
            with TabbedContent("Profiler", "Inspector"):
                yield Tree("Profiler", id="profiler")
                yield NodeView(id="node-view")
        with Vertical(id="main-container"):
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

        buffer_render = tree.root.add("Buffer Render")
        add_profiler_node(buffer_render, message.buffer_render_profiler)

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.dark = not self.dark

    def action_add_node(self) -> None:
        """An action to add a node."""
        graph_widget = self.query_one(Graph)

        def _add_node(name: str) -> None:
            if name:
                graph_widget.graph.add_node(name)
                graph_widget.graph.nodes[name]["$show"] = True
                graph_widget.graph_mutated()

        self.app.push_screen(
            InputDialog(
                "New Node",
                _add_node,
            )
        )

    def action_add_edge(self) -> None:
        """An action to add a node."""
        graph_widget = self.query_one(Graph)

        if graph_widget and self.selected_node:

            def _add_edge(node: Any) -> None:
                graph_widget.graph.add_edge(self.selected_node, node)
                graph_widget.graph.edges[self.selected_node, node].update(
                    {
                        "$edge-routing-mode": EdgeRoutingMode.ORTHOGONAL,
                        "$edge-segment-drawing-mode": EdgeSegmentDrawingMode.BOX,
                        "$end-arrow-tip": ArrowTip.ARROW,
                        "$show": True,
                    }
                )
                graph_widget.graph_mutated()

            self.app.push_screen(
                SelectDialog(
                    list(graph_widget.graph.nodes(data=False)),
                    _add_edge,
                )
            )

    def action_toggle_nodes(self) -> None:
        """An action to toggle nodes."""
        graph_widget = self.query_one(Graph)
        for node in graph_widget.graph.nodes:
            graph_widget.graph.nodes[node]["$show"] = not graph_widget.graph.nodes[node]["$show"]

        graph_widget.graph_mutated()

    def action_toggle_edges(self) -> None:
        """An action to toggle edges."""
        graph_widget = self.query_one(Graph)
        for u, v in graph_widget.graph.edges:
            graph_widget.graph.edges[u, v]["$show"] = not graph_widget.graph.edges[u, v]["$show"]

        graph_widget.graph_mutated()

    def action_select_node(self) -> None:
        graph_widget = self.query_one(Graph)
        if graph_widget:

            def _select_node(node: Any) -> None:
                if self.selected_node:
                    del graph_widget.graph.nodes[self.selected_node]["$style"]
                self.selected_node = node
                graph_widget.graph.nodes[node]["$style"] = Style(color="red")
                graph_widget.graph_mutated()

            self.app.push_screen(SelectDialog(list(graph_widget.graph.nodes(data=False)), _select_node))

    def action_layout(self) -> None:
        """An action to add a node."""
        graph_widget = self.query_one(Graph)
        for node in graph_widget.graph.nodes(data=False):
            del graph_widget.graph.nodes[node]["$x"]
            del graph_widget.graph.nodes[node]["$y"]

        graph_widget.graph_mutated()

    def action_load_graph(self) -> None:
        graph_widget = self.query_one(Graph)
        if graph_widget:

            def _load_graph(graph: str) -> None:
                if graph == "Binomial Graph n=5":
                    graph_widget.graph = create_graph()
                elif graph == "Empty Graph":
                    graph_widget.graph = nx.DiGraph()
                graph_widget.graph_mutated()

            self.app.push_screen(SelectDialog(["Binomial Graph n=5", "Empty Graph"], _load_graph))

    def on_key(self, event: Key) -> None:
        if self.selected_node:
            graph_widget = self.query_one(Graph)
            match event.character:
                case "k":
                    graph_widget.graph.nodes[self.selected_node]["$y"] -= 1
                case "j":
                    graph_widget.graph.nodes[self.selected_node]["$y"] += 1
                case "h":
                    graph_widget.graph.nodes[self.selected_node]["$x"] -= 1
                case "l":
                    graph_widget.graph.nodes[self.selected_node]["$x"] += 1
            graph_widget.graph_mutated()


class GraphDebuggerApp(App):
    CSS_PATH = "debugger.css"

    def on_mount(self):
        self.push_screen(MainScreen())


if __name__ == "__main__":
    app = GraphDebuggerApp()
    app.run()
