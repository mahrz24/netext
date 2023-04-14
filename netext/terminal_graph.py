from collections.abc import Hashable
from itertools import chain
from math import ceil
from typing import Any, Generic, Protocol, cast

import networkx as nx
from rich.console import Console, ConsoleOptions, RenderResult
from rich.measure import Measurement

from netext.geometry.point import Point

from .edge_rendering.buffer import EdgeBuffer
from .edge_routing.edge import EdgeLayout

from netext.rendering.segment_buffer import StripBuffer

from .buffer_renderer import render_buffers
from .edge_rasterizer import rasterize_edge
from .layout_engines.engine import LayoutEngine, G
from .layout_engines.grandalf import GrandalfSugiyamaLayout
from .node_rasterizer import NodeBuffer, rasterize_node


class GraphProfiler(Protocol):
    def start(self) -> None:
        return NotImplemented

    def stop(self) -> None:
        return NotImplemented


class TerminalGraph(Generic[G]):
    def __init__(
        self,
        g: G,
        # see https://github.com/python/mypy/issues/3737
        layout_engine: LayoutEngine[G] = GrandalfSugiyamaLayout[G](),  # type: ignore
        console: Console = Console(),
        layout_profiler: GraphProfiler | None = None,
        node_render_profiler: GraphProfiler | None = None,
        edge_render_profiler: GraphProfiler | None = None,
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
        self._nx_graph: G = cast(G, g.copy())
        # First we create the node buffers, this allows us to pass the sizing information to the
        # layout engine. For each node in the graph we generate a node buffer that contains the
        # segments to render the node and metadata where to place the buffer.

        if node_render_profiler:
            node_render_profiler.start()

        node_buffers: dict[Hashable, NodeBuffer] = {
            node: rasterize_node(console, node, cast(dict[Hashable, Any], data))
            for node, data in self._nx_graph.nodes(data=True)
        }

        if node_render_profiler:
            node_render_profiler.stop()

        # Store the node buffers in the graph itself
        nx.set_node_attributes(self._nx_graph, node_buffers, "_netext_node_buffer")

        if layout_profiler:
            layout_profiler.start()
        # Position the nodes and add the position information to the graph
        node_positions: dict[Hashable, tuple[float, float]] = layout_engine(
            self._nx_graph
        )
        self.node_layout = node_positions
        if layout_profiler:
            layout_profiler.stop()

        # From the node buffer sizing and the layout, determine the total size needed for the graph.
        # TODO: We could add explicit sizing, also it is possible to recompute the edge buffer adaptively.
        # TODO: Check if this should be part of the engine if we have a native integer coordinate layout engine)

        # The offset needs should be the most upper left point including the size of the node buffer
        node_positions = self._transform_node_positions_to_console(node_positions)
        self._set_size_from_node_positions(node_positions)

        # Store the node positions in the node buffers
        for node, pos in node_positions.items():
            buffer: NodeBuffer = self._nx_graph.nodes[node]["_netext_node_buffer"]
            buffer.center = Point(x=round(pos[0]), y=round(pos[1]))

        # Now we rasterize the edges
        self.edge_buffers: list[EdgeBuffer] = []
        self.edge_layouts: list[EdgeLayout] = []
        self.label_buffers: list[StripBuffer] = []

        if edge_render_profiler:
            edge_render_profiler.start()

        # Iterate over all edges (so far in no particular order)
        for u, v, data in self._nx_graph.edges(data=True):
            result = rasterize_edge(
                console,
                node_buffers[u],
                node_buffers[v],
                node_buffers.values(),
                self.edge_layouts,
                data,
            )
            if result is not None:
                edge_buffer, edge_layout, label_nodes = result

                self.edge_buffers.append(edge_buffer)
                self.edge_layouts.append(edge_layout)
                self.label_buffers.extend(label_nodes)

        if edge_render_profiler:
            edge_render_profiler.stop()

    def _transform_node_positions_to_console(
        self, node_positions: dict[Hashable, tuple[float, float]]
    ) -> dict[Hashable, tuple[float, float]]:
        """Transforms the node positions into console coordinate space.

        Right now this assumes sizing from the layout engine is correct and only
        performs rounding and transpositions.
        """

        # TODO: Division by 2 can lead to some rounding errors, check this is still what we want
        x_offset = -min(
            [
                x - self._nx_graph.nodes[node]["_netext_node_buffer"].width / 2
                for node, (x, _) in node_positions.items()
            ]
        )
        y_offset = -min(
            [
                y - self._nx_graph.nodes[node]["_netext_node_buffer"].height / 2
                for node, (_, y) in node_positions.items()
            ]
        )

        return {
            node: (
                round(x_offset + x),
                round(y_offset + y),
            )
            for node, (x, y) in node_positions.items()
        }

    def _set_size_from_node_positions(
        self, node_positions: dict[Hashable, tuple[float, float]]
    ) -> None:
        """
        Sets the graph size given the node positions & node buffers. Assumes positions
        in console coordinate space.
        """

        # TODO: Division by 2 can lead to some rounding errors, check this is still what we want
        self.width = ceil(
            max(
                [
                    x + self._nx_graph.nodes[node]["_netext_node_buffer"].width / 2
                    for node, (x, _) in node_positions.items()
                ]
            )
        )
        self.height = ceil(
            max(
                [
                    y + self._nx_graph.nodes[node]["_netext_node_buffer"].height / 2
                    for node, (_, y) in node_positions.items()
                ]
            )
        )

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        # Get graph subview
        visible_nodes = nx.subgraph_view(
            self._nx_graph,
            filter_node=lambda n: self._nx_graph.nodes[n].get("$show", True),
        )
        node_buffers = nx.get_node_attributes(visible_nodes, "_netext_node_buffer")  # type: ignore
        all_buffers = chain(
            node_buffers.values(), self.edge_buffers, self.label_buffers
        )
        yield from render_buffers(all_buffers, self.width, self.height)

    def __rich_measure__(
        self, console: Console, options: ConsoleOptions
    ) -> Measurement:
        # We only support fixed width for now. It would be possible
        # to adaptively re-render if a different width is requested.
        return Measurement(self.width, self.width)
