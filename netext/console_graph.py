from collections import defaultdict
from collections.abc import Hashable
from dataclasses import dataclass
from enum import Enum
from itertools import chain
from typing import Any, Generic, Iterable, cast

import networkx as nx
from rich.console import Console, ConsoleOptions, RenderResult
from rich.measure import Measurement

from rtree import index

from netext.geometry import Point, Region

from netext.edge_rendering.buffer import EdgeBuffer
from netext.edge_routing.edge import EdgeLayout

from netext.rendering.segment_buffer import StripBuffer

from netext.buffer_renderer import render_buffers
from netext.edge_rasterizer import rasterize_edge
from netext.layout_engines.engine import LayoutEngine, G
from netext.layout_engines.grandalf import GrandalfSugiyamaLayout
from netext.node_rasterizer import NodeBuffer, rasterize_node


class RenderState(Enum):
    INITIAL = "initial"
    """The initial state, no rendering has happened yet."""

    NODE_BUFFERS_RENDERED_1_LOD = "node_buffers_rendered_1_lod"
    """The node buffers have been rendered for 1 lod."""

    NODE_LAYOUT_COMPUTED = "node_layout_computed"
    """The node layout has been computed."""

    EDGES_RENDERED_1_LOD = "edges_rendered_1_lod"
    """The edges have been rendered for 1 lod."""

    ZOOMED_POSITIONS_COMPUTED = "zoomed_positions_computed"
    """The zoomed node positions have been computed."""

    NODE_BUFFERS_RENDERED_CURRENT_LOD = "node_buffers_rendered_current_lod"
    """The node buffers have ben rendered for the current lod."""

    EDGES_RENDERED_CURRENT_LOD = "edges_rendered_current_lod"
    """The edges have ben rendered for the current lod."""

transition_graph = nx.DiGraph()

