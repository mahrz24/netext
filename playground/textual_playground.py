import uuid
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
from textual.widgets import Input, Footer, Static, Tabs
from textual.widget import Widget
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive, Reactive

import networkx as nx

g = nx.DiGraph()


def _render(n, d, s):
    return d.get("title")


g.add_node(uuid.uuid4(), **{"title": "Hello World", "$content-renderer": _render})


class Toolbar(Widget):
    current_tool: str = "pointer-tool"

    def compose(self):
        yield Button(">", id="pointer-tool", classes="selected-tool")
        yield Button("O", id="add-node-tool")
        yield Button("/", id="add-edge-tool")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.switch_tool(event.button.id)

    def switch_tool(self, tool: str) -> None:
        self.query(f"#{self.current_tool}").remove_class("selected-tool")
        self.query(f"#{tool}").add_class("selected-tool")
        self.current_tool = tool


class NodeInspector(Widget):
    graph_view: GraphView
    node: Hashable

    def __init__(
        self,
        *children: Widget,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        graph_view: GraphView,
        node: Hashable,
    ) -> None:
        self.node = node
        self.graph_view = graph_view
        super().__init__(
            *children, name=name, id=id, classes=classes, disabled=disabled
        )

    def compose(self) -> ComposeResult:
        yield Tabs("Style", "Ports", "Content")


class Statusbar(Static):
    pass


