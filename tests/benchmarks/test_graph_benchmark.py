from networkx import binomial_tree
import networkx as nx
import pytest
from rich.console import Console

from netext import ConsoleGraph
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_routing.modes import EdgeRoutingMode


def _run_graph_benchmark(n):
    graph = binomial_tree(n)
    nx.set_edge_attributes(graph, EdgeRoutingMode.ORTHOGONAL, "$edge-routing-mode")
    nx.set_edge_attributes(
        graph,
        EdgeSegmentDrawingMode.BOX,
        "$edge-segment-drawing-mode",
    )
    console = Console()
    cg = ConsoleGraph.from_networkx(graph)
    console.print(cg)


@pytest.mark.parametrize("n", [2, 4, 6])
@pytest.mark.benchmark
def test_graph_performance_small_binomial_tree(n, benchmark):
    benchmark(lambda: _run_graph_benchmark(n))
