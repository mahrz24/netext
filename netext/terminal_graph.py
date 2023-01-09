from collections.abc import Hashable
from itertools import chain
from math import ceil
from typing import Any, Generic, TypeVar, cast

import networkx as nx
from rich.console import Console, ConsoleOptions, RenderResult
from rich.measure import Measurement

from .buffer_renderer import render_buffers
from .edge_rasterizer import EdgeBuffer, rasterize_edge
from .layout_engines.engine import LayoutEngine
from .layout_engines.grandalf import GrandalfSugiyamaLayout
from .node_rasterizer import NodeBuffer, rasterize_node

G = TypeVar("G", nx.Graph, nx.DiGraph)


class TerminalGraph(Generic[G]):
    def __init__(
        self,
        g: G,
        layout_engine: LayoutEngine[G] = GrandalfSugiyamaLayout[G](),
        console: Console = Console(),
    ):
        self._nx_graph: G = cast(G, g.copy())
        # First we create the node buffers, this allows us to pass the sizing information to the
        # layout engine. For each node in the graph we generate a node buffer that contains the
        # segments to render the node and metadata where to place the buffer.
        node_buffers: dict[Hashable, NodeBuffer] = {
            node: rasterize_node(console, node, cast(dict[Hashable, Any], data))
            for node, data in self._nx_graph.nodes(data=True)
        }

        # Store the node buffers in the graph itself
        nx.set_node_attributes(self._nx_graph, node_buffers, "_netext_node_buffer")

        # Position the nodes and add the position information to the graph
        node_positions: dict[Hashable, tuple[float, float]] = layout_engine(
            self._nx_graph
        )

        # From the node buffer sizing and the layout, determine the total size needed for the graph.
        # TODO: We could add explicit sizing, also it is possible to recompute the edge buffer adaptively.
        # TODO: Check if this should be part of the engine if we have a native integer coordinate layout engine)

        # The offset needs should be the most upper left point including the size of the node buffer
        node_positions = self._transform_node_positions_to_console(node_positions)
        self._set_size_from_node_positions(node_positions)

        # Store the node positions in the node buffers
        for node, pos in node_positions.items():
            buffer = self._nx_graph.nodes[node]["_netext_node_buffer"]
            buffer.x = pos[0]
            buffer.y = pos[1]

        # Assign magnets to edges

        # Now we rasterize the edges
        self.edge_buffers: list[EdgeBuffer] = [
            rasterize_edge(console, node_buffers[u], node_buffers[v], data)
            for (u, v, data) in self._nx_graph.edges(data=True)  # type: ignore
        ]

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
    ):
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
        node_buffers = nx.get_node_attributes(self._nx_graph, "_netext_node_buffer")
        all_buffers = chain(node_buffers.values(), self.edge_buffers)
        yield from render_buffers(all_buffers, self.width, self.height)

    def __rich_measure__(
        self, console: Console, options: ConsoleOptions
    ) -> Measurement:
        # We only support fixed width for now. It would be possible
        # to adaptively re-render if a different width is requested.
        return Measurement(self.width, self.width)
