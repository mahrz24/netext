from networkx import binomial_tree
import networkx as nx
import pytest
from rich.console import Console

from netext import ConsoleGraph
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_routing.modes import EdgeRoutingMode


@pytest.mark.benchmark
def test_graph_performance_small_binomial_tree(benchmark):
    graph = binomial_tree(5)
    nx.set_edge_attributes(graph, EdgeRoutingMode.ORTHOGONAL, "$edge-routing-mode")
    nx.set_edge_attributes(
        graph,
        EdgeSegmentDrawingMode.BOX,
        "$edge-segment-drawing-mode",
    )
    console = Console()

    @benchmark
    def _benchmark():
        cg = ConsoleGraph(graph)
        console.print(cg)
