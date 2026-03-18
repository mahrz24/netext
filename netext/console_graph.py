from collections.abc import Hashable
from dataclasses import dataclass
from enum import Enum
from itertools import chain
import itertools
from typing import Any, Iterable, cast

from rich.console import Console, ConsoleOptions, RenderResult
from rich.measure import Measurement

from netext.geometry import Region

from netext.edge_rendering.buffer import EdgeBuffer
from netext.geometry.point import FloatPoint
from netext.properties.edge import EdgeProperties
from netext.properties.node import NodeProperties
import netext._core as core
from netext._core import Point

from netext.rendering.segment_buffer import StripBuffer

from netext.buffer_renderer import render_buffers
from netext.node_rasterizer import NodeBuffer, rasterize_node

from netext.graph_transitions import (
    render_node_buffers_for_layout,
    compute_node_layout,
    compute_zoom,
    render_node_buffers_at_zoom,
    render_all_edges,
    register_node_with_router,
)
from netext.graph_mutations import (
    compute_node_view_position,
    rasterize_node_for_layout,
    rasterize_node_at_lod,
    check_zoom_recomputation,
    rasterize_and_store_edge,
    remove_existing_edge_buffers,
    rerender_connected_edges,
)

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


_STATE_ORDER: list[RenderState] = [
    RenderState.INITIAL,
    RenderState.NODE_BUFFERS_RENDERED_FOR_LAYOUT,
    RenderState.NODE_LAYOUT_COMPUTED,
    RenderState.ZOOMED_POSITIONS_COMPUTED,
    RenderState.NODE_BUFFERS_RENDERED,
    RenderState.EDGES_RENDERED,
]

_TRANSITIONS: list[str] = [
    "render_node_buffers_for_layout",
    "compute_node_layout",
    "compute_zoomed_positions",
    "render_node_buffers",
    "render_edges",
]

_STATE_INDEX: dict[RenderState, int] = {s: i for i, s in enumerate(_STATE_ORDER)}


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


