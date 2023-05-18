from collections.abc import Hashable
from dataclasses import dataclass
from enum import Enum
from itertools import chain
from typing import Any, Generic, Protocol, cast

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
        layout_profiler: GraphProfiler | None = None,
        node_render_profiler: GraphProfiler | None = None,
        edge_render_profiler: GraphProfiler | None = None,
        buffer_render_profiler: GraphProfiler | None = None,
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
            layout_profiler (GraphProfiler, optional): Profiler that is executed during layout.
            node_render_profiler (GraphProfiler, optional): Profiler that is executed during node rendering.
            edge_render_profiler (GraphProfiler, optional): Profiler that is executed during edge rendering.
            buffer_render_profiler (GraphProfiler, optional): Profiler that is execuuted during buffer rendering.
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

        if node_render_profiler:
            node_render_profiler.start()

        self.node_buffers: dict[Hashable, NodeBuffer] = {
            node: rasterize_node(console, node, cast(dict[Hashable, Any], data))
            for node, data in self._nx_graph.nodes(data=True)
        }

        if node_render_profiler:
            node_render_profiler.stop()

        # Store the node buffers in the graph itself
        nx.set_node_attributes(self._nx_graph, self.node_buffers, "_netext_node_buffer")

        if layout_profiler:
            layout_profiler.start()

        # Position the nodes and add the position information to the graph
        self.node_positions: dict[Hashable, tuple[float, float]] = layout_engine(
            self._nx_graph
        )

        # Center node positions around the midpoint of all nodes
        min_x = min([x for _, (x, _) in self.node_positions.items()])
        max_x = max([x for _, (x, _) in self.node_positions.items()])
        min_y = min([y for _, (_, y) in self.node_positions.items()])
        max_y = max([y for _, (_, y) in self.node_positions.items()])

        self.node_positions = {
            node: (x - min_x - (max_x - min_x) / 2, y - min_y - (max_y - min_y) / 2)
            for node, (x, y) in self.node_positions.items()
        }

        if layout_profiler:
            layout_profiler.stop()

        self.edge_buffers: list[EdgeBuffer] = []
        self.edge_layouts: list[EdgeLayout] = []
        self.label_buffers: list[StripBuffer] = []

        self._buffer_render_profiler = buffer_render_profiler
        self._edge_render_profiler = edge_render_profiler

    def _project_positions(self, max_width: int, max_height: int) -> None:
        # Need to set this first, otherwise viewport is determined the wrong way
        max_buffer_width = max([buffer.width for buffer in self.node_buffers.values()])
        max_buffer_height = max(
            [buffer.height for buffer in self.node_buffers.values()]
        )
        for node, pos in self.node_positions.items():
            buffer: NodeBuffer = self._nx_graph.nodes[node]["_netext_node_buffer"]
            buffer.center = Point(x=round(pos[0]), y=round(pos[1]))

        vp = self._unconstrained_viewport()

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

    def _render_edges(self, console: Console) -> None:
        # Now we rasterize the edges
        if self._edge_render_profiler:
            self._edge_render_profiler.start()

        # Iterate over all edges (so far in no particular order)
        node_idx = index.Index()
        edge_idx = index.Index()

        for i, node in enumerate(self.node_buffers.values()):
            node_idx.insert(i, node.bounding_box)

        all_node_buffers = list(self.node_buffers.values())

        for u, v, data in self._nx_graph.edges(data=True):
            result = rasterize_edge(
                console,
                self.node_buffers[u],
                self.node_buffers[v],
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

        if self._edge_render_profiler:
            self._edge_render_profiler.stop()

    @property
    def all_buffers(self):
        # Get graph subview
        visible_nodes = nx.subgraph_view(
            self._nx_graph,
            filter_node=lambda n: self._nx_graph.nodes[n].get("$show", True),
        )
        node_buffers = nx.get_node_attributes(visible_nodes, "_netext_node_buffer")  # type: ignore
        return chain(node_buffers.values(), self.edge_buffers, self.label_buffers)

    def _unconstrained_viewport(self):
        return Region.union([buffer.region for buffer in self.all_buffers])

    def _viewport_with_constraints(self):
        if self._viewport is not None:
            return self._viewport
        return self._unconstrained_viewport()

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        self._project_positions(options.max_width, options.max_height)
        self._render_edges(console)
        yield from render_buffers(self.all_buffers, self._viewport_with_constraints())

    def _profile_render(self):
        if self._buffer_render_profiler:
            self._buffer_render_profiler.start()
        list(render_buffers(self.all_buffers, self.viewport))
        if self._buffer_render_profiler:
            self._buffer_render_profiler.stop()

    def __rich_measure__(
        self, console: Console, options: ConsoleOptions
    ) -> Measurement:
        print("measuring")
        return Measurement(self.width, self.width)
