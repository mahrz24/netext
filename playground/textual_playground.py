import uuid
from netext.geometry.magnet import Magnet
from netext.rendering.segment_buffer import Reference
from netext.textual.widget import GraphView
from textual import events
from textual.app import App, ComposeResult
from typing import Hashable, cast
from rich.style import Style
from netext.edge_routing.modes import EdgeRoutingMode
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_rendering.arrow_tips import ArrowTip
from textual.widgets import Button
from textual.geometry import Offset
from textual.screen import Screen
from textual.widgets import Input, Footer, Placeholder
from textual.widget import Widget
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive, Reactive

import networkx as nx

g = nx.DiGraph()


def _render(n, d, s):
    return d.get("title")


g.add_node(uuid.uuid4(), **{"title": "Hello World", "$content-renderer": _render})


# nx.set_node_attributes(g, Style(color="blue"), "$content-style")
# nx.set_node_attributes(g, box.SQUARE, "$box-type")
# nx.set_edge_attributes(g, Style(color="red"), "$style")
# nx.set_edge_attributes(g, EdgeRoutingMode.ORTHOGONAL, "$edge-routing-mode")
# nx.set_edge_attributes(g, EdgeSegmentDrawingMode.BOX, "$edge-segment-drawing-mode")
# nx.set_edge_attributes(g, ArrowTip.ARROW, "$end-arrow-tip")
# nx.set_edge_attributes(g, ArrowTip.ARROW, "$start-arrow-tip")
# nx.set_node_attributes(g, _render2, "$content-renderer")


class Toolbar(Widget):
    current_tool: str = "pointer-tool"

    def compose(self):
        yield Button(">", id="pointer-tool", classes="selected-tool")
        yield Button("+O", id="add-node-tool")
        yield Button("+/", id="add-edge-tool")
        yield Button("+T", id="add-label-tool")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.query(f"#{self.current_tool}").remove_class("selected-tool")
        self.query(f"#{event.button.id}").add_class("selected-tool")
        self.current_tool = event.button.id


class Statusbar(Placeholder):
    pass


class MainScreen(Screen):
    current_editor: tuple[Input, Hashable] | None = None
    edge_first_click: Hashable | None = None
    hover_element: Reactive[Reference | None] = reactive(cast(Reference | None, None))

    BINDINGS = []

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Vertical(
                Toolbar(), GraphView(g, zoom=1, scroll_via_viewport=False, id="graph")
            ),
            Vertical(Footer(), Statusbar("Status"), id="footer"),
        )

    def watch_hover_element(
        self, old_value: Reference | None, new_value: Reference | None
    ) -> None:
        g = self.query_one(GraphView)
        if old_value is not None and old_value.type == "edge":
            g.update_edge(
                *old_value.ref,
                data={"$style": Style(color="white")},
                update_layout=False,
            )

        if new_value is not None and new_value.type == "edge":
            g.update_edge(
                *new_value.ref,
                data={"$style": Style(color="green")},
                update_layout=False,
            )

        if old_value is not None and old_value.type == "node":
            g.update_node(old_value.ref, data={"$style": None})

        if new_value is not None and new_value.type == "node":
            g.update_node(new_value.ref, data={"$style": Style(color="green")})

    def on_click(self, event: events.Click) -> None:
        toolbar = self.query_one(Toolbar)

        if toolbar.current_tool == "add-node-tool":
            self.add_node(event.x, event.y)

    def add_node(self, x: int, y: int) -> None:
        g = self.query_one(GraphView)
        node_uuid = uuid.uuid4()

        g.add_node(
            node_uuid,
            g.to_graph_coordinates(Offset(x, y)),
            data={
                "title": "Untitled New Node",
                "$content-renderer": _render,
                "$ports": {"a": {"magnet": Magnet.LEFT, "label": "A"}},
            },
        )
        self.edit_node_label(node_uuid)

    def add_edge(self, u: Hashable, v: Hashable) -> None:
        g = self.query_one(GraphView)
        g.add_edge(
            u,
            v,
            data={
                "$edge-routing-mode": EdgeRoutingMode.ORTHOGONAL,
                "$edge-segment-drawing-mode": EdgeSegmentDrawingMode.BOX,
                "$end-arrow-tip": ArrowTip.ARROW,
            },
        )

    def edit_node_label(self, node: Hashable) -> None:
        g = self.query_one(GraphView)

        if self.current_editor is not None:
            self.end_node_editing(*self.current_editor)

        title = g.graph.nodes(data=True)[node]["title"]
        input_widget = Input(placeholder=title)
        input_widget.focus()
        g.attach_widget_to_node(widget=input_widget, node=node)
        self.current_editor = input_widget, node

    def end_node_editing(self, input_widget: Input, node: Hashable) -> None:
        g = self.query_one(GraphView)
        g.detach_widget_from_node(node)
        self.current_editor = None

    def on_input_submitted(self, event: Input.Submitted) -> None:
        g = self.query_one(GraphView)
        control = event.control
        node = g._attached_widgets_lookup.get(control)
        g.update_node(node, data={"title": control.value})
        self.end_node_editing(control, node)

    def on_graph_view_element_click(self, event: GraphView.ElementClick) -> None:
        toolbar = self.query_one(Toolbar)

        if (
            toolbar.current_tool == "add-edge-tool"
            and event.element_reference.type == "node"
        ):
            g = self.query_one(GraphView)
            if self.edge_first_click is None:
                self.edge_first_click = event.element_reference.ref
                g.update_node(
                    self.edge_first_click, data={"$style": Style(color="red")}
                )
            else:
                g.update_node(self.edge_first_click, data={"$style": None})
                self.add_edge(self.edge_first_click, event.element_reference.ref)
                self.edge_first_click = None

    def on_graph_view_element_move(self, event: GraphView.ElementMove) -> None:
        pass

    def on_graph_view_element_mouse_down(
        self, event: GraphView.ElementMouseDown
    ) -> None:
        self.log(event, event.element_reference)

    def on_graph_view_element_mouse_up(self, event: GraphView.ElementMouseUp) -> None:
        self.log(event, event.element_reference)

    def on_graph_view_element_enter(self, event: GraphView.ElementEnter) -> None:
        self.log(event, event.element_reference)
        self.hover_element = event.element_reference

    def on_graph_view_element_leave(self, event: GraphView.ElementLeave) -> None:
        self.log(event, event.element_reference)
        self.hover_element = None


class GraphApp(App):
    CSS_PATH = "textual_playground.css"

    def on_mount(self):
        self.push_screen(MainScreen())


app = GraphApp()

app.run()
