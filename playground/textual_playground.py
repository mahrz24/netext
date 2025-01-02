from dataclasses import dataclass
import uuid
from netext.geometry.magnet import Magnet
from netext.properties.node import NodeProperties
from netext.properties.shape import Box, JustContent
from netext.rendering.segment_buffer import Reference
from netext.textual.widget import GraphView
from textual import events
from textual.app import App, ComposeResult
from typing import Any, Hashable, cast
from rich.style import Style
from netext.edge_routing.modes import EdgeRoutingMode
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_rendering.arrow_tips import ArrowTip
from textual.widgets import Button
from textual.geometry import Offset
from textual.screen import Screen
from textual.widgets import (
    Input,
    Footer,
    Static,
    TabbedContent,
    Pretty,
    Label,
    # Placeholder,
    # Checkbox,
    RadioSet,
    RadioButton,
)
from textual.widget import Widget
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive, Reactive
from textual.message import Message
from textual import on
from rich import box

import networkx as nx

g = nx.DiGraph()


def _render(n, d, s):
    return d.get("title")


g.add_node(uuid.uuid4(), **{"title": "Hello World", "$content-renderer": _render})


class Toolbar(Widget):
    current_tool: str = "pointer-tool"

    @dataclass
    class ToolSwitched(Message):
        tool: str

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
        self.post_message(self.ToolSwitched(tool=tool))


