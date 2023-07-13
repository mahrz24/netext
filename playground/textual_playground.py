from netext.textual.widget import GraphView
from textual.app import App, ComposeResult
from typing import Any, Callable, Hashable, cast
from rich.style import Style
from rich import box
from netext.edge_routing.modes import EdgeRoutingMode
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_rendering.arrow_tips import ArrowTip
from textual.widgets import Button
from textual.geometry import Region
from textual.screen import Screen, ModalScreen
from textual.widgets import OptionList, Input, Footer, Placeholder
from textual.widget import Widget
from textual.containers import Horizontal, Vertical

import networkx as nx

g = cast(nx.Graph, nx.binomial_tree(4))


def _render2(n, d, s):
    return f"This is node number #N{n}\nMultiline hi {d.get('title')}"


nx.set_node_attributes(g, Style(color="blue"), "$content-style")
nx.set_node_attributes(g, box.SQUARE, "$box-type")
nx.set_edge_attributes(g, Style(color="red"), "$style")
nx.set_edge_attributes(g, EdgeRoutingMode.ORTHOGONAL, "$edge-routing-mode")
nx.set_edge_attributes(g, EdgeSegmentDrawingMode.BOX, "$edge-segment-drawing-mode")
nx.set_edge_attributes(g, ArrowTip.ARROW, "$end-arrow-tip")
nx.set_edge_attributes(g, ArrowTip.ARROW, "$start-arrow-tip")
nx.set_node_attributes(g, _render2, "$content-renderer")

# class GraphInspector(Widget):
#     graph: reactive[GraphView | None] = reactive(None)

#     def __init__(self, graph: GraphView, **kwargs) -> None:
#         super().__init__(**kwargs)
#         self.graph = graph

#     def compose(self) -> ComposeResult:
#         yield ListView(id="edge-list")

#     def update(self) -> None:
#         edge_list: ListView = self.query_one("#edge-list")
#         edge_list.clear()
#         if self.graph and self.graph._console_graph is not None:
#             for (
#                 key,
#                 value,
#             ) in self.graph._console_graph.edge_buffers_current_lod.items():
#                 boundary = f"{value.boundary_1} {value.boundary_2}"
#                 edge_list.append(ListItem(Static(f"{key}: [{boundary}]")))
#             for (
#                 key,
#                 value,
#             ) in self.graph._console_graph.label_buffers_current_lod.items():
#                 for label in value:
#                     boundary = f"{label.bounding_box}"
#                     edge_list.append(ListItem(Static(f"{key}: [{boundary}]")))


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
        options: list[str] | list[list[str]],
        callback: Callable[[Any], None],
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(callback, name, id, classes)
        self.options = options
        self.multi_select = isinstance(self.options[0], list)
        self.lists = []
        self.args = dict()

    def compose(self) -> ComposeResult:
        if self.multi_select:
            for i, options in enumerate(self.options):
                ol = OptionList(*[str(s) for s in options], id=f"option-list-{i}")
                self.lists.append(ol)
                ol.focus()
                yield ol
            yield Button("Select", id="select-button")
        else:
            yield OptionList(*[str(s) for s in self.options], id="option-list").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.app.pop_screen()
        args = [self.args.get(i) for i, ol in enumerate(self.lists)]
        self.callback(*args)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if not self.multi_select:
            self.app.pop_screen()
            self.callback(self.options[event.option_index])
        else:
            ix = self.lists.index(event.option_list)
            self.args[ix] = self.options[ix][event.option_index]


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
    BINDINGS = []

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Vertical(
                Toolbar(), GraphView(g, zoom=1, scroll_via_viewport=False, id="graph")
            ),
            Vertical(Footer(), Statusbar("Status"), id="footer"),
        )

    # def action_add_edge(self) -> None:
    #     """An action to add a node."""
    #     graph_view = self.query_one(GraphView)

    #     if graph_view:

    #         def _add_edge(u: Hashable, v: Hashable) -> None:
    #             graph_view.add_edge(
    #                 u,
    #                 v,
    #                 data={
    #                     "$edge-routing-mode": EdgeRoutingMode.ORTHOGONAL,
    #                     "$edge-segment-drawing-mode": EdgeSegmentDrawingMode.BOX,
    #                     "$end-arrow-tip": ArrowTip.ARROW,
    #                     "$show": True,
    #                 },
    #             )

    #         self.app.push_screen(
    #             SelectDialog(
    #                 [
    #                     list(graph_view.graph.nodes(data=False)),
    #                     list(graph_view.graph.nodes(data=False)),
    #                 ],
    #                 _add_edge,
    #             )
    #         )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        g = self.query_one(GraphView)
        control = event.control
        node = g._attached_widgets_lookup.get(control)

        if node is not None:
            g.update_node(node, data={"title": control.value})
            g.detach_widget_from_node(node)

    def on_graph_view_element_click(self, event: GraphView.ElementClick) -> None:
        self.log(event.element_reference)
        g = self.query_one(GraphView)
        if event.element_reference.type == "node":
            input_widget = Input(placeholder="First Name")
            input_widget.focus()
            g.attach_widget_to_node(
                widget=input_widget, node=event.element_reference.ref
            )
        # g = self.query_one(GraphView)
        # if g._console_graph is not None:
        #     full_viewport = g._console_graph.full_viewport

        #     node_or_edge = g._reverse_click_map.get(
        #         (full_viewport.x + click.x, full_viewport.y + click.y)
        #     )

        #     if isinstance(node_or_edge, int):
        #         static = Input(placeholder="First Name")
        #         g.mount(static.focus())
        #         node_buffer = g._console_graph.node_buffers_current_lod[node_or_edge]

        #         static.styles.width = node_buffer.width
        #         static.styles.height = node_buffer.height
        #         static.styles.dock = "left"
        #         static.styles.offset = (
        #             node_buffer.left_x - full_viewport.x,
        #             node_buffer.top_y - full_viewport.y,
        #         )

    def on_graph_view_element_move(self, event: GraphView.ElementMove) -> None:
        self.log(event, event.element_reference)

    def on_graph_view_element_mouse_down(
        self, event: GraphView.ElementMouseDown
    ) -> None:
        self.log(event, event.element_reference)

    def on_graph_view_element_mouse_up(self, event: GraphView.ElementMouseUp) -> None:
        self.log(event, event.element_reference)

    def on_graph_view_element_enter(self, event: GraphView.ElementEnter) -> None:
        self.log(event, event.element_reference)

    def on_graph_view_element_leave(self, event: GraphView.ElementLeave) -> None:
        self.log(event, event.element_reference)


class GraphApp(App):
    CSS_PATH = "textual_playground.css"

    def on_mount(self):
        self.push_screen(MainScreen())


app = GraphApp()

app.run()