class GraphArea(Widget):
    current_editor: tuple[Input, Hashable] | None = None
    edge_first_click: Hashable | None = None
    hover_element: Reactive[Reference | None] = reactive(cast(Reference | None, None))
    selected_element: Reactive[Reference | None] = reactive(
        cast(Reference | None, None)
    )
    move_selected: bool = False

    def compose(self) -> ComposeResult:
        graph_view = GraphView(g, zoom=1, scroll_via_viewport=False, id="graph")
        yield graph_view

    def watch_selected_element(
        self, old_value: Reference | None, new_value: Reference | None
    ) -> None:
        g = self.query_one(GraphView)
        inspector = self.query_one(GraphInspector)
        inspector.selected_element = new_value

        if old_value is not None and old_value.type == "edge":
            if g.graph.has_edge(*old_value.ref):
                g.update_edge(
                    *old_value.ref,
                    data={"$style": Style(color="white")},
                    update_layout=False,
                )

        if new_value is not None and new_value.type == "edge":
            g.update_edge(
                *new_value.ref,
                data={"$style": Style(color="blue")},
                update_layout=False,
            )

        if old_value is not None and old_value.type == "node":
            if g.graph.has_node(old_value.ref):
                g.update_node(old_value.ref, data={"$style": Style(color="white")})

        if new_value is not None and new_value.type == "node":
            g.update_node(new_value.ref, data={"$style": Style(color="blue")})

    def reset_edge(self, edge: tuple[Hashable, Hashable]) -> None:
        g = self.query_one(GraphView)
        if not g.graph.has_edge(*edge):
            return
        if (
            self.selected_element is not None
            and self.selected_element.type == "edge"
            and self.selected_element.ref == edge
        ):
            style = Style(color="blue")
        else:
            style = Style(color="white")

        g.update_edge(
            *edge,
            data={"$style": style},
            update_layout=False,
        )

    def reset_node(self, node: Hashable) -> None:
        g = self.query_one(GraphView)
        if not g.graph.has_node(node):
            return
        if (
            self.selected_element is not None
            and self.selected_element.type == "node"
            and self.selected_element.ref == node
        ):
            style = Style(color="blue")
        elif self.edge_first_click is not None and self.edge_first_click == node:
            style = Style(color="red")
        else:
            style = Style(color="white")

        g.update_node(node, data={"$style": style})

    def watch_hover_element(
        self, old_value: Reference | None, new_value: Reference | None
    ) -> None:
        g = self.query_one(GraphView)
        if old_value is not None and old_value.type == "edge":
            self.reset_edge(old_value.ref)

        if new_value is not None and new_value.type == "edge":
            g.update_edge(
                *new_value.ref,
                data={"$style": Style(color="green")},
                update_layout=False,
            )

        if old_value is not None and old_value.type == "node":
            self.reset_node(old_value.ref)

        if (
            new_value is not None
            and new_value.type == "node"
            and not self.move_selected
        ):
            g.update_node(new_value.ref, data={"$style": Style(color="green")})

    def on_click(self, event: events.Click) -> None:
        toolbar = self.query_one(Toolbar)

        if toolbar.current_tool == "add-node-tool":
            self.add_node(event.x, event.y)
            toolbar.switch_tool("pointer-tool")

        if self.selected_element is not None:
            self.selected_element = None

    def add_node(self, x: int, y: int) -> None:
        g = self.query_one(GraphView)
        node_uuid = uuid.uuid4()

        g.add_node(
            node_uuid,
            g.to_graph_coordinates(Offset(x, y)),
            data={
                "title": "Untitled New Node",
                "$content-renderer": _render,
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

        if event.element_reference.type == "node":
            if self.move_selected:
                self.move_selected = False

            g = self.query_one(GraphView)
            if toolbar.current_tool == "add-edge-tool":
                if self.edge_first_click is None:
                    self.edge_first_click = event.element_reference.ref
                    g.update_node(
                        self.edge_first_click, data={"$style": Style(color="red")}
                    )
                else:
                    g.update_node(self.edge_first_click, data={"$style": None})
                    self.add_edge(self.edge_first_click, event.element_reference.ref)
                    self.edge_first_click = None
            else:
                if self.selected_element == event.element_reference:
                    self.selected_element = None
                else:
                    self.selected_element = event.element_reference
        elif event.element_reference.type == "edge":
            if self.selected_element == event.element_reference:
                self.selected_element = None
            else:
                self.selected_element = event.element_reference

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

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self.move_selected and self.selected_element is not None:
            g = self.query_one(GraphView)
            g.update_node(
                self.selected_element.ref, position=Offset(x=event.x, y=event.y)
            )


class GraphInspector(Widget):
    graph_area: GraphArea
    selected_element: Reactive[Reference | None] = reactive(
        cast(Reference | None, None)
    )

    def __init__(
        self,
        *children: Widget,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        graph_area: GraphArea,
    ) -> None:
        self.graph_area = graph_area
        super().__init__(
            *children, name=name, id=id, classes=classes, disabled=disabled
        )

    def compose(self) -> ComposeResult:
        yield Static("Graph Inspector")

    def watch_selected_element(
        self, old_value: Reference | None, new_value: Reference | None
    ) -> None:
        self.query(Widget).first().remove()
        if new_value is None:
            self.mount(Static("Graph Inspector"))
            return
        match new_value.type:
            case "node":
                self.mount(
                    NodeInspector(
                        node=new_value.ref,
                        graph_view=self.graph_view.query_one(GraphView),
                    )
                )


class MainScreen(Screen):
    BINDINGS = [("m", "move_node", "Move Node"), ("x", "delete", "Delete Node / Edge")]

    def compose(self) -> ComposeResult:
        graph_area = GraphArea()
        yield Horizontal(
            Vertical(
                Toolbar(),
                graph_area,
                Footer(),
            ),
            Vertical(
                GraphInspector(graph_area=graph_area), Statusbar("Status"), id="sidebar"
            ),
        )

    def action_move_node(self) -> None:
        area = self.query_one(GraphArea)
        area.move_selected = True
        w = self.query_one(Statusbar)
        w.update("Move Node: Move mouse to place")

    def action_delete(self) -> None:
        # TODO move to area
        g = self.query_one(GraphView)
        area = self.query_one(GraphArea)
        area.move_selected = True
        if area.selected_element is not None:
            if area.hover_element == area.selected_element:
                area.hover_element = None
            selected = area.selected_element
            area.selected_element = None
            if selected.type == "node":
                g.remove_node(selected.ref)
            elif selected.type == "edge":
                g.remove_edge(*selected.ref)


class GraphApp(App):
    CSS_PATH = "textual_playground.css"

    def on_mount(self):
        self.push_screen(MainScreen())


app = GraphApp()

app.run()
