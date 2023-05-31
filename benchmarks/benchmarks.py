# Write the benchmarking functions here.
# See "Writing benchmarks" in the asv docs for more information.

from networkx import binomial_tree
import networkx as nx
from rich.console import Console

from netext import ConsoleGraph
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_routing.modes import EdgeRoutingMode


class TimeSuite:
    """
    An example benchmark that times the performance of various kinds
    of iterating over dictionaries in Python.
    """

    params = [2, 4, 5, 6, 7]

    def setup(self, n):
        self.graph = binomial_tree(n)
        self.graph_ortho_box = binomial_tree(n)

        nx.set_edge_attributes(
            self.graph_ortho_box, EdgeRoutingMode.ORTHOGONAL, "$edge-routing-mode"
        )
        nx.set_edge_attributes(
            self.graph_ortho_box,
            EdgeSegmentDrawingMode.BOX,
            "$edge-segment-drawing-mode",
        )

        self.terminal_graph = ConsoleGraph(self.graph)
        self.console = Console()

    def time_render_binomial_tree(self, n):
        with self.console.capture():
            self.console.print(self.terminal_graph)

    def time_layout_and_rasterize_binomial_tree(self, n):
        ConsoleGraph(self.graph)

    def time_layout_and_rasterize_binomial_tree_orthogonal_box(self, n):
        ConsoleGraph(self.graph_ortho_box)
