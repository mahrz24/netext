from collections import defaultdict
from collections.abc import Hashable
from dataclasses import dataclass
from enum import Enum
from itertools import chain
from typing import Any, Generic, Iterable, Protocol, cast

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
from netext.node_rasterizer import NodeBuffer, lod_for_node, rasterize_node


class GraphProfiler(Protocol):
    def start(self) -> None:
        raise NotImplementedError()

    def stop(self) -> None:
        raise NotImplementedError()


class AutoZoom(Enum):
    FIT = "fit"
    FIT_PROPORTIONAL = "fit_proportional"


@dataclass
class ZoomSpec:
    x: float
    y: float


class TerminalGraph(Generic[G]):
    def __init__(
        self,
        g: G,
        # see https://github.com/python/mypy/issues/3737
        layout_engine: LayoutEngine[G] = GrandalfSugiyamaLayout[G](),  # type: ignore
        console: Console = Console(),
        viewport: Region | None = None,
        zoom: float | tuple[float, float] | ZoomSpec | AutoZoom = 1.0,
    ):
        """
        A terminal representation of a networkx graph.

        The class conforms to the rich console protocol and can be printed
        as any other rich renderable. You can pass a layout engine and a
        specific console that will be used for rendering.

        Rendering of nodes and edges happens on object creation and the
        object size is determined by the graph (no reactive rendering).

        Args:
            g (G): A networkx graph object (see [networkx.Graph][] or [networkx.DiGraph][]).
            layout_engine (LayoutEngine[G], optional): The layout engine used.
            console (Console, optional): The rich console driver used to render.
        """
        self._viewport = viewport

        if isinstance(zoom, float):
            zoom = ZoomSpec(zoom, zoom)
        elif isinstance(zoom, tuple):
            zoom = ZoomSpec(zoom[0], zoom[1])

        self._zoom = zoom
        self._nx_graph: G = cast(G, g.copy())
        # First we create the node buffers, this allows us to pass the sizing information to the
        # layout engine. For each node in the graph we generate a node buffer that contains the
        # segments to render the node and metadata where to place the buffer.

        self.node_buffers: dict[Hashable, NodeBuffer] = {
            node: rasterize_node(console, node, cast(dict[Hashable, Any], data))
            for node, data in self._nx_graph.nodes(data=True)
        }

        self.node_buffers_per_lod = defaultdict(dict, {1: self.node_buffers})

        # Store the node buffers in the graph itself
        nx.set_node_attributes(self._nx_graph, self.node_buffers, "_netext_node_buffer")

        # Position the nodes and store these original positions
        self.node_positions: dict[Hashable, tuple[float, float]] = layout_engine(
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

        self.edge_buffers: list[EdgeBuffer] = []
        self.edge_layouts: list[EdgeLayout] = []
        self.label_buffers: list[StripBuffer] = []

    def _project_positions(
        self, max_width: int, max_height: int
    ) -> tuple[float, float]:
        # Reset all node positions to the original, non zoomed position
        # from the layout engine
        for node, pos in self.node_positions.items():
            buffer: NodeBuffer = self._nx_graph.nodes[node]["_netext_node_buffer"]
            buffer.center = Point(x=round(pos[0]), y=round(pos[1]))

        # Get the unconstrined full viewport given the current positions
        vp = self._unconstrained_viewport()

        # Compute the zoom value for both axes
        max_buffer_width = max([buffer.width for buffer in self.node_buffers.values()])
        max_buffer_height = max(
            [buffer.height for buffer in self.node_buffers.values()]
        )

        # TODO Up until here everything could be precomputed
        match self._zoom:
            case AutoZoom.FIT:
                zoom_x = (max_width - max_buffer_width / 2 - 1) / vp.width
                zoom_y = (max_height - max_buffer_height / 2 - 1) / vp.height
            case AutoZoom.FIT_PROPORTIONAL:
                zoom_x = max_width / vp.width
                zoom_y = max_height / vp.height
                zoom_y = zoom_x = min(zoom_x, zoom_y)
            case ZoomSpec(x, y):
                zoom_x = x
                zoom_y = y
            case _:
                raise ValueError("Invalid zoom value")

        # Store the node positions in the node buffers
        for node, pos in self.node_positions.items():
            buffer: NodeBuffer = self._nx_graph.nodes[node]["_netext_node_buffer"]
            buffer.center = Point(x=round(zoom_x * pos[0]), y=round(zoom_y * pos[1]))

        return zoom_x, zoom_y

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
            u_lod = lod_for_node(self._nx_graph.nodes[u], zoom)
            v_lod = lod_for_node(self._nx_graph.nodes[v], zoom)

            result = rasterize_edge(
                console,
                self.node_buffers_per_lod[u_lod][u],
                self.node_buffers_per_lod[v_lod][v],
                all_node_buffers,
                self.edge_layouts,
                data,
                node_idx,
                edge_idx,
            )
            if result is not None:
                edge_buffer, edge_layout, label_nodes = result
                edge_idx.insert(len(self.edge_buffers), edge_buffer.bounding_box)

                self.edge_buffers.append(edge_buffer)
                self.edge_layouts.append(edge_layout)
                self.label_buffers.extend(label_nodes)

    def _all_buffers(
        self, console: Console | None = None, zoom: float = 1.0
    ) -> Iterable[NodeBuffer]:
        # Get graph subview
        visible_nodes = nx.subgraph_view(
            self._nx_graph,
            filter_node=lambda n: self._nx_graph.nodes[n].get("$show", True),
        )

        if zoom != 1.0:
            node_buffers = [
                node_buffer
                for node, node_buffer in self.render_lod_buffers(console, zoom).items()
                if node in visible_nodes
            ]
        else:
            node_buffers = nx.get_node_attributes(
                visible_nodes, "_netext_node_buffer"
            ).values()  # type: ignore

        return chain(node_buffers, self.edge_buffers, self.label_buffers)

    def render_lod_buffers(self, console: Console, zoom) -> dict[Hashable, NodeBuffer]:
        if console is None:
            raise RuntimeError(
                "Cannot generate ad-hoc zoomed node buffers without a console."
            )

        nodebuffers_at_current_lod = dict()

        for node, data in self._nx_graph.nodes(data=True):
            lod = lod_for_node(data, zoom)
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

    def _viewport_with_constraints(self) -> Region:
        if self._viewport is not None:
            return self._viewport
        return self._unconstrained_viewport()

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
