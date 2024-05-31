from typing import Any, Hashable, cast

from networkx import DiGraph
from textual.events import Resize
from textual import events
from textual.reactive import reactive
from textual.scroll_view import ScrollView
from textual.geometry import Region, Size, Offset
from textual.strip import Strip
from textual.widget import Widget

from netext import ConsoleGraph
from netext.buffer_renderer import render_buffers
from netext.console_graph import AutoZoom, ZoomSpec
from rich.segment import Segment
from netext.geometry.region import Region as NetextRegion
from netext.geometry.point import FloatPoint, Point
from textual.message import Message

from netext.rendering.segment_buffer import Reference


class GraphView(ScrollView):
    zoom: reactive[float | tuple[float, float] | ZoomSpec | AutoZoom] = reactive(
        cast(float | tuple[float, float] | ZoomSpec | AutoZoom, 1.0)
    )
    viewport: reactive[Region | None] = reactive(cast(Region | None, None))

    class ElementEvent(Message):
        """Element event message."""

        def __init__(self, element_reference: Reference, event: events.Event) -> None:
            self.event = event
            self.element_reference = element_reference
            super().__init__()

    class ElementClick(ElementEvent):
        """Element click message."""

    class ElementMove(ElementEvent):
        """Element mouse moved message."""

    class ElementEnter(ElementEvent):
        """Element mouse enter message."""

    class ElementLeave(ElementEvent):
        """Element mouse leave message."""

    class ElementMouseDown(ElementEvent):
        """Element mouse down message."""

    class ElementMouseUp(ElementEvent):
        """Element mouse up message."""

    def __init__(
        self,
        graph: DiGraph,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        zoom: float | tuple[float, float] | ZoomSpec | AutoZoom = 1.0,
        scroll_via_viewport: bool = False,
        **console_graph_kwargs,
    ):
        """Initializes a new instance of the Widget class.

        Args:
            graph: A graph object to be displayed in the widget.
            name: A string representing the name of the widget (optional).
            id: A string representing the ID of the widget (optional).
            classes: A string representing the CSS classes of the widget (optional).
            disabled: A boolean indicating whether the widget is disabled (optional).
            zoom: A float or tuple of floats representing the zoom level of the widget (optional).
            scroll_via_viewport: A boolean indicating whether the widget should scroll via the viewport (optional).
            **console_graph_kwargs: Additional keyword arguments to be passed to the ConsoleGraph constructor.

        Raises:
            ValueError: If both viewport and scroll_via_viewport are specified.

        """

        self._reverse_click_map: dict[tuple[int, int], Reference] = dict()
        self._last_hover: Reference | None = None
        self._console_graph_kwargs = console_graph_kwargs
        self._console_graph: ConsoleGraph = ConsoleGraph(
            graph,
            console=self.app.console,
            max_width=0,
            max_height=0,
            zoom=zoom,
            **console_graph_kwargs,
        )
        self._scroll_via_viewport = scroll_via_viewport
        self._attached_widgets: dict[Hashable, tuple[Widget, bool]] = dict()
        self._attached_widgets_lookup: dict[Widget, Hashable] = dict()
        self._graph: DiGraph = graph
        self._strip_segments: list[list[Segment]] = list()

        super().__init__(name=name, id=id, classes=classes, disabled=disabled)

        self.zoom = zoom
        self._timer = self.set_timer(0, self._resized)

    def _reset_console_graph(self):
        if self.size.width != 0 and self.size.height != 0:
            self._console_graph = ConsoleGraph(
                self._graph,
                console=self.app.console,
                max_width=self.size.width,
                max_height=self.size.height,
                zoom=self._zoom,
                **self._console_graph_kwargs,
            )

    @property
    def graph(self) -> DiGraph:
        """Returns and sets the graph object associated with this widget.

        Returns:
            DiGraph: The graph object associated with this widget.
        """
        return self._graph

    @graph.setter
    def graph(self, graph: DiGraph) -> None:
        self._graph = graph
        self._graph_was_updated()

    def on_resize(self, message: Resize):
        self._resized()

    def attach_widget_to_node(self, widget: Widget, node: Hashable, size: Size | None = None) -> None:
        """
        Attaches a widget to a node in the console graph.

        Args:
            widget (Widget): The textual widget to attach.
            node (Hashable): The node to attach the widget to.
            size (Size | None): The size of the widget, by default uses the node size (optional).
        """

        if node in self._attached_widgets:
            self.detach_widget_from_node(node)

        self._attached_widgets[node] = (widget, size is None)
        self._attached_widgets_lookup[widget] = node
        self.mount(widget)

        node_buffer = self._console_graph.node_buffers[node]

        if size is None:
            widget.styles.width = node_buffer.width
            widget.styles.height = node_buffer.height
        else:
            widget.styles.width = size.width
            widget.styles.height = size.height

        widget.styles.dock = "left"
        widget.styles.offset = self.view_to_widget_coordinates(Point(node_buffer.left_x, node_buffer.top_y))

    def detach_widget_from_node(self, node: Hashable) -> None:
        """Detach a widget from a node.

        Args:
            node (Hashable): The node to detach the widget from.

        Returns:
            None
        """
        widget, _ = self._attached_widgets[node]
        del self._attached_widgets[node]
        del self._attached_widgets_lookup[widget]
        widget.remove()

    def add_node(
        self,
        node: Hashable,
        position: FloatPoint | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        """
        Adds a node to the graph widget.

        Args:
            node: The node to add to the graph.
            position: The position of the node in the graph (optional). If set add the node at the specific
                position in graph space coordinates. If not set the node will be added and the layout will be
                recomputed.
            data: Optional dictionary of node attributes, see
                [ConsoleGraph.add_node][netext.console_graph.ConsoleGraph.add_node] (optional).

        Returns:
            None
        """

        self._console_graph.add_node(node, position, data)
        self._graph.add_node(node, **(data or {}))
        self._graph_was_updated()

    def add_edge(
        self,
        u: Hashable,
        v: Hashable,
        data: dict[str, Any] | None = None,
    ) -> None:
        """
        Adds an edge to the graph widget.

        Args:
            u: The source node of the edge.
            v: The destination node of the edge.
            data: Optional dictionary of edge attributes, see
                [ConsoleGraph.add_edge][netext.console_graph.ConsoleGraph.add_edge] (optional).

        Returns:
            None
        """

        self._console_graph.add_edge(u, v, data)
        self._graph.add_edge(u, v, **(data or {}))
        self._graph_was_updated()

    def remove_node(self, node: Hashable) -> None:
        """Remove a node from the graph  and updates the console graph and the internal graph.

        Args:
            node (Hashable): The node to remove from the graph.

        Returns:
            None
        """
        self._console_graph.remove_node(node)
        self._graph.remove_node(node)
        self._graph_was_updated()

    def remove_edge(self, u: Hashable, v: Hashable) -> None:
        """
        Removes an edge from the graph and updates the console graph and the internal graph.

        Args:
            u (Hashable): The source node of the edge.
            v (Hashable): The destination node of the edge.

        Returns:
            None
        """
        self._console_graph.remove_edge(u, v)
        self._graph.remove_edge(u, v)
        self._graph_was_updated()

    def update_node(
        self,
        node: Hashable,
        position: Offset | None = None,
        data: dict[str, Any] | None = None,
        update_data: bool = True,
    ) -> None:
        """
        Updates a node in the graph and reflects the changes in the console graph.

        See [ConsoleGraph.update_node][netext.console_graph.ConsoleGraph.update_node] for comparison.

        Args:
            node (Hashable): The node to update.
            position (Offset | None, optional): The new position of the node. Defaults to None.
            data (dict[str, Any] | None, optional): The new data to associate with the node. Defaults to None.
            update_data (bool, optional): Whether to merge the data associated with the node. Defaults to True.
        """

        if position is not None:
            node_position: FloatPoint | None = self.to_graph_coordinates(position)
        else:
            node_position = None
        self._console_graph.update_node(node, node_position, data, update_data=update_data)
        self._graph.nodes[node].update(data or {})
        self._graph_was_updated()

    def update_edge(
        self,
        u: Hashable,
        v: Hashable,
        data: dict[str, Any],
        update_data: bool = True,
        update_layout: bool = True,
    ) -> None:
        """
        Updates the edge between nodes `u` and `v` with the given `data`.

        See [ConsoleGraph.update_edge][netext.console_graph.ConsoleGraph.update_edge] for comparison.

        Args:
            u (Hashable): The source node of the edge.
            v (Hashable): The destination node of the edge.
            data (dict[str, Any]): The data to update the edge with.
            update_data (bool, optional): Whether to merge the data of the edge. Defaults to True.
            update_layout (bool, optional): Whether to update the layout of the graph. Defaults to True.

        Returns:
            None
        """
        self._console_graph.update_edge(u, v, data, update_data=update_data, update_layout=update_layout)
        self._graph.edges[u, v].update(data)
        self._graph_was_updated()

    def _resized(self):
        self._console_graph.max_width = self.size.width
        self._console_graph.max_height = self.size.height
        self._strip_segments = self.pre_render_strips()
        self.refresh()

    def watch_zoom(
        self,
        new_zoom: float | tuple[float, float] | ZoomSpec | AutoZoom,
        old_zoom: float | tuple[float, float] | ZoomSpec | AutoZoom,
    ) -> None:
        # TODO check why mypy gets the setter wrong
        if new_zoom != old_zoom:
            self._console_graph.zoom = new_zoom  # type: ignore
            self._zoom = new_zoom
            self._graph_was_updated()

    # Check if this would work with scrolling via viewport
    def widget_to_view_coordinates(self, offset: Offset) -> Point:
        """Converts widget coordinates to view coordinates.

        Args:
            offset (Offset): The offset to convert.

        Returns:
            Point: The converted point.
        """
        p = Point(offset.x, offset.y)
        if self._console_graph is not None:
            full_viewport = self._console_graph.full_viewport
            scroll_x, scroll_y = self.scroll_offset
            return full_viewport.top_left + p - Point(scroll_x, scroll_y)
        return p

    def to_graph_coordinates(self, p: Point | Offset) -> FloatPoint:
        """
        Converts a point or offset to graph coordinates.

        Args:
            p (Point | Offset): The point or offset to convert.

        Returns:
            FloatPoint: The converted point in graph coordinates.
        """
        if isinstance(p, Offset):
            p = self.widget_to_view_coordinates(p)
        if self._console_graph is not None:
            return self._console_graph.to_graph_coordinates(p)
        return FloatPoint(p.x, p.y)

    def graph_to_widget_coordinates(self, p: FloatPoint) -> Offset:
        """Converts a point in graph coordinates to widget coordinates.

        Args:
            p (FloatPoint): The point in graph coordinates.

        Returns:
            Offset: The point in widget coordinates.
        """
        if self._console_graph is not None:
            return self.view_to_widget_coordinates(self._console_graph.to_view_coordinates(p))
        return Offset(0, 0)

    def view_to_widget_coordinates(self, p: Point) -> Offset:
        """
        Converts a point in the view's coordinate system to a point in the widget's coordinate system.

        Args:
            p (Point): The point to convert.

        Returns:
            Offset: The converted point in the widget's coordinate system.
        """
        if self._console_graph is not None:
            full_viewport = self._console_graph.full_viewport
            scroll_x, scroll_y = self.scroll_offset
            coords = p - full_viewport.top_left + Point(scroll_x, scroll_y)
            return Offset(coords.x, coords.y)
        return Offset(p.x, p.y)

    def watch_viewport(
        self,
        new_viewport: Region | None,
        old_viewport: Region | None,
    ) -> None:
        if new_viewport != old_viewport:
            if new_viewport is None:
                self._console_graph.reset_viewport()
            else:
                if self._scroll_via_viewport:
                    raise ValueError("Cannot specify both viewport and scroll_via_viewport=True")

                full_viewport = self._console_graph.full_viewport
                self._console_graph.viewport = NetextRegion(
                    x=full_viewport.x + new_viewport.x,
                    y=full_viewport.y + new_viewport.y,
                    width=new_viewport.width,
                    height=new_viewport.height,
                )
            self._graph_was_updated()

    def _graph_was_updated(self):
        self._strip_segments = self.pre_render_strips()
        self.refresh()

    def refresh(
        self, *regions: Region, repaint: bool = True, layout: bool = False, recompose: bool = False
    ) -> "GraphView":
        if not self._scroll_via_viewport:
            new_size = Size(*self._console_graph.viewport.size.as_tuple())
        else:
            new_size = Size(*self._console_graph.full_viewport.size.as_tuple())
        if new_size != self.virtual_size:
            self.virtual_size = new_size
            self._refresh_scrollbars()

        for node, (widget, resize) in self._attached_widgets.items():
            node_buffer = self._console_graph.node_buffers[node]
            if resize:
                widget.styles.width = node_buffer.width
                widget.styles.height = node_buffer.height
            # TODO node buffer top left should be point
            widget.styles.offset = self.view_to_widget_coordinates(Point(node_buffer.left_x, node_buffer.top_y))
        return super().refresh(*regions, repaint=repaint, layout=layout, recompose=recompose)

    def pre_render_strips(self) -> list[list[Segment]]:
        all_buffers = list(self._console_graph._all_buffers())
        strips, self._reverse_click_map = render_buffers(all_buffers, self._console_graph.viewport)
        return strips

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
        ref = self._reverse_click_map.get(self.widget_to_view_coordinates(Offset(event.x, event.y)).as_tuple())

        if ref != self._last_hover and self._last_hover is not None:
            event.stop()
            self.post_message(GraphView.ElementLeave(self._last_hover, event))
            self._last_hover = None

        if ref is not None:
            if ref != self._last_hover:
                event.stop()
                self.post_message(GraphView.ElementEnter(ref, event))
            else:
                event.stop()
                self.post_message(GraphView.ElementMove(ref, event))
            self._last_hover = ref

    def on_click(self, event: events.Click) -> None:
        ref = self._reverse_click_map.get(self.widget_to_view_coordinates(Offset(event.x, event.y)).as_tuple())

        if ref is not None:
            event.stop()
            self.post_message(GraphView.ElementClick(ref, event))

    def on_mouse_down(self, event: events.MouseDown) -> None:
        ref = self._reverse_click_map.get(self.widget_to_view_coordinates(Offset(event.x, event.y)).as_tuple())

        if ref is not None:
            event.stop()
            self.post_message(GraphView.ElementMouseDown(ref, event))

    def on_mouse_up(self, event: events.MouseDown) -> None:
        ref = self._reverse_click_map.get(self.widget_to_view_coordinates(Offset(event.x, event.y)).as_tuple())

        if ref is not None:
            event.stop()
            self.post_message(GraphView.ElementMouseUp(ref, event))
