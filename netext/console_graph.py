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

from textual import log


class RenderState(Enum):
    INITIAL = "initial"
    """The initial state, no rendering has happened yet."""

    NODE_BUFFERS_RENDERED_1_LOD = "node_buffers_rendered_1_lod"
    """The node buffers have been rendered for 1 lod."""

    NODE_LAYOUT_COMPUTED = "node_layout_computed"
    """The node layout has been computed."""

    ZOOMED_POSITIONS_COMPUTED = "zoomed_positions_computed"
    """The zoomed node positions have been computed."""

    EDGES_RENDERED_1_LOD = "edges_rendered_1_lod"
    """The edges have been rendered for 1 lod."""

    NODE_BUFFERS_RENDERED_CURRENT_LOD = "node_buffers_rendered_current_lod"
    """The node buffers have ben rendered for the current lod."""

    EDGES_RENDERED_CURRENT_LOD = "edges_rendered_current_lod"
    """The edges have ben rendered for the current lod."""


transition_graph = nx.DiGraph()

transition_graph.add_edge(
    RenderState.INITIAL,
    RenderState.NODE_BUFFERS_RENDERED_1_LOD,
    transition="render_node_buffers_1_lod",
)
transition_graph.add_edge(
    RenderState.NODE_BUFFERS_RENDERED_1_LOD,
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
    RenderState.EDGES_RENDERED_1_LOD,
    transition="render_edges_1_lod",
)
transition_graph.add_edge(
    RenderState.EDGES_RENDERED_1_LOD,
    RenderState.NODE_BUFFERS_RENDERED_CURRENT_LOD,
    transition="render_node_buffers_current_lod",
)
transition_graph.add_edge(
    RenderState.NODE_BUFFERS_RENDERED_CURRENT_LOD,
    RenderState.EDGES_RENDERED_CURRENT_LOD,
    transition="render_edges_current_lod",
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

        if isinstance(zoom, float):
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

        self.node_buffers: dict[Hashable, NodeBuffer] = dict()
        self.node_buffers_per_lod: dict[int, dict[Hashable, NodeBuffer]] = defaultdict(
            dict
        )
        self.node_buffers_current_lod: dict[Hashable, NodeBuffer] = dict()

        self.node_positions: dict[Hashable, tuple[float, float]] = dict()

        self.edge_buffers: dict[tuple[Hashable, Hashable], EdgeBuffer] = dict()
        self.edge_buffers_per_lod: dict[
            int, dict[tuple[Hashable, Hashable], EdgeBuffer]
        ] = defaultdict(dict)
        self.edge_buffers_current_lod: dict[
            tuple[Hashable, Hashable], EdgeBuffer
        ] = dict()

        self.edge_layouts: dict[tuple[Hashable, Hashable], EdgeLayout] = dict()
        self.edge_layouts_per_lod: dict[
            int, dict[tuple[Hashable, Hashable], EdgeLayout]
        ] = defaultdict(dict)
        self.edge_layouts_current_lod: dict[
            tuple[Hashable, Hashable], EdgeLayout
        ] = dict()

        self.label_buffers: dict[tuple[Hashable, Hashable], list[StripBuffer]] = dict()
        self.label_buffers_per_lod: dict[
            int, dict[tuple[Hashable, Hashable], list[StripBuffer]]
        ] = defaultdict(dict)
        self.label_buffers_current_lod: dict[
            tuple[Hashable, Hashable], list[StripBuffer]
        ] = dict()

        self.node_idx_1_lod = index.Index()
        self.edge_idx_1_lod = index.Index()

        self.node_idx_current_lod = index.Index()
        self.edge_idx_current_lod = index.Index()

    def _require(self, required_state: RenderState):
        if required_state in nx.descendants(transition_graph, self._render_state):
            self._transition_to(required_state)

    def _transition_to(self, target_state: RenderState):
        path = nx.shortest_path(transition_graph, self._render_state, target_state)
        for u, v in zip(path, path[1:]):
            el = transition_graph.edges[u, v]
            transition = el["transition"]
            transition_func = getattr(self, f"_transition_{transition}")
            log(f"Transitioning from {u} to {v} using {transition}")
            transition_func()
            log(f"Transitioned to {transition}")
            self._render_state = v

    def _reset_render_state(self, new_state: RenderState) -> None:
        if self._render_state in nx.descendants(transition_graph, new_state):
            self._render_state = new_state

    @property
    def zoom(self) -> float | tuple[float, float] | ZoomSpec | AutoZoom:
        return self._zoom

    @zoom.setter
    def zoom(self, value: float | tuple[float, float] | ZoomSpec | AutoZoom) -> None:
        if isinstance(value, float):
            value = ZoomSpec(value, value)
        elif isinstance(value, tuple):
            value = ZoomSpec(value[0], value[1])
        if self._zoom != value:
            self._zoom = value
            self._reset_render_state(RenderState.NODE_LAYOUT_COMPUTED)

    @property
    def max_width(self) -> int | None:
        return self._max_width

    @max_width.setter
    def max_width(self, value: int | None) -> None:
        if self._max_width != value:
            self._max_width = value
            if self._zoom is AutoZoom.FIT or self._zoom is AutoZoom.FIT_PROPORTIONAL:
                self._reset_render_state(RenderState.NODE_LAYOUT_COMPUTED)

    @property
    def max_height(self) -> int | None:
        return self._max_height

    @max_height.setter
    def max_height(self, value: int | None) -> None:
        if self._max_height != value:
            self._max_height = value
            if self._zoom is AutoZoom.FIT or self._zoom is AutoZoom.FIT_PROPORTIONAL:
                self._reset_render_state(RenderState.NODE_LAYOUT_COMPUTED)

    @property
    def full_viewport(self) -> Region:
        return self._unconstrained_viewport()

    @property
    def viewport(self) -> Region:
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
        position: Point | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        if data is None:
            data = dict()
        # TODO Graph should be rendered by here, also on all other remove/add methods
        self._nx_graph.add_node(node, **data)

        self.node_buffers[node] = rasterize_node(self.console, node, data)

        if position is not None:
            pos_x, pos_y = position.as_tuple()
            # We add a new node and first need to transform the point from the buffer space to the not zoomed
            # coordinate space of the nodes
            # TODO these should probably be points
            coords = (pos_x / self.zoom_x, pos_y / self.zoom_y)
            self.node_positions[node] = coords
            self.node_buffers[node].center = Point(round(coords[0]), round(coords[1]))

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
                log(
                    "RESETTING RENDER STATE AS ZOOM FACTOR CHANGED FROM"
                    f" {self._zoom_factor} to {zoom_factor}"
                )
                self._zoom_factor = zoom_factor
                self._reset_render_state(RenderState.NODE_LAYOUT_COMPUTED)
            else:
                lod = determine_lod(data, zoom_factor)
                position = Point(
                    x=round(coords[0] * self.zoom_x), y=round(coords[1] * self.zoom_y)
                )
                self._render_node_buffer_current_lod(node, data, lod, coords)
        else:
            self._reset_render_state(RenderState.NODE_BUFFERS_RENDERED_1_LOD)

    def add_edge(
        self, u: Hashable, v: Hashable, data: dict[str, Any] | None = None
    ) -> None:
        # TODO a lot of code duplication with the edge rendering
        edge_buffer: EdgeBuffer | None = None
        edge_layout: EdgeLayout | None = None
        label_nodes: list[StripBuffer] | None = None

        log("Adding edge", u, v, data)
        log(self.edge_buffers.keys())

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

        result = rasterize_edge(
            self.console,
            self.node_buffers[u],
            self.node_buffers[v],
            list(self.node_buffers.values()),
            list(self.edge_layouts.values()),
            data,
            self.node_idx_1_lod,
            self.edge_idx_1_lod,
            lod=1,
        )

        if result is not None:
            print("ADDING LOD 1")
            edge_buffer, edge_layout, label_nodes = result

            # This works because insertion order is sort order for dicts
            self.edge_idx_1_lod.insert(len(self.edge_buffers), edge_buffer.bounding_box)

            self.edge_buffers[(u, v)] = edge_buffer
            self.edge_layouts[(u, v)] = edge_layout
            self.label_buffers[(u, v)] = label_nodes

        u_lod = determine_lod(self._nx_graph.nodes[u], self._zoom_factor)
        v_lod = determine_lod(self._nx_graph.nodes[v], self._zoom_factor)

        edge_lod = determine_lod(data, self._zoom_factor)

        edge_buffer = self.edge_buffers_per_lod[edge_lod].get((u, v))
        edge_layout = self.edge_layouts_per_lod[edge_lod].get((u, v))
        label_nodes = self.label_buffers_per_lod[edge_lod].get((u, v))

        result = rasterize_edge(
            self.console,
            self.node_buffers_per_lod[u_lod][u],
            self.node_buffers_per_lod[v_lod][v],
            list(self.node_buffers_current_lod.values()),
            list(self.edge_layouts_current_lod.values()),
            data,
            self.node_idx_current_lod,
            self.edge_idx_current_lod,
            edge_lod,
        )

        if result is not None:
            edge_buffer, edge_layout, label_nodes = result
            self.edge_idx_current_lod.insert(
                len(self.edge_buffers_current_lod), edge_buffer.bounding_box
            )

            self.edge_buffers_per_lod[edge_lod][(u, v)] = edge_buffer
            self.edge_layouts_per_lod[edge_lod][(u, v)] = edge_layout
            self.label_buffers_per_lod[edge_lod][(u, v)] = label_nodes

        if edge_buffer is not None:
            self.edge_buffers_current_lod[(u, v)] = edge_buffer
        if label_nodes is not None:
            self.label_buffers_current_lod[(u, v)] = label_nodes
        if edge_layout is not None:
            self.edge_layouts_current_lod[(u, v)] = edge_layout

        log("EDGE ADDED")
        log(self._nx_graph.edges)
        log(self.edge_buffers.keys())
        log(self.edge_buffers_current_lod.keys())

    def remove_node(self, node: Hashable) -> None:
        self.node_positions.pop(node)
        self.node_buffers.pop(node)
        self.node_buffers_current_lod.pop(node)

        for lod in self.node_buffers_per_lod.keys():
            self.node_buffers_per_lod[lod].pop(node, None)

        # Rebuild indices
        # TODO: this is not very efficient
        self.node_idx_1_lod = index.Index()
        for i, (node, node_buffer) in enumerate(self.node_buffers.items()):
            self.node_idx_1_lod.insert(i, node_buffer.bounding_box)

        self.node_idx_current_lod = index.Index()
        for i, (node, node_buffer) in enumerate(self.node_buffers_current_lod.items()):
            self.node_idx_current_lod.insert(i, node_buffer.bounding_box)

        for u, v in self._nx_graph.edges():
            if u == node or v == node:
                self.remove_edge(u, v)

        self._nx_graph.remove_node(node)

    def remove_edge(self, u: Hashable, v: Hashable) -> None:
        log(self._nx_graph.edges)
        log(self.edge_buffers.keys())
        log(self.edge_buffers_current_lod.keys())

        self._nx_graph.remove_edge(u, v)
        self.edge_buffers.pop((u, v))
        self.edge_buffers_current_lod.pop((u, v))

        for lod in self.edge_buffers_per_lod.keys():
            self.edge_buffers_per_lod[lod].pop((u, v), None)

        # Rebuild indices
        # TODO: this is not very efficient
        self.edge_idx_1_lod = index.Index()
        for i, (edge, edge_buffer) in enumerate(self.edge_buffers.items()):
            self.edge_idx_1_lod.insert(i, edge_buffer.bounding_box)

        self.edge_idx_current_lod = index.Index()
        for i, (edge, edge_buffer) in enumerate(self.edge_buffers_current_lod.items()):
            self.edge_idx_current_lod.insert(i, edge_buffer.bounding_box)

    def update_node(
        self,
        node: Hashable,
        position: Point | None = None,
        data: dict[str, Any] | None = None,
        update_data: bool = True,
    ) -> None:
        if data is None and position is None:
            return

        if data is not None:
            # Replace the data of the node with the new data
            if update_data:
                new_data = dict(self._nx_graph.nodes[node], **data)
            else:
                new_data = data
            log("Updating node data", node=node, data=new_data)
            self._nx_graph.nodes[node].update(new_data)
            old_position = self.node_buffers[node].center
            self.node_buffers[node] = rasterize_node(self.console, node, new_data)
            self.node_buffers[node].center = old_position

        data = cast(dict[str, Any], self._nx_graph.nodes(data=True)[node])

        if position is None:
            coords = self.node_positions[node]
            zoom_factor = self._zoom_factor if self._zoom_factor is not None else 0
        else:
            # TODO same as in add_node
            pos_x, pos_y = position.as_tuple()
            # We add a new node and first need to transform the point from the buffer space to the not zoomed
            # coordinate space of the nodes
            # TODO these should probably be points
            coords = (pos_x / self.zoom_x, pos_y / self.zoom_y)
            self.node_positions[node] = coords
            self.node_buffers[node].center = Point(round(coords[0]), round(coords[1]))

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
                log(
                    "RESETTING RENDER STATE AS ZOOM FACTOR CHANGED FROM"
                    f" {self._zoom_factor} to {zoom_factor}"
                )
                self._zoom_factor = zoom_factor
                self._reset_render_state(RenderState.NODE_LAYOUT_COMPUTED)
                return

        lod = determine_lod(data, zoom_factor)
        position = Point(
            x=round(coords[0] * self.zoom_x), y=round(coords[1] * self.zoom_y)
        )
        self._render_node_buffer_current_lod(node, data, lod, coords)

        # Rebuild indices
        # TODO: this is not very efficient
        self.node_idx_1_lod = index.Index()
        for i, (node, node_buffer) in enumerate(self.node_buffers.items()):
            self.node_idx_1_lod.insert(i, node_buffer.bounding_box)

        self.node_idx_current_lod = index.Index()
        for i, (node, node_buffer) in enumerate(self.node_buffers_current_lod.items()):
            self.node_idx_current_lod.insert(i, node_buffer.bounding_box)

        # TODO Update affected edges

    def update_edge(
        self, u: Hashable, v: Hashable, data: dict[str, Any], update_data: bool = True
    ) -> None:
        # Needs also a mode to keep the layout but rerender
        # For now we remove the edge and re-add it
        # TODO: This is not efficient and does indeed rebuild the indices twice
        old_data = self._nx_graph.edges[u, v]
        self.remove_edge(u, v)
        data = dict(old_data, **data) if update_data else data
        self.add_edge(u, v, data)

    def layout(self) -> None:
        self._reset_render_state(RenderState.NODE_BUFFERS_RENDERED_1_LOD)

    def _transition_render_node_buffers_1_lod(self) -> None:
        # First we create the node buffers, this allows us to pass the sizing information to the
        # layout engine. For each node in the graph we generate a node buffer that contains the
        # segments to render the node and metadata where to place the buffer.
        self.node_buffers = {
            node: rasterize_node(self.console, node, cast(dict[str, Any], data))
            for node, data in self._nx_graph.nodes(data=True)
        }
        self.node_buffers_per_lod[1] = self.node_buffers

    def _transition_compute_node_layout(self) -> None:
        # Store the node buffers in the graph itself
        nx.set_node_attributes(self._nx_graph, self.node_buffers, "_netext_node_buffer")

        # Position the nodes and store these original positions
        self.node_positions = self.layout_engine(self._nx_graph)

        if self.node_positions:
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

        for node, position in self.node_positions.items():
            self.node_buffers[node].center = Point(
                x=round(position[0]), y=round(position[1])
            )

    def _transition_compute_zoomed_positions(self) -> None:
        zoom_x, zoom_y = self._compute_current_zoom()
        self.zoom_x = zoom_x
        self.zoom_y = zoom_y
        self._zoom_factor = min([zoom_x, zoom_y])

    def _compute_current_zoom(self):
        if self.node_positions:
            max_node_x = max([x for x, _ in self.node_positions.values()])
            max_node_y = max([y for _, y in self.node_positions.values()])
            min_node_x = min([x for x, _ in self.node_positions.values()])
            min_node_y = min([y for _, y in self.node_positions.values()])

            # Compute the zoom value for both axes
            max_buffer_width = max(
                [buffer.width for buffer in self.node_buffers.values()]
            )
            max_buffer_height = max(
                [buffer.height for buffer in self.node_buffers.values()]
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
                    raise ValueError("Invalid zoom value")
        else:
            zoom_x = 1
            zoom_y = 1
        return zoom_x, zoom_y

    def _transition_render_edges_1_lod(self) -> None:
        if self._zoom_factor is None:
            raise RuntimeError(
                "Invalid transition, edges can only be rendered once zoom is computed."
            )

        self.edge_buffers = dict()
        self.label_buffers = dict()
        self.edge_layouts = dict()

        self.edge_buffers_per_lod = dict()
        self.edge_buffers_current_lod = dict()

        self.label_buffers_per_lod = dict()
        self.label_buffers_current_lod = dict()

        self.edge_layouts_per_lod = dict()
        self.edge_layouts_current_lod = dict()

        # Iterate over all edges (so far in no particular order)
        self.node_idx_1_lod = index.Index()
        self.edge_idx_1_lod = index.Index()

        # Make sure we use the lod 1 positions:
        for node, node_buffer in self.node_buffers.items():
            node_buffer.center = Point(
                x=round(self.node_positions[node][0]),
                y=round(self.node_positions[node][0]),
            )

        all_node_buffers = []
        for i, (node, node_buffer) in enumerate(self.node_buffers.items()):
            self.node_idx_1_lod.insert(i, node_buffer.bounding_box)
            all_node_buffers.append(node_buffer)

        for u, v, data in self._nx_graph.edges(data=True):
            result = rasterize_edge(
                self.console,
                self.node_buffers[u],
                self.node_buffers[v],
                all_node_buffers,
                list(self.edge_layouts.values()),
                data,
                self.node_idx_1_lod,
                self.edge_idx_1_lod,
                lod=1,
            )
            if result is not None:
                edge_buffer, edge_layout, label_nodes = result
                self.edge_idx_1_lod.insert(
                    len(self.edge_buffers), edge_buffer.bounding_box
                )

                self.edge_buffers[(u, v)] = edge_buffer
                self.edge_layouts[(u, v)] = edge_layout
                self.label_buffers[(u, v)] = label_nodes

        self.edge_buffers_per_lod[1] = self.edge_buffers
        self.edge_layouts_per_lod[1] = self.edge_layouts
        self.label_buffers_per_lod[1] = self.label_buffers

    def _transition_render_node_buffers_current_lod(self) -> None:
        if self._zoom_factor is None:
            raise RuntimeError(
                "Invalid transition, lod buffers can only be rendered once zoom is"
                " computed."
            )

        for node, data in self._nx_graph.nodes(data=True):
            lod = determine_lod(data, self._zoom_factor)
            # Get the zoomed position of the node
            coords = self.node_positions[node]
            self._render_node_buffer_current_lod(node, data, lod, coords)

    def _render_node_buffer_current_lod(
        self,
        node: Hashable,
        data: dict[str, Any],
        lod: int,
        coords: tuple[float, float],
    ):
        position = Point(
            x=round(coords[0] * self.zoom_x), y=round(coords[1] * self.zoom_y)
        )
        node_buffer = self.node_buffers_per_lod.get(lod, dict()).get(node)
        if node_buffer is None:
            node_buffer = rasterize_node(self.console, node, data, lod=lod)
            self.node_buffers_per_lod[lod][node] = node_buffer
        if node_buffer.center != position:
            node_buffer.center = position
            for v in nx.all_neighbors(self._nx_graph, node):
                # TODO This really needs to be rerendered if we pop things
                self.edge_buffers_per_lod[lod].pop((node, v), None)
                self.edge_buffers_per_lod[lod].pop((v, node), None)
                self.label_buffers_per_lod[lod].pop((node, v), None)
                self.label_buffers_per_lod[lod].pop((v, node), None)

                self.edge_buffers_current_lod.pop((node, v), None)
                self.edge_buffers_current_lod.pop((v, node), None)
                self.label_buffers_current_lod.pop((node, v), None)
                self.label_buffers_current_lod.pop((v, node), None)

        self.node_buffers_current_lod[node] = node_buffer

    def _transition_render_edges_current_lod(self) -> None:
        if self._zoom_factor is None:
            raise RuntimeError(
                "Invalid transition, lod buffers can only be rendered once zoom is"
                " computed."
            )

        # Now we rasterize the edges

        # Iterate over all edges (so far in no particular order)
        self.node_idx_current_lod = index.Index()
        self.edge_idx_current_lod = index.Index()

        edge_layouts: list[EdgeLayout] = []

        all_node_buffers = []
        for i, (node, node_buffer) in enumerate(self.node_buffers_current_lod.items()):
            self.node_idx_current_lod.insert(i, node_buffer.bounding_box)
            all_node_buffers.append(node_buffer)

        for u, v, data in self._nx_graph.edges(data=True):
            u_lod = determine_lod(self._nx_graph.nodes[u], self._zoom_factor)
            v_lod = determine_lod(self._nx_graph.nodes[v], self._zoom_factor)

            edge_lod = determine_lod(data, self._zoom_factor)
            edge_buffer = self.edge_buffers_per_lod[edge_lod].get((u, v))
            edge_layout = self.edge_layouts_per_lod[edge_lod].get((u, v))
            label_nodes = self.label_buffers_per_lod[edge_lod].get((u, v))

            if edge_buffer is None or label_nodes is None or edge_layout is None:
                result = rasterize_edge(
                    self.console,
                    self.node_buffers_per_lod[u_lod][u],
                    self.node_buffers_per_lod[v_lod][v],
                    all_node_buffers,
                    edge_layouts,
                    data,
                    self.node_idx_current_lod,
                    self.edge_idx_current_lod,
                    edge_lod,
                )
                if result is not None:
                    edge_buffer, edge_layout, label_nodes = result
                    self.edge_idx_current_lod.insert(
                        len(self.edge_buffers_current_lod), edge_buffer.bounding_box
                    )

                    self.edge_buffers_per_lod[edge_lod][(u, v)] = edge_buffer
                    self.edge_layouts_per_lod[edge_lod][(u, v)] = edge_layout
                    self.label_buffers_per_lod[edge_lod][(u, v)] = label_nodes

            if edge_buffer is not None:
                self.edge_buffers_current_lod[(u, v)] = edge_buffer
            if label_nodes is not None:
                self.label_buffers_current_lod[(u, v)] = label_nodes
            if edge_layout is not None:
                edge_layouts.append(edge_layout)
                self.edge_layouts_current_lod[(u, v)] = edge_layout

    def _unconstrained_lod_1_viewport(self) -> Region:
        return Region.union([buffer.region for buffer in self._all_lod_1_buffers()])

    def _all_lod_1_buffers(self) -> Iterable[StripBuffer]:
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
        return chain(
            node_buffers,
            self.edge_buffers.values(),
            itertools.chain(*self.label_buffers.values()),
        )

    def _all_current_lod_buffers(self) -> Iterable[StripBuffer]:
        self._require(RenderState.EDGES_RENDERED_CURRENT_LOD)
        # Get graph subview
        visible_nodes = nx.subgraph_view(
            self._nx_graph,
            filter_node=lambda n: self._nx_graph.nodes[n].get("$show", True),
        )

        node_buffers = [
            node_buffer
            for node, node_buffer in self.node_buffers_current_lod.items()
            if node in visible_nodes
        ]
        return chain(
            node_buffers,
            self.edge_buffers_current_lod.values(),
            itertools.chain(*self.label_buffers_current_lod.values()),
        )

    def _unconstrained_viewport(self) -> Region:
        regions = [buffer.region for buffer in self._all_current_lod_buffers()]

        if not regions:
            return Region(0, 0, 0, 0)

        return Region.union(regions)

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        self.max_width = options.max_width
        self.max_height = options.max_height

        self._require(RenderState.EDGES_RENDERED_CURRENT_LOD)

        strips, _ = render_buffers(
            self._all_current_lod_buffers(),
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