transition_graph.add_edge(RenderState.INITIAL, RenderState.NODE_BUFFERS_RENDERED_1_LOD, transition="render_node_buffers_1_lod")
transition_graph.add_edge(RenderState.NODE_BUFFERS_RENDERED_1_LOD, RenderState.NODE_LAYOUT_COMPUTED, transition="compute_node_layout")
transition_graph.add_edge(RenderState.NODE_LAYOUT_COMPUTED, RenderState.EDGES_RENDERED_1_LOD, transition="render_edges_1_lod")
transition_graph.add_edge(RenderState.EDGES_RENDERED_1_LOD, RenderState.ZOOMED_POSITIONS_COMPUTED, transition="compute_zoomed_positions")
transition_graph.add_edge(RenderState.ZOOMED_POSITIONS_COMPUTED, RenderState.NODE_BUFFERS_RENDERED_CURRENT_LOD, transition="render_node_buffers_current_lod")
transition_graph.add_edge(RenderState.NODE_BUFFERS_RENDERED_CURRENT_LOD, RenderState.EDGES_RENDERED_CURRENT_LOD, transition="render_edges_current_lod")


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

        if isinstance(zoom, float):
            zoom = ZoomSpec(zoom, zoom)
        elif isinstance(zoom, tuple):
            zoom = ZoomSpec(zoom[0], zoom[1])

        self.console = console
        self.zoom = zoom

        self.max_width = max_width
        self.max_height = max_height

        self.layout_engine = layout_engine
        self._nx_graph: G = cast(G, graph.copy())

        self.node_buffers: dict[Hashable, NodeBuffer] = dict()
        self.node_buffers_per_lod = defaultdict(dict)
        self.node_buffers_current_lod: dict[Hashable, NodeBuffer] = dict()


        self.node_positions: dict[Hashable, tuple[float, float]] = dict()

        self.edge_buffers: list[EdgeBuffer] = []
        self.edge_buffers_per_lod: dict[int, list[EdgeBuffer]] = defaultdict(list)
        self.edge_buffers_current_lod: list[EdgeBuffer] = []


        self.edge_layouts: list[EdgeLayout] = []
        self.edge_layouts_per_lod: dict[int, list[EdgeLayout]] = defaultdict(list)
        self.edge_layouts_current_lod: list[EdgeLayout] = []

        self.label_buffers: list[StripBuffer] = []
        self.label_buffers_per_lod: dict[int, list[StripBuffer]] = defaultdict(list)
        self.label_buffers_current_lod: list[StripBuffer] = []


    def _require(self, required_state: RenderState):
        if required_state in nx.descendants(transition_graph, self._render_state):
            self._transition_to(required_state)

    def _transition_to(self, target_state: RenderState):
        path = nx.shortest_path(transition_graph, self._render_state, target_state)
        for el in path:
            transition = el["transition"]
            transition_func = getattr(self, f"_transition_{transition}")
            transition_func()

    def _transition_render_node_buffers_1_lod(self):
        # First we create the node buffers, this allows us to pass the sizing information to the
        # layout engine. For each node in the graph we generate a node buffer that contains the
        # segments to render the node and metadata where to place the buffer.

        self.node_buffers: dict[Hashable, NodeBuffer] = {
            node: rasterize_node(self.console, node, cast(dict[Hashable, Any], data))
            for node, data in self._nx_graph.nodes(data=True)
        }
        self.node_buffers_per_lod[1] = self.node_buffers

    def _transition_compute_node_layout(self):
        # Position the nodes and store these original positions
        self.node_positions: dict[Hashable, tuple[float, float]] = self.layout_engine(
            self._nx_graph
        )

        x_positions = [x for _, (x, _) in self.node_positions.items()]
        y_positions = [y for _, (_, y) in self.node_positions.items()]
        # Center node positions around the midpoint of all nodes
        min_x = min(x_positions)
        max_x = max(x_positions)
        min_y = min(y_positions)
        max_y = max(y_positions)

        self.node_positions = {
            node: (x - min_x - (max_x - min_x) / 2, y - min_y - (max_y - min_y) / 2)
            for node, (x, y) in self.node_positions.items()
        }



    def _transition_render_edges_1_lod(self):
        # Iterate over all edges (so far in no particular order)
        node_idx = index.Index()
        edge_idx = index.Index()

        # Make sure we use the lod 1 positions:
        for node, node_buffer in self.node_buffers.items():
            node_buffer.center = Point(*map(round, self.node_positions[node]))

        all_node_buffers = []
        for i, (node, node_buffer) in enumerate(self.node_buffers.items()):
            node_idx.insert(i, node_buffer.bounding_box)
            all_node_buffers.append(node_buffer)

        for u, v, data in self._nx_graph.edges(data=True):
            result = rasterize_edge(
                self.console,
                self.node_buffers[u],
                self.node_buffers[v],
                all_node_buffers,
                self.edge_layouts,
                data,
                node_idx,
                edge_idx,
                lod=1,
            )
            if result is not None:
                edge_buffer, edge_layout, label_nodes = result
                edge_idx.insert(len(self.edge_buffers), edge_buffer.bounding_box)

                self.edge_buffers.append(edge_buffer)
                self.edge_layouts.append(edge_layout)
                self.label_buffers.extend(label_nodes)

        self.edge_buffers_per_lod[1] = self.edge_buffers
        self.edge_layouts_per_lod[1] = self.edge_layouts
        self.label_buffers_per_lod[1] = self.label_buffers

    def _transition_compute_zoomed_positions(self):
        viewport = self._unconstrained_lod_1_viewport()

        # Compute the zoom value for both axes
        max_buffer_width = max([buffer.width for buffer in self.node_buffers.values()])
        max_buffer_height = max(
            [buffer.height for buffer in self.node_buffers.values()]
        )

        match self.zoom:
            case AutoZoom.FIT:
                if self.max_width is None or self.max_height is None:
                    raise ValueError("AutoZoom.FIT is onlye allowed if the maximum renderable width and height is known.")
                zoom_x = (self.max_width - max_buffer_width / 2 - 1) / viewport.width
                zoom_y = (self.max_height - max_buffer_height / 2 - 1) / viewport.height
            case AutoZoom.FIT_PROPORTIONAL:
                if self.max_width is None or self.max_height is None:
                    raise ValueError("AutoZoom.FIT is onlye allowed if the maximum renderable width and height is known.")
                zoom_x = self.max_width / viewport.width
                zoom_y = self.max_height / viewport.height
                zoom_y = zoom_x = min(zoom_x, zoom_y)
            case ZoomSpec(x, y):
                zoom_x = x
                zoom_y = y
            case _:
                raise ValueError("Invalid zoom value")

        self.zoom_x = zoom_x
        self.zoom_y = zoom_y

    def _unconstrained_lod_1_viewport(self) -> Region:
        return Region.union([buffer.region for buffer in self._all_lod_1_buffers()])

    def _all_lod_1_buffers(
        self
    ) -> Iterable[StripBuffer]:
        # Get graph subview
        visible_nodes = nx.subgraph_view(
            self._nx_graph,
            filter_node=lambda n: self._nx_graph.nodes[n].get("$show", True),
        )

        node_buffers = [node_buffer for node, node_buffer in self.node_buffers.items() if node in visible_nodes]
        return chain(node_buffers, self.edge_buffers, self.label_buffers)



    def _render_edges(self, console: Console, zoom: float = 1.0) -> None:
        # Now we rasterize the edges

        # Iterate over all edges (so far in no particular order)
        node_idx = index.Index()
        edge_idx = index.Index()

        current_lod_node_buffers = self.render_lod_buffers(console, zoom)

        all_node_buffers = []
        for i, (node, node_buffer) in enumerate(current_lod_node_buffers.items()):
            node_idx.insert(i, node_buffer.bounding_box)
            all_node_buffers.append(node_buffer)

        for u, v, data in self._nx_graph.edges(data=True):
            u_lod = determine_lod(self._nx_graph.nodes[u], zoom)
            v_lod = determine_lod(self._nx_graph.nodes[v], zoom)

            edge_lod = determine_lod(data, zoom)

            result = rasterize_edge(
                console,
                self.node_buffers_per_lod[u_lod][u],
                self.node_buffers_per_lod[v_lod][v],
                all_node_buffers,
                self.edge_layouts,
                data,
                node_idx,
                edge_idx,
                edge_lod,
            )
            if result is not None:
                edge_buffer, edge_layout, label_nodes = result
                edge_idx.insert(len(self.edge_buffers), edge_buffer.bounding_box)

                self.edge_buffers.append(edge_buffer)
                self.edge_layouts.append(edge_layout)
                self.label_buffers.extend(label_nodes)


    def render_lod_buffers(self, console: Console, zoom) -> dict[Hashable, NodeBuffer]:
        nodebuffers_at_current_lod = dict()

        for node, data in self._nx_graph.nodes(data=True):
            lod = determine_lod(data, zoom)
            # Get the zoomed position of the node
            position = self.node_buffers[node].center
            node_buffer = self.node_buffers_per_lod.get(lod, dict()).get(node)
            if node_buffer is None:
                node_buffer = rasterize_node(
                    console, node, cast(dict[Hashable, Any], data), lod=lod
                )
                node_buffer.center = position
                self.node_buffers_per_lod[lod][node] = node_buffer
            nodebuffers_at_current_lod[node] = node_buffer

        return nodebuffers_at_current_lod

    def _unconstrained_viewport(self) -> Region:
        return Region.union([buffer.region for buffer in self._all_buffers()])

    @property
    def full_viewport(self) -> Region:
        """The full viewport of the graph, including all nodes and edges."""
        # TODO: This is not computed correctly as edges are only computed at render time
        # we need to precompute the edges and then we can use the unconstrained viewport
        # but for that we need a console, and that is not necessarily available at that
        # point. So we need to refactor this a bit.
        #
        # My current idea is to pass the console already to the constructor and then
        # check at render time if the console is still the same / compatible.
        return self._unconstrained_viewport()

    def _viewport_with_constraints(self) -> Region:
        if self._viewport is not None:
            return self._viewport
        return self._unconstrained_viewport()

    @property
    def viewport(self) -> Region:
        return self._viewport_with_constraints()

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        zoom_x, zoom_y = self._project_positions(options.max_width, options.max_height)
        zoom = min([zoom_x, zoom_y])

        # TODO this needs to be called before render edges and this coupling is quite implicit
        # Also project positions is not idempotent, which it should be
        all_buffers = self._all_buffers(console=console, zoom=zoom)

        self._render_edges(console, zoom=zoom)
        yield from render_buffers(
            all_buffers,
            self._viewport_with_constraints(),
        )

    def __rich_measure__(
        self, console: Console, options: ConsoleOptions
    ) -> Measurement:
        # Once done, we
        self._project_positions(options.max_width, options.max_height)

        viewport = self._viewport_with_constraints()

        return Measurement(viewport.width, options.max_width)


def determine_lod(data: dict[Hashable, Any], zoom: float = 1.0) -> int:
    lod_map = data.get("$lod-map", lambda _: 1)
    lod = lod_map(zoom)
    return lod
