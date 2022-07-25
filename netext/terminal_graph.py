from typing import Dict, List, Tuple, TypeVar, Generic, Hashable
from heapq import merge
from itertools import chain
from collections import defaultdict
from rich.console import Console, ConsoleOptions, RenderResult, Measurement
from rich.segment import Segment
from rich.style import Style
from rich import print

import networkx as nx

from .node_rasterizer import rasterize_node, NodeBuffer
from .edge_rasterizer import rasterize_edge, EdgeBuffer
from .layout_engines.engine import LayoutEngine
from .layout_engines.grandalf import GrandalfSugiyamaLayout

from math import ceil

G = TypeVar("G", nx.Graph, nx.DiGraph)


class TerminalGraph(Generic[G]):
    def __init__(self, g: G, layout_engine: LayoutEngine = GrandalfSugiyamaLayout()):
        self._nx_graph = g.copy()
        # First we create the node buffers, this allows us to pass the sizing information to the
        # layout engine. For each node in the graph we generate a node buffer that contains the
        # segments to render the node and metadata where to place the buffer and information
        # about padding.
        node_buffers: Dict[Hashable, NodeBuffer] = {
            node: rasterize_node(node, data)
            for node, data in self._nx_graph.nodes(data=True)
        }

        # Store the node buffers in the graph itself
        nx.set_node_attributes(self._nx_graph, node_buffers, "_netext_node_buffer")

        # Position the nodes and add the position information to the graph
        node_positions: Dict[Hashable, Tuple[float, float]] = layout_engine(self._nx_graph)

        # From the node buffer sizing and the layout, determine the total size needed for the graph.
        # TODO: We could add explicit sizing, also it is possible to recompute the edge buffer adaptively.
        # TODO: Check if this should be part of the engine if we have a native integer coordinate layout engine)

        # The offset needs should be the most upper left point including the size of the node buffer
        # TODO: Division by 2 can lead to some rounding errors, check this is still what we want
        node_positions = self._transform_node_positions_to_console(node_positions)
        self._set_size_from_node_positions(node_positions)

        # Store the node positions in the node buffers
        for node, pos in node_positions.items():
            buffer = self._nx_graph.nodes[node]["_netext_node_buffer"]
            buffer.x = pos[0]
            buffer.y = pos[1]

        # Now we rasterize the edges
        self.edge_buffers: List[EdgeBuffer] = [
            rasterize_edge(node_buffers[u], node_buffers[v], data)
            for u, v, data in self._nx_graph.edges(data=True)
        ]

    def _transform_node_positions_to_console(
        self, node_positions: Dict[Hashable, Tuple[float, float]]
    ) -> Dict[Hashable, Tuple[float, float]]:
        """Transforms the node positions into console coordinate space.

        Right now this assumes sizing from the layout engine is correct and only
        performs rounding and transpositions.
        """

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
        self, node_positions: Dict[Hashable, Tuple[float, float]]
    ):
        """
        Sets the graph size given the node positions & node buffers. Assumes positions
        in console coordinate space.
        """
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

        buffers_by_row = defaultdict(list)
        for buffer in chain(node_buffers.values(), self.edge_buffers):
            buffers_by_row[buffer.top_y] = sorted(
                buffers_by_row[buffer.top_y] + [((buffer.left_x, buffer))]
            )

        active_buffers = []
        for row in range(self.height):
            # This contains information where the segments for the currently
            # active buffers start (active buffer == intersects with current line)
            active_buffers = sorted(
                [
                    (
                        bb_left_x
                        - buffer.segments[buffer_row].x_offset
                        + buffer.segments[buffer_row + 1].x_offset,
                        z_index,
                        buffer_row + 1,
                        buffer,
                    )
                    for bb_left_x, z_index, buffer_row, buffer in active_buffers
                    if row < buffer.bottom_y
                ]
            )
            new_active_buffers = sorted(
                [
                    (bb_left_x + buffer.segments[0].x_offset, buffer.z_index, 0, buffer)
                    for bb_left_x, buffer in buffers_by_row[row]
                ]
            )
            active_buffers = list(
                merge(active_buffers, new_active_buffers)
            )
            if not active_buffers:
                yield Segment(" " * self.width + "\n")
                continue
            current_x = 0

            # TODO: There is still some problem here as can be seen in the payley graph
            # Some overlaps seem to push lines to far
            for bb_left_x, z_index, buffer_row, buffer in active_buffers:
                # We need to cut the segment and only print the non overlapped part if the current x coordinate 
                # is already the buffer's left boundary.
                segment: Segment = buffer.segments[buffer_row].segment
                segment_cell_length = buffer.segments[buffer_row].segment.cell_length
                if current_x > bb_left_x:
                    # TODO: We already sort by z-index, but if we have a z-index overlap
                    # We need to maintain a look-ahead z-index buffer to see if we have to cut more
                    segment = segment.split_cells(current_x-bb_left_x)[1]
                else:
                    yield Segment(" " * (bb_left_x - current_x))
                yield segment
                current_x = bb_left_x + segment_cell_length

            if current_x < self.width:
                yield Segment(" " * (self.width - current_x))
            yield Segment("\n")

    def __rich_measure__(
        self, console: Console, options: ConsoleOptions
    ) -> Measurement:
        # We only support fixed width for now. It would be possible
        # to adaptively re-render if a different width is requested.
        return Measurement(self.width, self.width)