class Port(Widget):
    port: str
    port_setting: dict[str, Any]

    @dataclass
    class DeletePort(Message):
        port: str

    @dataclass
    class PortSettingChanged(Message):
        port: str
        port_setting: dict[str, Any]

    def __init__(
        self,
        *children: Widget,
        port: str,
        port_setting: dict[str, Any],
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        self.port = port
        self.port_setting = port_setting
        super().__init__(*children, name=name, id=id, classes=classes, disabled=disabled)

    def compose(self) -> ComposeResult:
        with Horizontal(id="port-row"):
            yield Input(self.port_setting["label"], id="port-label")
            with Horizontal(id="magnet-buttons"):
                yield Button("T", id="magnet-top", classes="magnet-button")
                yield Button("B", id="magnet-bottom", classes="magnet-button")
                yield Button("L", id="magnet-left", classes="magnet-button")
                yield Button("R", id="magnet-right", classes="magnet-button")
            yield Button("Delete", id="delete-button")

    @on(Button.Pressed, "#delete-button")
    def delete_port(self, event: Button.Pressed) -> None:
        self.log("Delete Port")
        self.post_message(self.DeletePort(port=self.port))

    @on(Input.Submitted, "#port-label")
    def port_label_changed(self, event: Input.Submitted) -> None:
        self.log("Port Label Changed")
        self.port_setting["label"] = event.control.value
        self.post_message(self.PortSettingChanged(port=self.port, port_setting=self.port_setting))

    @on(Button.Pressed, "#magnet-top")
    def magnet_top(self, event: Button.Pressed) -> None:
        self.log("Magnet Top")
        self.port_setting["magnet"] = Magnet.TOP
        self.post_message(self.PortSettingChanged(port=self.port, port_setting=self.port_setting))

    @on(Button.Pressed, "#magnet-bottom")
    def magnet_bottom(self, event: Button.Pressed) -> None:
        self.log("Magnet Bottom")
        self.port_setting["magnet"] = Magnet.BOTTOM
        self.post_message(self.PortSettingChanged(port=self.port, port_setting=self.port_setting))

    @on(Button.Pressed, "#magnet-left")
    def magnet_left(self, event: Button.Pressed) -> None:
        self.log("Magnet Left")
        self.port_setting["magnet"] = Magnet.LEFT
        self.post_message(self.PortSettingChanged(port=self.port, port_setting=self.port_setting))

    @on(Button.Pressed, "#magnet-right")
    def magnet_right(self, event: Button.Pressed) -> None:
        self.log("Magnet Right")
        self.port_setting["magnet"] = Magnet.RIGHT
        self.post_message(self.PortSettingChanged(port=self.port, port_setting=self.port_setting))


class PortEditor(Widget):
    node_data: dict[str, Any]
    node: Hashable

    def __init__(
        self,
        *children: Widget,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        node: Hashable,
        node_data: dict[str, Any],
    ) -> None:
        self.node_data = node_data
        self.node = node
        super().__init__(*children, name=name, id=id, classes=classes, disabled=disabled)

    @dataclass
    class PortChanged(Message):
        node: Hashable
        node_data: dict[str, Any]

    def compose(self) -> ComposeResult:
        ports = self.node_data.get("$ports", {})
        with Vertical():
            yield Button("Add Port", id="add-port")
            with Vertical(id="port-list"):
                if not ports:
                    yield Label("No Ports")
                else:
                    for port, port_setting in ports.items():
                        yield Port(port=port, port_setting=port_setting, id=f"port-{port}")

    @on(Button.Pressed, "#add-port")
    def add_port(self, event: Button.Pressed) -> None:
        self.log("Add Port")
        port_name = str(uuid.uuid4())
        if "$ports" not in self.node_data:
            self.node_data["$ports"] = {}
            self.query_one("#port-list").remove_children()
        self.node_data["$ports"][port_name] = {
            "magnet": Magnet.LEFT,
            "label": "A",
        }
        self.post_message(self.PortChanged(node=self.node, node_data=self.node_data))
        self.query_one("#port-list").mount(
            Port(
                port=port_name,
                port_setting=self.node_data["$ports"][port_name],
                id=f"port-{port_name}",
            ),
            before=0,
        )
        self.refresh()

    @on(Port.DeletePort)
    def delete_port(self, event: Port.DeletePort) -> None:
        self.log("Delete Port")
        del self.node_data["$ports"][event.port]
        if not self.node_data["$ports"]:
            del self.node_data["$ports"]
        self.query_one(f"#port-{event.port}").remove()
        self.post_message(self.PortChanged(node=self.node, node_data=self.node_data))
        self.refresh()

    @on(Port.PortSettingChanged)
    def port_setting_changed(self, event: Port.PortSettingChanged) -> None:
        self.log("Port Setting Changed")
        self.node_data["$ports"][event.port] = event.port_setting
        self.post_message(self.PortChanged(node=self.node, node_data=self.node_data))
        self.refresh()


class StyleEditor(Widget):
    node_data: dict[str, Any]
    node_properties: NodeProperties
    node: Hashable

    def __init__(
        self,
        *children: Widget,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        node: Hashable,
        node_data: dict[str, Any],
        node_properties: NodeProperties,
    ) -> None:
        self.node_data = node_data
        self.node = node
        self.node_properties = node_properties
        super().__init__(*children, name=name, id=id, classes=classes, disabled=disabled)

    @dataclass
    class StyleChanged(Message):
        node: Hashable
        node_data: dict[str, Any]

    def compose(self) -> ComposeResult:
        # TODO with proper property system, defaults are materialized before this
        shape = self.node_properties.shape
        box_type = None

        if isinstance(shape, Box):
            box_type = shape.box_type

        with Vertical():
            yield Label("Shape", classes="section-title")
            with RadioSet(id="shape-selector"):
                yield RadioButton(
                    "Just Content",
                    id="just-content",
                    value=isinstance(shape, JustContent),
                )
                yield RadioButton("Box", id="box", value=isinstance(shape, Box))
            with RadioSet(
                id="box-type-selector",
                classes="invisible" if not isinstance(shape, Box) else None,
            ):
                yield RadioButton("ASCII", id="ascii", value=box_type == box.ASCII)
                yield RadioButton("SQUARE", id="square", value=box_type == box.SQUARE)
                yield RadioButton("MINIMAL", id="minimal", value=box_type == box.MINIMAL)
                yield RadioButton("HORIZONTALS", id="horizontals", value=box_type == box.HORIZONTALS)
                yield RadioButton("ROUNDED", id="rounded", value=box_type == box.ROUNDED)
                yield RadioButton("HEAVY", id="heavy", value=box_type == box.HEAVY)
                yield RadioButton("DOUBLE", id="double", value=box_type == box.DOUBLE)

    @on(RadioSet.Changed, "#shape-selector")
    def shape_changed(self, event: RadioSet.Changed) -> None:
        if event.index == 0:
            self.node_data["$shape"] = "just-content"
            self.query("#box-type-selector").add_class("invisible")
        elif event.index == 1:
            self.query("#box-type-selector").remove_class("invisible")
            self.node_data["$shape"] = "box"
        self.post_message(self.StyleChanged(node=self.node, node_data=self.node_data))

    @on(RadioSet.Changed, "#box-type-selector")
    def box_type_changed(self, event: RadioSet.Changed) -> None:
        if event.pressed.id == "rounded":
            self.node_data["$box-type"] = box.ROUNDED
        elif event.pressed.id == "ascii":
            self.node_data["$box-type"] = box.ASCII
        elif event.pressed.id == "ascii2":
            self.node_data["$box-type"] = box.ASCII2
        elif event.pressed.id == "ascii_double_head":
            self.node_data["$box-type"] = box.ASCII_DOUBLE_HEAD
        elif event.pressed.id == "square":
            self.node_data["$box-type"] = box.SQUARE
        elif event.pressed.id == "square_double_head":
            self.node_data["$box-type"] = box.SQUARE_DOUBLE_HEAD
        elif event.pressed.id == "minimal":
            self.node_data["$box-type"] = box.MINIMAL
        elif event.pressed.id == "minimal_heavy_head":
            self.node_data["$box-type"] = box.MINIMAL_HEAVY_HEAD
        elif event.pressed.id == "minimal_double_head":
            self.node_data["$box-type"] = box.MINIMAL_DOUBLE_HEAD
        elif event.pressed.id == "simple":
            self.node_data["$box-type"] = box.SIMPLE
        elif event.pressed.id == "simple_head":
            self.node_data["$box-type"] = box.SIMPLE_HEAD
        elif event.pressed.id == "simple_heavy":
            self.node_data["$box-type"] = box.SIMPLE_HEAVY
        elif event.pressed.id == "horizontals":
            self.node_data["$box-type"] = box.HORIZONTALS
        elif event.pressed.id == "heavy":
            self.node_data["$box-type"] = box.HEAVY
        elif event.pressed.id == "heavy_edge":
            self.node_data["$box-type"] = box.HEAVY_EDGE
        elif event.pressed.id == "heavy_head":
            self.node_data["$box-type"] = box.HEAVY_HEAD
        elif event.pressed.id == "double":
            self.node_data["$box-type"] = box.DOUBLE
        elif event.pressed.id == "double_edge":
            self.node_data["$box-type"] = box.DOUBLE_EDGE
        elif event.pressed.id == "markdown":
            self.node_data["$box-type"] = box.MARKDOWN
        self.post_message(self.StyleChanged(node=self.node, node_data=self.node_data))


class NodeInspector(Widget):
    node_data: dict[str, Any]
    node_properties: NodeProperties
    node: Hashable

    @dataclass
    class NodeChanged(Message):
        node: Hashable
        node_data: dict[str, Any]
        node_properties: NodeProperties

    def __init__(
        self,
        *children: Widget,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        node_data: dict[str, Any],
        node_properties: NodeProperties,
        node: Hashable,
    ) -> None:
        self.node = node
        self.node_data = node_data
        self.node_properties = node_properties
        self.log(f"Node Properties: {node_properties}")
        super().__init__(*children, name=name, id=id, classes=classes, disabled=disabled)

    def compose(self) -> ComposeResult:
        attr_dct = {k: v for k, v in self.node_data.items() if k.startswith("$")}
        node_dct = {k: v for k, v in self.node_data.items() if not k.startswith("$") and not k.startswith("_")}

        with TabbedContent("Node", "Style", "Ports", "Debug"):
            with Vertical():
                yield Label("Title", classes="section-title")
                yield Input(value=self.node_data["title"], id="title")
                yield Label("Node Dictionary", classes="section-title")
                yield Pretty(node_dct)
            yield StyleEditor(node_data=self.node_data, node=self.node, node_properties=self.node_properties)
            yield PortEditor(node_data=self.node_data, node=self.node)
            with Vertical():
                yield Label("Attributes", classes="section-title")
                yield Pretty(attr_dct)
                yield Pretty(self.node_properties)

    @on(Input.Submitted, "#title")
    def title_changed(self, event: Input.Submitted) -> None:
        self.node_data["title"] = event.control.value
        self.post_message(
            NodeInspector.NodeChanged(node=self.node, node_data=self.node_data, node_properties=self.node_properties)
        )


class Statusbar(Static):
    pass


class GraphArea(Widget):
    current_editor: tuple[Input, Hashable] | None = None
    edge_first_click: Hashable | None = None
    port_first_click: str | None = None
    hover_element: Reactive[Reference | None] = reactive(cast(Reference | None, None))
    selected_element: Reactive[Reference | None] = reactive(cast(Reference | None, None))
    move_selected: bool = False
    current_tool: str = "pointer-tool"

    class ResetTool(Message):
        """Reset the tool in the toolbar."""

    @dataclass
    class ElementSelected(Message):
        element: Reference | None
        element_data: dict[str, Any] | None
        element_properties: NodeProperties | None

    def compose(self) -> ComposeResult:
        graph_view = GraphView(g, zoom=1, scroll_via_viewport=False, id="graph")
        yield graph_view

    def watch_selected_element(self, old_value: Reference | None, new_value: Reference | None) -> None:
        g = self.query_one(GraphView)

        element_message = self.ElementSelected(element=None, element_data=None, element_properties=None)

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
            element_message = self.ElementSelected(
                element=new_value, element_data=g.graph.nodes(data=True)[new_value.ref],
                element_properties=g.node_properties(new_value.ref)
            )

        self.post_message(element_message)

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

    def watch_hover_element(self, old_value: Reference | None, new_value: Reference | None) -> None:
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
            self.log("Resetting hover")
            self.reset_node(old_value.ref)

        if new_value is not None and new_value.type == "node" and not self.move_selected:
            g.update_node(new_value.ref, data={"$style": Style(color="green")})

    def on_click(self, event: events.Click) -> None:
        if self.current_tool == "add-node-tool":
            self.add_node(event.x, event.y)
            self.post_message(self.ResetTool())

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

    def add_edge(
        self,
        u: Hashable,
        v: Hashable,
        start_port: str | None = None,
        end_port: str | None = None,
    ) -> None:
        g = self.query_one(GraphView)
        g.add_edge(
            u,
            v,
            data={
                "$edge-routing-mode": EdgeRoutingMode.ORTHOGONAL,
                "$edge-segment-drawing-mode": EdgeSegmentDrawingMode.BOX,
                "$end-arrow-tip": ArrowTip.ARROW,
                "$start-port": start_port,
                "$end-port": end_port,
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
        if event.element_reference.type == "port":
            g = self.query_one(GraphView)
            if self.current_tool == "add-edge-tool":
                if self.edge_first_click is None:
                    self.port_first_click = event.element_reference.ref[1]
                    self.edge_first_click = event.element_reference.ref[0]
                    g.update_node(self.edge_first_click, data={"$style": Style(color="red")})
                else:
                    g.update_node(self.edge_first_click, data={"$style": None})
                    self.add_edge(
                        self.edge_first_click,
                        event.element_reference.ref[0],
                        self.port_first_click,
                        event.element_reference.ref[1],
                    )
                    self.edge_first_click = None
                    self.port_first_click = None
        elif event.element_reference.type == "node":
            if self.move_selected:
                self.move_selected = False

            g = self.query_one(GraphView)
            if self.current_tool == "add-edge-tool":
                if self.edge_first_click is None:
                    self.edge_first_click = event.element_reference.ref
                    self.port_first_click = None
                    g.update_node(self.edge_first_click, data={"$style": Style(color="red")})
                else:
                    g.update_node(self.edge_first_click, data={"$style": None})
                    self.add_edge(
                        self.edge_first_click,
                        event.element_reference.ref,
                        self.port_first_click,
                        None,
                    )
                    self.edge_first_click = None
                    self.port_first_click = None
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

    def on_graph_view_element_mouse_down(self, event: GraphView.ElementMouseDown) -> None:
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
        if self.move_selected and self.selected_element is not None and self.selected_element.type == "node":
            g = self.query_one(GraphView)
            g.update_node(self.selected_element.ref, position=Offset(x=event.x, y=event.y))


class GraphInspector(Widget):
    selected_element: Reactive[Reference | None] = reactive(cast(Reference | None, None))
    selected_element_data: dict[str, Any] | None = None
    selected_element_properties: NodeProperties | None = None

    def __init__(
        self,
        *children: Widget,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(*children, name=name, id=id, classes=classes, disabled=disabled)

    def compose(self) -> ComposeResult:
        yield Static("Graph Inspector")

    def watch_selected_element(self, old_value: Reference | None, new_value: Reference | None) -> None:
        self.query(Widget).first().remove()
        if new_value is None:
            self.mount(Static("Graph Inspector"))
            return
        match new_value.type:
            case "node":
                self.mount(
                    NodeInspector(
                        node=new_value.ref,
                        node_data=self.selected_element_data,
                        node_properties=self.selected_element_properties,
                    )
                )


class MainScreen(Screen):
    BINDINGS = [("m", "move_node", "Move Node"), ("x", "delete", "Delete Node / Edge")]

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Vertical(
                Toolbar(),
                GraphArea(),
                Footer(),
            ),
            Vertical(GraphInspector(), Statusbar("Status"), id="sidebar"),
        )

    def on_graph_area_reset_tool(self, event: GraphArea.ResetTool) -> None:
        toolbar = self.query_one(Toolbar)
        toolbar.switch_tool("pointer-tool")

    def on_graph_area_element_selected(self, event: GraphArea.ElementSelected) -> None:
        graph_inspector = self.query_one(GraphInspector)
        graph_inspector.selected_element_data = event.element_data
        graph_inspector.selected_element_properties = event.element_properties
        graph_inspector.selected_element = event.element

    def on_toolbar_tool_switched(self, event: Toolbar.ToolSwitched) -> None:
        graph_area = self.query_one(GraphArea)
        graph_area.current_tool = event.tool

    def on_style_editor_style_changed(self, event: StyleEditor.StyleChanged) -> None:
        graph_view = self.query_one(GraphView)
        graph_view.update_node(event.node, data=event.node_data)

    def on_node_inspector_node_changed(self, event: NodeInspector.NodeChanged) -> None:
        graph_view = self.query_one(GraphView)
        graph_view.update_node(event.node, data=event.node_data)

    def on_port_editor_port_changed(self, event: PortEditor.PortChanged) -> None:
        graph_view = self.query_one(GraphView)
        graph_view.update_node(event.node, data=event.node_data)

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