class ConsoleGraph:
    def __init__(
        self,
        nodes: dict[Hashable, dict[str, Any]] | None = None,
        edges: (
            Iterable[tuple[Hashable, Hashable]]
            | Iterable[tuple[Hashable, Hashable, dict[str, Any]]]
            | None
        ) = None,
        *,
        layout_engine: core.LayoutEngine = core.SugiyamaLayout(core.LayoutDirection.TOP_DOWN),
        console: Console = Console(),
        viewport: Region | None = None,
        max_width: int | None = None,
        max_height: int | None = None,
        zoom: float | tuple[float, float] | ZoomSpec | AutoZoom = 1.0,
    ):
        """
        A console representation of a graph.

        The class conforms to the rich console protocol and can be printed
        as any other rich renderable. You can pass a layout engine and a
        specific console that will be used for rendering.

        Rendering of nodes and edges happens on object creation and the
        object size is determined by the graph (no reactive rendering).

        Args:
            nodes: A dict mapping node ids to data dicts, e.g. ``{1: {"label": "A"}, 2: {}}``.
            edges: An iterable of 2-tuples ``(u, v)`` or 3-tuples ``(u, v, data_dict)``.
            layout_engine: The layout engine used.
            console: The rich console driver used to render.
            viewport: The viewport to render. Defaults to the whole graph.
            max_width: The maximum width of the graph in characters.
            max_height: The maximum height of the graph in characters.
            zoom: The zoom level, either a float, a tuple of zoom in x and y direction
                or a zoom spec / auto zoom mode. Defaults to 1.0.
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

        self._layout_engine = layout_engine
        self._edge_router = core.EdgeRouter()

        edge_list: list[tuple[Hashable, Hashable]] = []
        edge_data_list: list[tuple[Hashable, Hashable, dict[str, Any]]] = []

        if edges is not None:
            for item in list(edges):
                item_tuple = tuple(item) if not isinstance(item, tuple) else item
                if len(item_tuple) == 3:
                    edge_list.append((item_tuple[0], item_tuple[1]))
                    edge_data_list.append((item_tuple[0], item_tuple[1], item_tuple[2]))
                else:
                    edge_list.append((item_tuple[0], item_tuple[1]))
                    edge_data_list.append((item_tuple[0], item_tuple[1], {}))

        self._core_graph = core.CoreGraph.from_edges(edge_list)

        if nodes is not None:
            for node, data in nodes.items():
                if not self._core_graph.contains_node(node):
                    self._core_graph.add_node(node, data, core.Size(0, 0))
                else:
                    self._core_graph.update_node_data(node, data)

        for u, v, data in edge_data_list:
            self._core_graph.update_edge_data(u, v, data)

        self.node_buffers_for_layout: dict[Hashable, NodeBuffer] = dict()
        self.node_buffers: dict[Hashable, NodeBuffer] = dict()
        self.port_buffers: dict[Hashable, list[StripBuffer]] = dict()

        self.node_positions: dict[Hashable, FloatPoint] = dict()

        self.edge_buffers: dict[tuple[Hashable, Hashable], EdgeBuffer] = dict()
        self.edge_label_buffers: dict[tuple[Hashable, Hashable], list[StripBuffer]] = dict()

    @classmethod
    def from_networkx(cls, graph: "Any", **kwargs: Any) -> "ConsoleGraph":
        """Create a ConsoleGraph from a networkx DiGraph.

        Requires networkx to be installed (pip install netext[networkx]).

        Args:
            graph: A networkx DiGraph (or Graph) object.
            **kwargs: Additional keyword arguments passed to the ConsoleGraph constructor.

        Returns:
            A new ConsoleGraph instance.
        """
        nodes = dict(graph.nodes(data=True))
        edges = [(u, v, d) for u, v, d in graph.edges(data=True)]
        return cls(nodes=nodes, edges=edges, **kwargs)

    def _require(self, required_state: RenderState) -> None:
        if _STATE_INDEX[required_state] > _STATE_INDEX[self._render_state]:
            self._transition_to(required_state)

    def _transition_to(self, target_state: RenderState) -> None:
        current_idx = _STATE_INDEX[self._render_state]
        target_idx = _STATE_INDEX[target_state]
        for i in range(current_idx, target_idx):
            transition_func = getattr(self, f"_transition_{_TRANSITIONS[i]}")
            transition_func()
            self._render_state = _STATE_ORDER[i + 1]

    def _reset_render_state(self, new_state: RenderState) -> None:
        if _STATE_INDEX[self._render_state] > _STATE_INDEX[new_state]:
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
        """The maximum width of the graph in characters or None if no maximum width is set."""
        return self._max_width

    @max_width.setter
    def max_width(self, value: int | None) -> None:
        if self._max_width != value:
            self._max_width = value
            if self._zoom is AutoZoom.FIT or self._zoom is AutoZoom.FIT_PROPORTIONAL:
                self._reset_render_state(RenderState.NODE_LAYOUT_COMPUTED)

    @property
    def max_height(self) -> int | None:
        """The maximum height of the graph in characters as integer or None if no maximum height is set."""
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
        """The viewport that is set by the user (or the full viewport if none is set)."""
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

        properties = NodeProperties.from_data_dict(data)

        layout_buffer = rasterize_node_for_layout(
            self.console,
            node,
            data,
            self._layout_engine.layout_direction,
        )
        self.node_buffers_for_layout[node] = layout_buffer

        display_buffer = rasterize_node_at_lod(
            self.console,
            node,
            data,
            self._zoom_factor,
            layout_buffer.node_anchors,
        )
        display_buffer.determine_edge_positions()

        self._core_graph.add_node(
            node, dict(data, **{"$properties": properties}), core.Size(display_buffer.width, display_buffer.height)
        )

        self.node_buffers[node] = display_buffer

        if position is not None:
            node_position = cast(FloatPoint, position)
            node_position += self.offset
            self.node_positions[node] = node_position
            display_buffer.center = compute_node_view_position(node_position, self.zoom_x, self.zoom_y)

            needs_recompute, zoom_factor = check_zoom_recomputation(
                self._zoom,
                self._zoom_factor,
                self._compute_current_zoom,
            )
            if needs_recompute:
                self._zoom_factor = zoom_factor
                self._reset_render_state(RenderState.NODE_LAYOUT_COMPUTED)
                return

            self.node_buffers[node].center = compute_node_view_position(node_position, self.zoom_x, self.zoom_y)
            register_node_with_router(self._edge_router, node, self.node_buffers[node])
            self._render_port_buffer_for_node(node)
        else:
            self._reset_render_state(RenderState.NODE_BUFFERS_RENDERED_FOR_LAYOUT)

    def add_edge(self, u: Hashable, v: Hashable, data: dict[str, Any] | None = None) -> None:
        """Add an edge between existing nodes in the graph.

        Args:
            u (Hashable): The source node.
            v (Hashable): The target node.
            data (dict[str, Any] | None, optional): The data and attributes of the edge.

        Raises:
            ValueError: Raised if one of the edges does not exist in the graph.
        """

        self._require(RenderState.EDGES_RENDERED)

        assert self._zoom_factor is not None, (
            "You tried to add an edge without a computed zoom factor. This should never happen."
        )

        if not self._core_graph.contains_node(u):
            raise ValueError(f"Node {u} does not exist in graph")
        if not self._core_graph.contains_node(v):
            raise ValueError(f"Node {v} does not exist in graph")
        if self._core_graph.contains_edge(u, v):
            return

        if data is None:
            data = dict()

        properties = EdgeProperties.from_data_dict(data)
        self._core_graph.add_edge(u, v, dict(data, **{"$properties": properties}))

        rasterize_and_store_edge(
            self.console,
            self._edge_router,
            u,
            v,
            self.node_buffers,
            self.edge_buffers,
            self.edge_label_buffers,
            properties,
            self._zoom_factor,
            len(self.edge_buffers),
            self._layout_engine.layout_direction,
        )

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

        edges = list(self._core_graph.all_edges())
        for u, v in edges:
            if u == node or v == node:
                self.remove_edge(u, v)

        self.node_positions.pop(node)
        self.node_buffers_for_layout.pop(node)
        self.node_buffers.pop(node)

        self.port_buffers.pop(node, None)
        self._core_graph.remove_node(node)
        self._edge_router.remove_node(node)

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

        self._core_graph.remove_edge(u, v)
        self._edge_router.remove_edge(u, v)

        self.edge_buffers.pop((u, v))
        self.edge_label_buffers.pop((u, v))

        self._render_port_buffer_for_node(u)
        self._render_port_buffer_for_node(v)

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
        properties = NodeProperties.from_data_dict({})
        if data is not None:
            if update_data:
                new_data = dict(self._core_graph.node_data_or_default(node, dict()), **data)
            else:
                new_data = data

            if "$properties" in new_data:
                del new_data["$properties"]
            properties = NodeProperties.from_data_dict(new_data)
            new_data["$properties"] = properties

            self._core_graph.update_node_data(node, new_data)
            old_position = self.node_buffers[node].center

            layout_buffer = rasterize_node_for_layout(
                self.console,
                node,
                cast(dict[str, Any], new_data),
                self._layout_engine.layout_direction,
            )
            self.node_buffers_for_layout[node] = layout_buffer

            new_node_buffer = rasterize_node(
                self.console,
                node,
                new_data,
                node_anchors=layout_buffer.node_anchors,
            )

            new_node_buffer.center = old_position
            self.node_buffers[node] = new_node_buffer

            # TODO: Replace this by something possible without shapely
            force_edge_rerender = True

        node_data = cast(dict[Hashable, Any], self._core_graph.node_data_or_default(node, dict()))
        data = cast(dict[str, Any], node_data)

        properties = NodeProperties.from_data_dict(data)

        force_edge_rerender = force_edge_rerender or (position is not None) or "$ports" in data

        self._edge_router.remove_node(node)

        if position is None:
            node_position = self.node_positions[node]
        else:
            node_position = cast(FloatPoint, position)
            node_position += self.offset
            self.node_positions[node] = node_position
            self.node_buffers[node].center = compute_node_view_position(node_position, self.zoom_x, self.zoom_y)
            self.node_buffers[node].node_anchors.all_positions = dict()

            needs_recompute, zoom_factor = check_zoom_recomputation(
                self._zoom,
                self._zoom_factor,
                self._compute_current_zoom,
            )
            if needs_recompute:
                self._zoom_factor = zoom_factor
                self._reset_render_state(RenderState.NODE_LAYOUT_COMPUTED)
                return

        # TODO also ports could have changed with data update needs some proper treatment
        self.node_buffers[node].connected_ports = connected_ports

        self._render_port_buffer_for_node(node)

        self.node_buffers[node].center = compute_node_view_position(node_position, self.zoom_x, self.zoom_y)
        self._core_graph.update_node_data(node, dict(data, **{"$properties": properties}))

        register_node_with_router(self._edge_router, node, self.node_buffers[node])

        if force_edge_rerender:
            rerender_connected_edges(
                self.console,
                self._core_graph,
                self._edge_router,
                node,
                self.node_buffers,
                self.edge_buffers,
                self.edge_label_buffers,
                self._zoom_factor,
                self._layout_engine.layout_direction,
                self.port_buffers,
                self._render_port_buffer_for_node,
            )

    def to_graph_coordinates(self, p: Point) -> FloatPoint:
        """Converts a point from view coordinates to graph coordinates.

        This means applying the inverse zoom and offset to the point.

        Args:
            p (Point): The point to convert.

        Returns:
            FloatPoint: The converted point in graph coordinates.
        """
        return FloatPoint(p.x / self.zoom_x - self.offset.x, p.y / self.zoom_y - self.offset.y)

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
        if self._zoom_factor is None:
            raise RuntimeError("You can only update edges once the zoom factor has been computed")

        old_data = self._core_graph.edge_data(u, v)
        data = dict(old_data, **data) if update_data else data

        if "$properties" in data:
            del data["$properties"]

        properties = EdgeProperties.from_data_dict(data)
        self._core_graph.update_edge_data(u, v, dict(data, **{"$properties": properties}))

        old_z_index = remove_existing_edge_buffers(
            self._edge_router,
            u,
            v,
            self.node_buffers,
            self.edge_buffers,
            self.edge_label_buffers,
        )

        rasterize_and_store_edge(
            self.console,
            self._edge_router,
            u,
            v,
            self.node_buffers,
            self.edge_buffers,
            self.edge_label_buffers,
            properties,
            self._zoom_factor,
            old_z_index,
            self._layout_engine.layout_direction,
        )

        self._render_port_buffer_for_node(u)
        self._render_port_buffer_for_node(v)

    def layout(self) -> None:
        self._reset_render_state(RenderState.NODE_BUFFERS_RENDERED_FOR_LAYOUT)

    def _transition_render_node_buffers_for_layout(self) -> None:
        self.node_buffers_for_layout = render_node_buffers_for_layout(self.console, self._core_graph)

    def _transition_compute_node_layout(self) -> None:
        self.node_positions, self.offset = compute_node_layout(
            self._layout_engine, self._core_graph, self.node_buffers_for_layout
        )

    def _transition_compute_zoomed_positions(self) -> None:
        self._edge_router = core.EdgeRouter()
        zoom_x, zoom_y = self._compute_current_zoom()
        self.zoom_x = zoom_x
        self.zoom_y = zoom_y
        self._zoom_factor = min([zoom_x, zoom_y])

    def _compute_current_zoom(self) -> tuple[float, float]:
        return compute_zoom(
            self._zoom,
            self.node_positions,
            self.node_buffers_for_layout,
            self._max_width,
            self._max_height,
        )

    def _transition_render_node_buffers(self) -> None:
        if self._zoom_factor is None:
            raise RuntimeError("Invalid transition, lod buffers can only be rendered once zoom is computed.")

        self.node_buffers = render_node_buffers_at_zoom(
            self.console,
            self._core_graph,
            self.node_positions,
            self.node_buffers_for_layout,
            self.zoom_x,
            self.zoom_y,
            self._zoom_factor,
            self._edge_router,
        )

    def _transition_render_edges(self) -> None:
        if self._zoom_factor is None:
            raise RuntimeError("Invalid transition, lod buffers can only be rendered once zoom is computed.")

        self.edge_buffers, self.edge_label_buffers = render_all_edges(
            self.console,
            self._core_graph,
            self.node_buffers,
            self._edge_router,
            self._zoom_factor,
            self._layout_engine.layout_direction,
        )

        for node in self._core_graph.all_nodes():
            self._render_port_buffer_for_node(node)

    def _render_port_buffer_for_node(self, node):
        if self._zoom_factor is None:
            raise RuntimeError("Invalid transition, lod buffers can only be rendered once zoom is computed.")

        node_buffer = self.node_buffers[node]
        self.port_buffers[node] = node_buffer.get_port_buffers(
            self.console,
        )

    def _all_buffers(self) -> Iterable[StripBuffer]:
        self._require(RenderState.EDGES_RENDERED)
        # Get graph subview
        visible_nodes = [
            node
            for node in self._core_graph.all_nodes()
            if self._core_graph.node_data_or_default(node, dict()).get("$show", True)
        ]

        node_buffers = [node_buffer for node, node_buffer in self.node_buffers.items() if node in visible_nodes]

        port_buffers = [port_buffers for node, port_buffers in self.port_buffers.items() if node in visible_nodes]
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

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        self.max_width = options.max_width
        self.max_height = options.max_height

        self._require(RenderState.EDGES_RENDERED)

        strips, _ = render_buffers(
            self._all_buffers(),
            self.viewport,
        )

        yield from itertools.chain(*[strip + [""] for strip in strips])

    def __rich_measure__(self, console: Console, options: ConsoleOptions) -> Measurement:
        self.max_width = options.max_width
        self.max_height = options.max_height

        viewport = self.viewport

        return Measurement(viewport.width, options.max_width)
