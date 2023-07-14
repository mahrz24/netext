from typing import Any, Generic, Hashable, Protocol, Self, TypeGuard, cast

from textual.events import Resize
from textual import events
from textual.reactive import reactive
from textual.scroll_view import ScrollView
from textual.geometry import Region, Size, Offset
from textual.strip import Strip
from textual.widget import Widget

from netext import ConsoleGraph
from netext.buffer_renderer import render_buffers
from netext.console_graph import G, AutoZoom, ZoomSpec
from rich.segment import Segment
from netext.geometry.region import Region as NetextRegion
from netext.geometry.point import Point
from textual.message import Message

from netext.rendering.segment_buffer import Reference


class InitializedGraphView(Protocol[G]):
    _console_graph: ConsoleGraph[G]
    _strip_segments: list[list[Segment]]
    _scroll_via_viewport: bool
    _attached_widgets: dict[Hashable, tuple[Widget, bool]]

    size: Size
    virtual_size: Size

    def _graph_was_updated(self) -> None:
        ...

    def refresh(self) -> None:
        ...

    def pre_render_strips(self) -> list[list[Segment]]:
        ...

    def _to_view_coordinates(self, x: int, y: int) -> tuple[int, int]:
        ...


def _setup_console_graph(graph: "GraphView[G]") -> TypeGuard[InitializedGraphView[G]]:
    if (
        graph.graph is not None
        and graph._console_graph is None
        and graph.size.width != 0
        and graph.size.height != 0
    ):
        graph._console_graph = ConsoleGraph(
            graph.graph,
            console=graph.app.console,
            max_width=graph.size.width,
            max_height=graph.size.height,
            zoom=graph.zoom,
            **graph._console_graph_kwargs,
        )
    return graph._console_graph is not None


