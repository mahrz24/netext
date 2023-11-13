from collections import defaultdict
from collections.abc import Hashable
from dataclasses import dataclass
from enum import Enum
from itertools import chain
import itertools
from typing import Any, Generic, Iterable, cast

import networkx as nx
from rich.console import Console, ConsoleOptions, RenderResult
from rich.measure import Measurement

from netext.geometry import Point, Region

from netext.edge_rendering.buffer import EdgeBuffer
from netext.edge_routing.edge import EdgeLayout
from netext.geometry.index import BufferIndex
from netext.geometry.magnet import Magnet, ShapeSide
from netext.geometry.point import FloatPoint

from netext.rendering.segment_buffer import StripBuffer

from netext.buffer_renderer import render_buffers
from netext.edge_rasterizer import rasterize_edge
from netext.layout_engines.engine import LayoutEngine, G
from netext.layout_engines.grandalf import GrandalfSugiyamaLayout
from netext.node_rasterizer import NodeBuffer, rasterize_node

from rich.traceback import install

install(show_locals=False)


class RenderState(Enum):
    INITIAL = "initial"
    """The initial state, no rendering has happened yet."""

    NODE_BUFFERS_RENDERED_FOR_LAYOUT = "node_buffers_rendered_for_layout"
    """The node buffers have been rendered for layout."""

    NODE_LAYOUT_COMPUTED = "node_layout_computed"
    """The node layout has been computed."""

    ZOOMED_POSITIONS_COMPUTED = "zoomed_positions_computed"
    """The zoomed node positions have been computed."""

    NODE_BUFFERS_RENDERED = "node_buffers_rendered"
    """The node buffers have ben rendered for the current lod."""

    EDGES_RENDERED = "edges_rendered"
    """The edges have been rendered for the current lod."""


transition_graph = nx.DiGraph()

transition_graph.add_edge(
    RenderState.INITIAL,
    RenderState.NODE_BUFFERS_RENDERED_FOR_LAYOUT,
    transition="render_node_buffers_for_layout",
)
transition_graph.add_edge(
    RenderState.NODE_BUFFERS_RENDERED_FOR_LAYOUT,
    RenderState.NODE_LAYOUT_COMPUTED,
    transition="compute_node_layout",
)
transition_graph.add_edge(
    RenderState.NODE_LAYOUT_COMPUTED,
    RenderState.ZOOMED_POSITIONS_COMPUTED,
    transition="compute_zoomed_positions",
)
transition_graph.add_edge(
    RenderState.ZOOMED_POSITIONS_COMPUTED,
    RenderState.NODE_BUFFERS_RENDERED,
    transition="render_node_buffers",
)

transition_graph.add_edge(
    RenderState.NODE_BUFFERS_RENDERED,
    RenderState.EDGES_RENDERED,
    transition="render_edges",
)


class AutoZoom(Enum):
    FIT = "fit"
    """Fit the graph into the viewport."""
    FIT_PROPORTIONAL = "fit_proportional"
    """Fit the graph into the viewport, but keep the aspect ratio."""


@dataclass
class ZoomSpec:
    x: float
    """Scaling along the x-axis."""
    y: float
    """Scaling along the y-axis."""


