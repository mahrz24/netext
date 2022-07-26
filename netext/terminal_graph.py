from collections import defaultdict
from heapq import merge
from itertools import chain
from math import ceil
from typing import Dict, Generic, Hashable, List, Tuple, TypeVar

import networkx as nx
from rich import print
from rich.console import Console, ConsoleOptions, Measurement, RenderResult
from rich.segment import Segment
from rich.style import Style

from .edge_rasterizer import EdgeBuffer, rasterize_edge
from .layout_engines.engine import LayoutEngine
from .layout_engines.grandalf import GrandalfSugiyamaLayout
from .node_rasterizer import NodeBuffer, rasterize_node

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
        node_positions: Dict[Hashable, Tuple[float, float]] = layout_engine(
            self._nx_graph
        )

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
                buffers_by_row[buffer.top_y] + [buffer]
            )

        active_buffers = []
        for row in range(self.height):
            # This contains information where the segments for the currently
            # active buffers start (active buffer == intersects with current line)
            active_buffers = sorted(
                [
                    (
                        buffer.left_x + buffer.segments[buffer_row + 1].x_offset,
                        buffer.segments[buffer_row + 1].segment,
                        buffer_row + 1,
                        buffer,
                    )
                    for _, segment, buffer_row, buffer in active_buffers
                    if row <= buffer.bottom_y
                ]
            )

            new_active_buffers = sorted(
                [
                    (
                        buffer.left_x + buffer.segments[0].x_offset,
                        buffer.segments[0].segment,
                        0,
                        buffer,
                    )
                    for buffer in buffers_by_row[row]
                ]
            )

            active_buffers = list(merge(active_buffers, new_active_buffers))

            if not active_buffers:
                yield Segment(" " * self.width + "\n")
                continue

            current_x = 0

            working_buffers = list(active_buffers)
            # print(working_buffers)
            while working_buffers:
                segment_left_x, segment, buffer_row, buffer = working_buffers.pop(0)

                full_segment_cell_length = segment.cell_length

                # Empty segments should be ignored, though ideally we should not store them
                # in the buffer at all.
                if full_segment_cell_length == 0:
                    continue

                # We need to cut the segment and only print the non overlapped part if the current x coordinate
                # is already the buffer's left boundary.
                if current_x >= segment_left_x:
                    segment = segment.split_cells(current_x - segment_left_x)[1]
                else:
                    # Pad to the left boundary of the segment
                    yield Segment(" " * (segment_left_x - current_x))
                    current_x = segment_left_x

                # Perform a look ahead, and if the left boundary of any of the next active buffers
                # intersects with the current buffer & length (and has a smaller z-index), we split the
                # current buffer segment at that place and add the remaining part after the intersecting
                # segment.
                for i, (segment_left_x_next, _, _, buffer_next) in enumerate(
                    working_buffers
                ):
                    if (
                        segment_left_x_next <= segment_left_x + full_segment_cell_length
                        and buffer_next.z_index < buffer.z_index
                    ):
                        segment, overflow_segment = segment.split_cells(
                            segment_left_x_next - segment_left_x
                        )
                        working_buffers.insert(
                            i + 1,
                            (segment_left_x_next, overflow_segment, buffer_row, buffer),
                        )
                        break

                # If the overlap from a prior segment or the overlap of an upcoming
                # segment (with lower z-index) cut the segment to disappear, nothing
                # will be yielded.
                if segment.cell_length > 0:
                    yield segment
                    current_x += segment.cell_length

            if current_x < self.width:
                yield Segment(" " * (self.width - current_x))
            yield Segment("\n")

    def __rich_measure__(
        self, console: Console, options: ConsoleOptions
    ) -> Measurement:
        # We only support fixed width for now. It would be possible
        # to adaptively re-render if a different width is requested.
        return Measurement(self.width, self.width)