class GraphView(ScrollView, Generic[G]):
    graph: reactive[G | None] = reactive(cast(G | None, None))
    zoom: reactive[float | tuple[float, float] | ZoomSpec | AutoZoom] = reactive(
        cast(float | tuple[float, float] | ZoomSpec | AutoZoom, 1.0)
    )
    viewport: reactive[Region | None] = reactive(cast(Region | None, None))

    # TODO: We need to link the parent event here to be able to get modifier keys and such
    class ElementClick(Message):
        """Element click message."""

        def __init__(self, element_reference: Reference, x: int, y: int) -> None:
            self.x = x
            self.y = y
            self.element_reference = element_reference
            super().__init__()

    class ElementMove(Message):
        """Element mouse moved message."""

        def __init__(self, element_reference: Reference, x: int, y: int) -> None:
            self.x = x
            self.y = y
            self.element_reference = element_reference
            super().__init__()

    class ElementEnter(Message):
        """Element mouse enter message."""

        def __init__(self, element_reference: Reference, x: int, y: int) -> None:
            self.x = x
            self.y = y
            self.element_reference = element_reference
            super().__init__()

    class ElementLeave(Message):
        """Element mouse leave message."""

        def __init__(self, element_reference: Reference, x: int, y: int) -> None:
            self.x = x
            self.y = y
            self.element_reference = element_reference
            super().__init__()

    class ElementMouseDown(Message):
        """Element moused down message."""

        def __init__(self, element_reference: Reference, x: int, y: int) -> None:
            self.x = x
            self.y = y
            self.element_reference = element_reference
            super().__init__()

    class ElementMouseUp(Message):
        """Element moused up message."""

        def __init__(self, element_reference: Reference, x: int, y: int) -> None:
            self.x = x
            self.y = y
            self.element_reference = element_reference
            super().__init__()

    def __init__(
        self,
        graph: G | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        zoom: float | tuple[float, float] | ZoomSpec | AutoZoom = 1.0,
        viewport: Region | None = None,
        scroll_via_viewport: bool = False,
        **console_graph_kwargs,
    ):
        self._reverse_click_map = dict()
        self._last_hover: Reference | None = None
        self._console_graph_kwargs = console_graph_kwargs
        self._console_graph: ConsoleGraph[G] | None = None
        self._scroll_via_viewport = scroll_via_viewport
        self._attached_widgets: dict[Hashable, tuple[Widget, bool]] = dict()
        self._attached_widgets_lookup: dict[Widget, Hashable] = dict()
        if scroll_via_viewport and viewport is not None:
            raise ValueError(
                "Cannot specify both viewport and scroll_via_viewport=True"
            )
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self.graph = graph
        self._strip_segments: list[list[Segment]] = list()
        self._timer = self.set_timer(0, self._resized)
        self.zoom = zoom

    def on_resize(self, message: Resize):
        self.log("Graph was resized.")
        self._resized()

    def attach_widget_to_node(
        self, widget: Widget, node: Hashable, size: Size | None = None
    ) -> None:
        if self._console_graph is not None:
            if node in self._attached_widgets:
                self.detach_widget_from_node(node)

            self._attached_widgets[node] = (widget, size is None)
            self._attached_widgets_lookup[widget] = node
            self.mount(widget)

            node_buffer = self._console_graph.node_buffers_current_lod[node]

            if size is None:
                widget.styles.width = node_buffer.width
                widget.styles.height = node_buffer.height
            else:
                widget.styles.width = size.width
                widget.styles.height = size.height

            widget.styles.dock = "left"
            widget.styles.offset = self._to_view_coordinates(
                node_buffer.left_x, node_buffer.top_y
            )

    def detach_widget_from_node(self, node: Hashable) -> None:
        widget, _ = self._attached_widgets[node]
        del self._attached_widgets[node]
        del self._attached_widgets_lookup[widget]
        widget.remove()

    def add_node(
        self,
        node: Hashable,
        position: Offset | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        if self._console_graph is not None:
            if position is not None:
                node_position: Point | None = Point(
                    *self._to_graph_coordinates(position.x, position.y)
                )
            else:
                node_position = position
            self.log(f"Adding node {node} at {node_position}")
            self._console_graph.add_node(node, node_position, data)
            self._graph_was_updated()

    def add_edge(
        self,
        u: Hashable,
        v: Hashable,
        data: dict[str, Any] | None = None,
    ) -> None:
        if self._console_graph is not None:
            self._console_graph.add_edge(u, v, data)
            self._graph_was_updated()

    def remove_node(self, node: Hashable) -> None:
        if self._console_graph is not None:
            self._console_graph.remove_node(node)
            self._graph_was_updated()

    def remove_edge(self, u: Hashable, v: Hashable) -> None:
        if self._console_graph is not None:
            self._console_graph.remove_edge(u, v)
            self._graph_was_updated()

    def update_node(
        self,
        node: Hashable,
        position: Offset | None = None,
        data: dict[str, Any] | None = None,
        update_data: bool = True,
    ) -> None:
        if self._console_graph is not None:
            if position is not None:
                node_position: Point | None = Point(
                    *self._to_graph_coordinates(position.x, position.y)
                )
            else:
                node_position = position
            self.log(f"Adding node {node} at {node_position}")
            self._console_graph.update_node(
                node, node_position, data, update_data=update_data
            )
            self._graph_was_updated()

    def update_edge(self, u: Hashable, v: Hashable, data: dict[str, Any]) -> None:
        if self._console_graph is not None:
            self._console_graph.update_edge(u, v, data)
            self._graph_was_updated()

    def _resized(self):
        if _setup_console_graph(self):
            self._console_graph.max_width = self.size.width
            self._console_graph.max_height = self.size.height
            self._strip_segments = self.pre_render_strips()
            self.refresh()

    def _to_graph_coordinates(self, x: int, y: int) -> tuple[int, int]:
        if self._console_graph is not None:
            full_viewport = self._console_graph.full_viewport
            scroll_x, scroll_y = self.scroll_offset
            return full_viewport.x + x + scroll_x, full_viewport.y + y + scroll_y
        return x, y

    def _to_view_coordinates(self, x: int, y: int) -> tuple[int, int]:
        if self._console_graph is not None:
            full_viewport = self._console_graph.full_viewport
            scroll_x, scroll_y = self.scroll_offset
            return x - full_viewport.x - scroll_x, y - full_viewport.y - scroll_y
        return x, y

    def watch_graph(self, old_graph: G | None, new_graph: G | None) -> None:
        self._graph_was_updated()

    def watch_zoom(
        self,
        new_zoom: float | tuple[float, float] | ZoomSpec | AutoZoom,
    ) -> None:
        if _setup_console_graph(self):
            self._console_graph.zoom = new_zoom
            self._graph_was_updated()

    def watch_viewport(
        self,
        new_viewport: Region | None,
    ) -> None:
        if _setup_console_graph(self):
            if new_viewport is None:
                self._console_graph.reset_viewport()
            else:
                if self._scroll_via_viewport:
                    raise ValueError(
                        "Cannot specify both viewport and scroll_via_viewport=True"
                    )

                full_viewport = self._console_graph.full_viewport
                self._console_graph.viewport = NetextRegion(
                    x=full_viewport.x + new_viewport.x,
                    y=full_viewport.y + new_viewport.y,
                    width=new_viewport.width,
                    height=new_viewport.height,
                )
            self._graph_was_updated()

    def _graph_was_updated(self):
        if _setup_console_graph(self):
            self._strip_segments = self.pre_render_strips()
            self.refresh()
        else:
            self._console_graph = None
            self._strip_segments = []

    def refresh(
        self, *regions: Region, repaint: bool = True, layout: bool = False
    ) -> Self:
        if self._console_graph is not None:
            if not self._scroll_via_viewport:
                new_size = Size(*self._console_graph.viewport.size.as_tuple())
            else:
                new_size = Size(*self._console_graph.full_viewport.size.as_tuple())
            if new_size != self.virtual_size:
                self.virtual_size = new_size
                self._refresh_scrollbars()

            for node, (widget, resize) in self._attached_widgets.items():
                node_buffer = self._console_graph.node_buffers_current_lod[node]
                if resize:
                    widget.styles.width = node_buffer.width
                    widget.styles.height = node_buffer.height
                widget.styles.offset = self._to_view_coordinates(
                    node_buffer.left_x, node_buffer.top_y
                )
        return super().refresh(*regions, repaint=repaint, layout=layout)

    def pre_render_strips(self) -> list[list[Segment]]:
        if self._console_graph is not None:
            all_buffers = list(self._console_graph._all_current_lod_buffers())
            strips, self._reverse_click_map = render_buffers(
                all_buffers, self._console_graph.viewport
            )
            return strips
        else:
            return []

    def watch_scroll_x(self, old_value: float, new_value: float) -> None:
        if self.show_horizontal_scrollbar and round(old_value) != round(new_value):
            self.horizontal_scrollbar.position = round(new_value)
        if self._scroll_via_viewport:
            self._update_scroll_viewport()
        self.refresh()

    def watch_scroll_y(self, old_value: float, new_value: float) -> None:
        if self.show_vertical_scrollbar and round(old_value) != round(new_value):
            self.vertical_scrollbar.position = round(new_value)
        if self._scroll_via_viewport:
            self._update_scroll_viewport()
        self.refresh()

    def _update_scroll_viewport(self) -> None:
        if self._console_graph is not None:
            scroll_x, scroll_y = self.scroll_offset
            full_viewport = self._console_graph.full_viewport
            self._console_graph.viewport = NetextRegion(
                x=full_viewport.x + scroll_x,
                y=full_viewport.y + scroll_y,
                width=self.size.width,
                height=self.size.height,
            )
            self._strip_segments = self.pre_render_strips()

    def render_line(self, y: int) -> Strip:
        scroll_x, scroll_y = self.scroll_offset  # The current scroll position

        if self._scroll_via_viewport:
            scroll_x, scroll_y = 0, 0

        y += scroll_y

        if y < 0 or y >= len(self._strip_segments):
            return Strip.blank(self.size.width)

        return Strip(self._strip_segments[y]).crop(scroll_x, scroll_x + self.size.width)

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._console_graph is not None:
            ref = self._reverse_click_map.get(
                self._to_graph_coordinates(event.x, event.y)
            )

            if ref != self._last_hover and self._last_hover is not None:
                self.post_message(
                    GraphView.ElementLeave(self._last_hover, event.x, event.y)
                )
                self._last_hover = None

            if ref is not None:
                if ref != self._last_hover:
                    self.post_message(GraphView.ElementEnter(ref, event.x, event.y))
                else:
                    self.post_message(GraphView.ElementMove(ref, event.x, event.y))
                self._last_hover = ref

    def on_click(self, event: events.Click) -> None:
        if self._console_graph is not None:
            ref = self._reverse_click_map.get(
                self._to_graph_coordinates(event.x, event.y)
            )

            if ref is not None:
                self.post_message(GraphView.ElementClick(ref, event.x, event.y))

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if self._console_graph is not None:
            ref = self._reverse_click_map.get(
                self._to_graph_coordinates(event.x, event.y)
            )

            if ref is not None:
                self.post_message(GraphView.ElementMouseDown(ref, event.x, event.y))

    def on_mouse_up(self, event: events.MouseDown) -> None:
        if self._console_graph is not None:
            ref = self._reverse_click_map.get(
                self._to_graph_coordinates(event.x, event.y)
            )

            if ref is not None:
                self.post_message(GraphView.ElementMouseUp(ref, event.x, event.y))