class ConsoleGraph(Generic[G]):
    def __init__(
        self,
        graph: G,
        # see https://github.com/python/mypy/issues/3737
        layout_engine: LayoutEngine[G] = GrandalfSugiyamaLayout[G](),  # type: ignore
        console: Console = Console(),
        viewport: Region | None = None,
        max_width: int | None = None,
        max_height: int | None = None,
        zoom: float | tuple[float, float] | ZoomSpec | AutoZoom = 1.0,
    ):
        """
        A console representation of a networkx graph.

        The class conforms to the rich console protocol and can be printed
        as any other rich renderable. You can pass a layout engine and a
        specific console that will be used for rendering.

        Rendering of nodes and edges happens on object creation and the
        object size is determined by the graph (no reactive rendering).

        Args:
            graph (G): A networkx graph object (see [networkx.Graph][] or [networkx.DiGraph][]).
            layout_engine (LayoutEngine[G], optional): The layout engine used.
            console (Console, optional): The rich console driver used to render.
            viewport (Region, optional): The viewport to render. Defaults to the whole graph.
            zoom (float | tuple[float, float] | ZoomSpec | AutoZoom, optional): The zoom level, either a float, a
                tuple of zoom in x and y direction or a zoom spec / auto zoom mode. Defaults to 1.0.
        """
        self._viewport = viewport
        self._render_state = RenderState.INITIAL

        if isinstance(zoom, float) or isinstance(zoom, int):
            zoom = ZoomSpec(zoom, zoom)
        elif isinstance(zoom, tuple):
            zoom = ZoomSpec(zoom[0], zoom[1])

        self.console = console
        self._zoom: ZoomSpec | AutoZoom = zoom

        self._zoom_factor: float | None = None
        self._max_width = max_width
        self._max_height = max_height

        self.layout_engine: LayoutEngine[G] = layout_engine
        self._nx_graph: G = cast(G, graph.copy())

        self.node_buffers_for_layout: dict[Hashable, NodeBuffer] = dict()
        self.node_buffers: dict[Hashable, NodeBuffer] = dict()

        self.port_buffers: dict[Hashable, list[StripBuffer]] = dict()

        self.node_positions: dict[Hashable, FloatPoint] = dict()

        self.edge_buffers: dict[tuple[Hashable, Hashable], EdgeBuffer] = dict()
        self.edge_layouts: dict[tuple[Hashable, Hashable], EdgeLayout] = dict()

        self.edge_label_buffers: dict[
            tuple[Hashable, Hashable], list[StripBuffer]
        ] = dict()

        self.port_side_assignments: dict[
            Hashable, dict[ShapeSide, list[str]]
        ] = defaultdict(lambda: defaultdict(list))
        self.port_sides: dict[Hashable, dict[str, ShapeSide]] = defaultdict(dict)
        self.port_positions: dict[
            Hashable, dict[str, tuple[Point, Point | None]]
        ] = defaultdict(dict)

        self.node_idx: BufferIndex[NodeBuffer, None] = BufferIndex()
        self.edge_idx: BufferIndex[EdgeBuffer, EdgeLayout] = BufferIndex()

    def _require(self, required_state: RenderState):
        if required_state in nx.descendants(transition_graph, self._render_state):
            self._transition_to(required_state)

    def _transition_to(self, target_state: RenderState):
        path = nx.shortest_path(transition_graph, self._render_state, target_state)
        for u, v in zip(path, path[1:]):
            el = transition_graph.edges[u, v]
            transition = el["transition"]
            transition_func = getattr(self, f"_transition_{transition}")
            transition_func()
            self._render_state = v

    def _reset_render_state(self, new_state: RenderState) -> None:
        if self._render_state in nx.descendants(transition_graph, new_state):
            self._render_state = new_state

    @property
    def zoom(self) -> ZoomSpec | AutoZoom:
        """The zoom level of the graph.

        Can be set either to a float, a tuple of zoom in x and y direction or a
        zoom spec / auto zoom mode. Defaults to 1.0, always returns a
        ZoomSpec or AutoZoom, so a float or tuple is converted to a ZoomSpec.
        """
        return self._zoom

    @zoom.setter
    def zoom(self, value: float | tuple[float, float] | ZoomSpec | AutoZoom) -> None:
        if isinstance(value, float) or isinstance(value, int):
            value = ZoomSpec(float(value), float(value))
        elif isinstance(value, tuple):
            value = ZoomSpec(value[0], value[1])
        if self._zoom != value:
            self._zoom = value
            self._reset_render_state(RenderState.NODE_LAYOUT_COMPUTED)

    @property
    def max_width(self) -> int | None:
        """The maximum width of the graph in characters or None if no maximum width is set.
        """
        return self._max_width

    @max_width.setter
    def max_width(self, value: int | None) -> None:
        if self._max_width != value:
            self._max_width = value
            if self._zoom is AutoZoom.FIT or self._zoom is AutoZoom.FIT_PROPORTIONAL:
                self._reset_render_state(RenderState.NODE_LAYOUT_COMPUTED)

    @property
    def max_height(self) -> int | None:
        """The maximum height of the graph in characters as integer or None if no maximum height is set.
        """
        return self._max_height

    @max_height.setter
    def max_height(self, value: int | None) -> None:
        if self._max_height != value:
            self._max_height = value
            if self._zoom is AutoZoom.FIT or self._zoom is AutoZoom.FIT_PROPORTIONAL:
                self._reset_render_state(RenderState.NODE_LAYOUT_COMPUTED)

    @property
    def full_viewport(self) -> Region:
        """The full viewport of the graph that is spanned by the whole graph."""
        return self._unconstrained_viewport()

    @property
    def viewport(self) -> Region:
        """The viewport that is set by the user (or the full viewport if none is set).
        """
        if self._viewport is not None:
            return self._viewport
        return self._unconstrained_viewport()

    @viewport.setter
    def viewport(self, value: Region) -> None:
        self._viewport = value
        self._reset_render_state(RenderState.ZOOMED_POSITIONS_COMPUTED)

    def reset_viewport(self) -> None:
        self._viewport = None

    def add_node(
        self,
        node: Hashable,
        position: FloatPoint | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Add a node to the console graph.

        Args:
            node (Hashable): The node to add.
            position (FloatPoint | None): If set add the node at the specific position in graph
                space coordinates.
            data (dict[str, Any] | None): The data and attributes of the node.
        """
        self._require(RenderState.EDGES_RENDERED)

        if data is None:
            data = dict()

        self._nx_graph.add_node(node, **data)

        # Add to node buffers for layout
        self.node_buffers_for_layout[node] = rasterize_node(
            self.console, node, cast(dict[str, Any], data)
        )

        # Determine port side assignment
        for current_port_name, port_settings in sorted(
            data.get("$ports", {}).items(), key=lambda x: x[1].get("key", 0)
        ):
            port_magnet = port_settings.get("magnet", Magnet.LEFT)

            if port_magnet == Magnet.CENTER or port_magnet == Magnet.CLOSEST:
                port_magnet = Magnet.LEFT
            port_side = ShapeSide(port_magnet.value)
            self.port_sides[node][current_port_name] = port_side
            self.port_side_assignments[node][port_side].append(current_port_name)

        self.node_buffers[node] = rasterize_node(
            self.console,
            node,
            data,
            port_side_assignments=self.port_side_assignments[node],
        )

        if position is not None:
            node_position = cast(FloatPoint, position)
            node_position += self.offset
            self.node_positions[node] = node_position
            self.node_buffers[node].center = Point(
                round(node_position.x * self.zoom_x),
                round(node_position.y * self.zoom_y),
            )

            # Then we recompute zoom (in case we have a zoom to fit)
            zoom_factor = self._zoom_factor if self._zoom_factor is not None else 0
            if (
                self._zoom is AutoZoom.FIT
                or self._zoom is AutoZoom.FIT_PROPORTIONAL
                or self._zoom_factor is None
            ):
                zoom_x, zoom_y = self._compute_current_zoom()
                zoom_factor = min([zoom_x, zoom_y])

            if zoom_factor != self._zoom_factor:
                self._zoom_factor = zoom_factor
                self._reset_render_state(RenderState.NODE_LAYOUT_COMPUTED)
                return

            lod = determine_lod(data, zoom_factor)
            self._determine_port_positions(node, lod=lod, data=data)

            position_view_space = Point(
                round(node_position.x * self.zoom_x),
                round(node_position.y * self.zoom_y),
            )
            self.node_buffers[node].center = position_view_space

            self.node_idx.insert(self.node_buffers[node])

            self._render_port_buffer_for_node(node)
        else:
            self._reset_render_state(RenderState.NODE_BUFFERS_RENDERED_FOR_LAYOUT)

    def add_edge(
        self, u: Hashable, v: Hashable, data: dict[str, Any] | None = None
    ) -> None:
        """Add an edge between existing nodes in the graph.

        Args:
            u (Hashable): The source node.
            v (Hashable): The target node.
            data (dict[str, Any] | None, optional): The data and attributes of the edge.

        Raises:
            ValueError: Raised if one of the edges does not exist in the graph.
        """

        self._require(RenderState.EDGES_RENDERED)

        edge_buffer: EdgeBuffer | None = None
        edge_layout: EdgeLayout | None = None
        label_nodes: list[StripBuffer] | None = None

        if self._zoom_factor is None:
            raise RuntimeError(
                "You can only add edges once the zoom factor has been computed"
            )

        if u not in self._nx_graph.nodes:
            raise ValueError(f"Node {u} does not exist in graph")
        if v not in self._nx_graph.nodes:
            raise ValueError(f"Node {v} does not exist in graph")

        if (u, v) in self._nx_graph.edges:
            return

        if data is None:
            data = dict()

        self._nx_graph.add_edge(u, v, **data)

        edge_lod = determine_lod(data, self._zoom_factor)

        result = rasterize_edge(
            self.console,
            self.node_buffers[u],
            self.node_buffers[v],
            list(self.node_buffers.values()),
            list(self.edge_layouts.values()),
            data,
            self.node_idx,
            self.edge_idx,
            edge_lod,
            port_positions=self.port_positions,
        )

        if result is not None:
            edge_buffer, edge_layout, label_nodes = result

        if edge_buffer is not None:
            self.edge_idx.insert(edge_buffer, edge_layout)
            self.edge_buffers[(u, v)] = edge_buffer
        if label_nodes is not None:
            self.edge_label_buffers[(u, v)] = label_nodes
        if edge_layout is not None:
            self.edge_layouts[(u, v)] = edge_layout

        self._render_port_buffer_for_node(u)
        self._render_port_buffer_for_node(v)

    def remove_node(self, node: Hashable) -> None:
        """Removes the specified node from the graph, along with any edges that are connected to it.

        Args:
            node (Hashable): The node to remove.

        Returns:
            None
        """

        self._require(RenderState.EDGES_RENDERED)

        edges = list(self._nx_graph.edges())
        for u, v in edges:
            if u == node or v == node:
                self.remove_edge(u, v)

        self.node_positions.pop(node)
        self.node_buffers_for_layout.pop(node)
        node_buffer = self.node_buffers.pop(node)

        self.port_buffers.pop(node, None)
        self.port_positions.pop(node, None)
        self.port_side_assignments.pop(node, None)

        if node_buffer is not None:
            self.node_idx.delete(node_buffer)

        self._nx_graph.remove_node(node)

    def remove_edge(self, u: Hashable, v: Hashable) -> None:
        """Removes an edge from the graph.

        Args:
            u (Hashable): The source node of the edge.
            v (Hashable): The target node of the edge.

        Returns:
            None
        """
        self._require(RenderState.EDGES_RENDERED)

        self.node_buffers[v].disconnect(u)
        self.node_buffers[u].disconnect(v)

        print(self.node_buffers[u].connected_ports)
        print(self.node_buffers[v].connected_ports)

        self._nx_graph.remove_edge(u, v)

        edge_buffer = self.edge_buffers.pop((u, v))
        self.edge_label_buffers.pop((u, v))
        self.edge_idx.delete(edge_buffer)

        self._render_port_buffer_for_node(u)
        self._render_port_buffer_for_node(v)
        print(self.port_buffers)
        print(self.node_buffers[u].connected_ports)
        print(self.node_buffers[v].connected_ports)

    def update_node(
        self,
        node: Hashable,
        position: FloatPoint | None = None,
        data: dict[str, Any] | None = None,
        update_data: bool = True,
    ) -> None:
        """Update a node position or attributes (data).

        Args:
            node (Hashable): The node to update.
            position (FloatPoint | None, optional): A new position if the node should be moved, by default None.
            data (dict[str, Any] | None, optional): A new or updated data dictionary, by default None.
            update_data (bool, optional): Whether to replace or update the data dictionary, by default True.

        Returns:
            None
        """
        self._require(RenderState.EDGES_RENDERED)
        force_edge_rerender = False

        if data is None and position is None:
            return

        connected_ports = self.node_buffers[node].connected_ports

        if data is not None:
            # Replace the data of the node with the new data
            if update_data:
                new_data = dict(self._nx_graph.nodes[node], **data)
            else:
                new_data = data

            self._nx_graph.nodes[node].update(new_data)
            old_position = self.node_buffers[node].center

            # Update node buffers for layout
            self.node_buffers_for_layout[node] = rasterize_node(
                self.console, node, cast(dict[str, Any], new_data)
            )

            # Update port side assignment

            # Determine port side assignment
            # TODO this is duplicated
            self.port_sides[node] = dict()
            self.port_side_assignments[node] = defaultdict(list)
            for current_port_name, port_settings in sorted(
                new_data.get("$ports", {}).items(), key=lambda x: x[1].get("key", 0)
            ):
                port_magnet = port_settings.get("magnet", Magnet.LEFT)

                if port_magnet == Magnet.CENTER or port_magnet == Magnet.CLOSEST:
                    port_magnet = Magnet.LEFT
                port_side = ShapeSide(port_magnet.value)
                self.port_sides[node][current_port_name] = port_side
                self.port_side_assignments[node][port_side].append(current_port_name)

            new_node = rasterize_node(
                self.console,
                node,
                new_data,
                port_side_assignments=self.port_side_assignments[node],
            )

            old_node = self.node_buffers[node]
            new_node.center = old_position
            self.node_buffers[node] = new_node

            # If the data change, triggered a change of the shape, we need to rerender the edges
            if new_node.shape.polygon(new_node) != old_node.shape.polygon(old_node):
                force_edge_rerender = True

        data = cast(dict[str, Any], self._nx_graph.nodes(data=True)[node])

        force_edge_rerender = (
            force_edge_rerender or (position is not None) or "$ports" in data
        )

        if position is None:
            node_position = self.node_positions[node]
            zoom_factor = self._zoom_factor if self._zoom_factor is not None else 0
        else:
            node_position = cast(FloatPoint, position)
            node_position += self.offset
            self.node_positions[node] = node_position
            self.node_buffers[node].center = Point(
                round(node_position.x * self.zoom_x),
                round(node_position.y * self.zoom_y),
            )
            self.node_buffers[node].port_positions = defaultdict(dict)

            # Then we recompute zoom (in case we have a zoom to fit)
            zoom_factor = self._zoom_factor if self._zoom_factor is not None else 0
            if (
                self._zoom is AutoZoom.FIT
                or self._zoom is AutoZoom.FIT_PROPORTIONAL
                or self._zoom_factor is None
            ):
                zoom_x, zoom_y = self._compute_current_zoom()
                zoom_factor = min([zoom_x, zoom_y])

            if zoom_factor != self._zoom_factor:
                self._zoom_factor = zoom_factor
                self._reset_render_state(RenderState.NODE_LAYOUT_COMPUTED)
                return

        lod = determine_lod(data, zoom_factor)

        if lod != 1:
            self.node_buffers[node] = rasterize_node(
                self.console,
                node,
                data,
                lod=lod,
                port_side_assignments=self.port_side_assignments[node],
            )

        # This seems quite weird to keep
        # TODO also ports could have changed with data update needs some proper treatment
        self.node_buffers[node].connected_ports = connected_ports

        self._determine_port_positions(node, lod=lod, data=data)
        self._render_port_buffer_for_node(node)

        affected_edges: list[tuple[Hashable, Hashable]] = []

        position_view_space = Point(
            round(node_position.x * self.zoom_x), round(node_position.y * self.zoom_y)
        )
        self.node_buffers[node].center = position_view_space

        for v in nx.all_neighbors(self._nx_graph, node):
            if (node, v) in self.edge_buffers:
                affected_edges.append((node, v))
            if (v, node) in self.edge_buffers:
                affected_edges.append((v, node))

        self.node_idx.update(self.node_buffers[node])

        if affected_edges and force_edge_rerender:
            for u, v in affected_edges:
                self.edge_buffers.pop((u, v), None)
                self.edge_label_buffers.pop((u, v), None)
                self.update_edge(u, v, self._nx_graph.edges[u, v], update_data=False)

    def to_graph_coordinates(self, p: Point) -> FloatPoint:
        """Converts a point from view coordinates to graph coordinates.

        This means applying the inverse zoom and offset to the point.

        Args:
            p (Point): The point to convert.

        Returns:
            FloatPoint: The converted point in graph coordinates.
        """
        return FloatPoint(
            p.x / self.zoom_x - self.offset.x, p.y / self.zoom_y - self.offset.y
        )

    def to_view_coordinates(self, p: FloatPoint) -> Point:
        """Converts a point from graph coordinates to view coordinates.

        This means applying the zoom and offset to the point.

        Args:
            p (FloatPoint): The point to convert.

        Returns:
            Point: The converted point in view coordinates.
        """
        return Point(
            round((self.offset.x + p.x) * self.zoom_x),
            round((self.offset.y + p.y) * self.zoom_y),
        )

    def update_edge(
        self,
        u: Hashable,
        v: Hashable,
        data: dict[str, Any],
        update_data: bool = True,
        update_layout: bool = True,
    ) -> None:
        """Update edge attributes (data).

        Args:
            u (Hashable): The source node of the edge.
            v (Hashable): The target node of the edge.
            data (dict[str, Any]): The new or updated data dictionary.
            update_data (bool, optional): Whether to replace or update the data dictionary, by default True.
            update_layout (bool, optional): Whether to update the layout of the edge, by default True.

        Raises:
            RuntimeError: If the zoom factor has not been computed yet.

        Returns:
            None

        """
        self._require(RenderState.EDGES_RENDERED)

        # This should not happen as we require the render state to have zoomed positions computed.
        if self._zoom_factor is None:
            raise RuntimeError(
                "You can only update edges once the zoom factor has been computed"
            )

        old_data = self._nx_graph.edges[u, v]
        data = dict(old_data, **data) if update_data else data
        self._nx_graph.edges[u, v].update(data)

        edge_buffer: EdgeBuffer | None = None
        edge_layout: EdgeLayout | None = None
        label_nodes: list[StripBuffer] | None = None

        old_edge_layout = None
        if not update_layout:
            old_edge_layout = self.edge_layouts.get((u, v))

        self.node_buffers[v].disconnect(u)
        self.node_buffers[u].disconnect(v)

        del self.edge_layouts[(u, v)]

        edge_lod = determine_lod(data, self._zoom_factor)

        result = rasterize_edge(
            self.console,
            self.node_buffers[u],
            self.node_buffers[v],
            list(self.node_buffers.values()),
            list(self.edge_layouts.values()),
            data,
            self.node_idx,
            self.edge_idx,
            edge_lod,
            edge_layout=old_edge_layout,
            port_positions=self.port_positions,
        )
        self._render_port_buffer_for_node(u)
        self._render_port_buffer_for_node(v)

        if result is not None:
            edge_buffer, edge_layout, label_nodes = result
        if edge_buffer is not None:
            self.edge_idx.update(edge_buffer, edge_layout)
            self.edge_buffers[(u, v)] = edge_buffer
        if label_nodes is not None:
            self.edge_label_buffers[(u, v)] = label_nodes
        if edge_layout is not None:
            self.edge_layouts[(u, v)] = edge_layout

    def layout(self) -> None:
        self._reset_render_state(RenderState.NODE_BUFFERS_RENDERED_FOR_LAYOUT)

    def _transition_render_node_buffers_for_layout(self) -> None:
        # First we create the node buffers, this allows us to pass the sizing information to the
        # layout engine. For each node in the graph we generate a node buffer that contains the
        # segments to render the node and metadata where to place the buffer.
        self.node_buffers_for_layout = {
            node: rasterize_node(self.console, node, cast(dict[str, Any], data))
            for node, data in self._nx_graph.nodes(data=True)
        }

    def _transition_compute_node_layout(self) -> None:
        # Store the node buffers in the graph itself
        nx.set_node_attributes(
            self._nx_graph, self.node_buffers_for_layout, "_netext_node_buffer"
        )

        # Position the nodes and store these original positions
        self.node_positions = self.layout_engine(self._nx_graph)
        self.offset: FloatPoint = FloatPoint(0, 0)

        if self.node_positions:
            x_positions = [pos.x for _, pos in self.node_positions.items()]
            y_positions = [pos.y for _, pos in self.node_positions.items()]
            # Center node positions around the midpoint of all nodes
            min_x = min(x_positions)
            max_x = max(x_positions)
            min_y = min(y_positions)
            max_y = max(y_positions)

            # We add 0.25 to the offset to make sure we do not get rounding errors
            # Otherwise nodes that have different coordinates originally end up in
            # the same position after rounding.
            self.offset = FloatPoint(
                -min_x - (max_x - min_x) / 2 + 0.25, -min_y - (max_y - min_y) / 2 + 0.25
            )

            self.node_positions = {
                node: pos + self.offset for node, pos in self.node_positions.items()
            }

        for node, position in self.node_positions.items():
            self.node_buffers_for_layout[node].center = Point(
                x=round(position.x), y=round(position.y)
            )

        # TODO Split off into own step
        for node, data in self._nx_graph.nodes(data=True):
            if "$ports" in data:
                for current_port_name, port_settings in sorted(
                    data.get("$ports", {}).items(), key=lambda x: x[1].get("key", 0)
                ):
                    port_magnet = port_settings.get("magnet", Magnet.CLOSEST)

                    if port_magnet == Magnet.CENTER or port_magnet == Magnet.CLOSEST:
                        # Determine the port magnet
                        port_side = ShapeSide.LEFT
                        neighbours = self._nx_graph.neighbors(node)
                        for v_node in neighbours:
                            if (node, v_node) in self._nx_graph.edges:
                                if (
                                    self._nx_graph.edges[(node, v_node)].get(
                                        "$start-port"
                                    )
                                    == current_port_name
                                ):
                                    port_side = ShapeSide(
                                        self.node_buffers_for_layout[node]
                                        .get_closest_magnet(
                                            self.node_buffers_for_layout[v_node].center
                                        )
                                        .value
                                    )
                                elif (
                                    self._nx_graph.edges[(v_node, node)].get(
                                        "$end-port"
                                    )
                                    == current_port_name
                                ):
                                    port_side = ShapeSide(
                                        self.node_buffers_for_layout[node]
                                        .get_closest_magnet(
                                            self.node_buffers_for_layout[v_node].center
                                        )
                                        .value
                                    )

                    else:
                        port_side = ShapeSide(port_magnet.value)

                    self.port_sides[node][current_port_name] = port_side
                    self.port_side_assignments[node][port_side].append(
                        current_port_name
                    )

    def _transition_compute_zoomed_positions(self) -> None:
        zoom_x, zoom_y = self._compute_current_zoom()
        self.zoom_x = zoom_x
        self.zoom_y = zoom_y
        self._zoom_factor = min([zoom_x, zoom_y])

    def _compute_current_zoom(self):
        if self.node_positions:
            max_node_x = max([pos.x for pos in self.node_positions.values()])
            max_node_y = max([pos.y for pos in self.node_positions.values()])
            min_node_x = min([pos.x for pos in self.node_positions.values()])
            min_node_y = min([pos.y for pos in self.node_positions.values()])

            # Compute the zoom value for both axes
            max_buffer_width = max(
                [buffer.width for buffer in self.node_buffers_for_layout.values()]
            )
            max_buffer_height = max(
                [buffer.height for buffer in self.node_buffers_for_layout.values()]
            )

            max_width = (max_node_x - min_node_x) + max_buffer_width + 2
            max_height = (max_node_y - min_node_y) + max_buffer_height + 2

            match self._zoom:
                case AutoZoom.FIT:
                    if self.max_width is None or self.max_height is None:
                        raise ValueError(
                            "AutoZoom.FIT is onlye allowed if the maximum renderable"
                            " width and height is known."
                        )
                    zoom_x = self.max_width / max_width
                    zoom_y = self.max_height / max_height
                case AutoZoom.FIT_PROPORTIONAL:
                    if self.max_width is None or self.max_height is None:
                        raise ValueError(
                            "AutoZoom.FIT is only allowed if the maximum renderable"
                            " width and height is known."
                        )
                    zoom_x = self.max_width / max_width
                    zoom_y = self.max_height / max_height
                    zoom_y = zoom_x = min(zoom_x, zoom_y)
                case ZoomSpec(x, y):
                    zoom_x = x
                    zoom_y = y
                case _:
                    raise ValueError(f"Invalid zoom value {self._zoom}")
        else:
            zoom_x = 1
            zoom_y = 1
        return zoom_x, zoom_y

    def _transition_render_node_buffers(self) -> None:
        if self._zoom_factor is None:
            raise RuntimeError(
                "Invalid transition, lod buffers can only be rendered once zoom is"
                " computed."
            )

        for node, data in self._nx_graph.nodes(data=True):
            lod = determine_lod(data, self._zoom_factor)
            # Get the zoomed position of the node
            position = self.node_positions[node]
            position_view_space = Point(
                round(position.x * self.zoom_x), round(position.y * self.zoom_y)
            )

            node_buffer = rasterize_node(
                self.console,
                node,
                data,
                lod=lod,
                port_side_assignments=self.port_side_assignments[node],
            )
            node_buffer.center = position_view_space
            self.node_buffers[node] = node_buffer

            self._determine_port_positions(node, lod, data)

    def _determine_port_positions(self, node: Hashable, lod: int, data: dict[str, Any]):
        # Determine the port positions as this is now possible
        if "$ports" in data:
            for current_port_name, _ in sorted(
                data.get("$ports", {}).items(), key=lambda x: x[1].get("key", 0)
            ):
                port_side = self.port_sides[node][current_port_name]
                pos, pos_helper = self.node_buffers[node].get_port_position(
                    port_name=current_port_name,
                    lod=lod,
                    port_side=port_side,
                    ports_on_side=self.port_side_assignments[node][port_side],
                )
                self.port_positions[node][current_port_name] = (pos, pos_helper)

    def _transition_render_edges(self) -> None:
        if self._zoom_factor is None:
            raise RuntimeError(
                "Invalid transition, lod buffers can only be rendered once zoom is"
                " computed."
            )

        # Now we rasterize the edges

        # Iterate over all edges (so far in no particular order)
        self.node_idx.reset()
        self.edge_idx.reset()

        edge_layouts: list[EdgeLayout] = []

        all_node_buffers = []
        for _, node_buffer in self.node_buffers.items():
            self.node_idx.insert(node_buffer)
            all_node_buffers.append(node_buffer)

        for u, v, data in self._nx_graph.edges(data=True):
            edge_lod = determine_lod(data, self._zoom_factor)

            result = rasterize_edge(
                self.console,
                self.node_buffers[u],
                self.node_buffers[v],
                all_node_buffers,
                edge_layouts,
                data,
                self.node_idx,
                self.edge_idx,
                edge_lod,
                port_positions=self.port_positions,
            )

            if result is None:
                continue

            edge_buffer, edge_layout, label_nodes = result

            if edge_buffer is not None:
                self.edge_idx.insert(edge_buffer, edge_layout)
                self.edge_buffers[(u, v)] = edge_buffer
            if label_nodes is not None:
                self.edge_label_buffers[(u, v)] = label_nodes
            if edge_layout is not None:
                edge_layouts.append(edge_layout)
                self.edge_layouts[(u, v)] = edge_layout

        # Also render the port buffers now
        # TODO move to its own step
        self._render_port_buffers()

    def _render_port_buffers(self) -> None:
        if self._zoom_factor is None:
            raise RuntimeError(
                "Invalid transition, lod buffers can only be rendered once zoom is"
                " computed."
            )

        for node in self._nx_graph.nodes:
            self._render_port_buffer_for_node(node)

    def _render_port_buffer_for_node(self, node):
        if self._zoom_factor is None:
            raise RuntimeError(
                "Invalid transition, lod buffers can only be rendered once zoom is"
                " computed."
            )

        node_buffer = self.node_buffers[node]
        lod = determine_lod(self._nx_graph.nodes[node], self._zoom_factor)
        self.port_buffers[node] = node_buffer.get_port_buffers(
            self.console,
            lod,
            self.port_side_assignments[node],
            self.port_sides[node],
        )

    def _all_buffers(self) -> Iterable[StripBuffer]:
        self._require(RenderState.EDGES_RENDERED)
        # Get graph subview
        visible_nodes = nx.subgraph_view(
            self._nx_graph,
            filter_node=lambda n: self._nx_graph.nodes[n].get("$show", True),
        )

        node_buffers = [
            node_buffer
            for node, node_buffer in self.node_buffers.items()
            if node in visible_nodes
        ]

        port_buffers = [
            port_buffers
            for node, port_buffers in self.port_buffers.items()
            if node in visible_nodes
        ]
        return chain(
            node_buffers,
            self.edge_buffers.values(),
            itertools.chain(*self.edge_label_buffers.values()),
            itertools.chain(*port_buffers),
        )

    def _unconstrained_viewport(self) -> Region:
        regions = [buffer.region for buffer in self._all_buffers()]

        if not regions:
            return Region(0, 0, 0, 0)

        return Region.union(regions)

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        self.max_width = options.max_width
        self.max_height = options.max_height

        self._require(RenderState.EDGES_RENDERED)

        strips, _ = render_buffers(
            self._all_buffers(),
            self.viewport,
        )

        yield from itertools.chain(*[strip + [""] for strip in strips])

    def __rich_measure__(
        self, console: Console, options: ConsoleOptions
    ) -> Measurement:
        self.max_width = options.max_width
        self.max_height = options.max_height

        viewport = self.viewport

        return Measurement(viewport.width, options.max_width)


def determine_lod(data: dict[str, Any], zoom: float = 1.0) -> int:
    lod_map = data.get("$lod-map", lambda _: 1)
    lod = lod_map(zoom)
    return lod
