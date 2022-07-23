from typing import TypeVar, Generic, Hashable
from heapq import merge
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
        node_positions: Dict[Hashable, (float, float)] = layout_engine(self._nx_graph)

        # From the node buffer sizing and the layout, determine the total size needed for the graph.
        # TODO: We could add explicit sizing, also it is possible to recompute the edge buffer adaptively.
        # TODO: Check if this should be part of the engine if we have a native integer coordinate layout engine)

        # The offset needs should be the most upper left point including the size of the node buffer
        # TODO: Division by 2 can lead to some rounding errors, check this
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

        # Find a good way to avoid overlapping buffers due to rounding errors
        x_scaling_factor = 1
        y_scaling_factor = 0.2

        node_positions = {
            node: (
                round((x_offset + x) * x_scaling_factor),
                round((y_offset + y) * y_scaling_factor),
            )
            for node, (x, y) in node_positions.items()
        }

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

        for node, pos in node_positions.items():
            buffer = self._nx_graph.nodes[node]["_netext_node_buffer"]
            buffer.x = pos[0]
            buffer.y = pos[1]

        # Now we rasterize the edges
        self.edge_buffers: List[EdgeBuffer] = [
            rasterize_edge(node_buffers[u], node_buffers[v], data)
            for u, v, data in self._nx_graph.edges(data=True)
        ]

        print(self._nx_graph.nodes(data=True))

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        node_buffers = nx.get_node_attributes(self._nx_graph, "_netext_node_buffer")

        buffers_by_row = defaultdict(list)
        for buffer in node_buffers.values():
            buffers_by_row[buffer.top_y] = sorted(buffers_by_row[buffer.top_y] + [((buffer.left_x, buffer))])

        print(buffers_by_row)
        # TODO: Right now this only supports rectangular nodes, for
        # other shapes the lx argument would need to be updated with
        # each row or an additional row offest be defined in the node
        # buffer.
        active_buffers = []
        for row in range(self.height):
            active_buffers = [(lx, buffer_row+1, buffer) for lx, buffer_row, buffer in active_buffers if row < buffer.bottom_y]
            new_active_buffers = [(lx, 0, buffer) for lx, buffer in buffers_by_row[row]]
            active_buffers = list(merge(active_buffers, new_active_buffers))
            print(row, active_buffers)
            if not active_buffers:
                yield Segment(" "*self.width+"\n")
                continue
            current_x = 0
            for lx, buffer_row, buffer in active_buffers:
                # TODO: No overlapping yet, we skip overlapped nodes for now and assume the layout does not create overlaps.
                if current_x > lx:
                    continue
                print(current_x)
                print(lx)
                yield Segment(" "*(lx-current_x))
                yield buffer.segments[buffer_row]
                current_x = lx+buffer.width

            if current_x < self.width:
                yield Segment(" "*(self.width-current_x))
            yield Segment("\n")

    def __rich_measure__(
        self, console: Console, options: ConsoleOptions
    ) -> Measurement:
        return Measurement(self.width, self.width)
