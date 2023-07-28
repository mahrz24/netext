import pytest
from networkx import binomial_tree
from networkx import DiGraph
from rich.console import Console

from netext import ConsoleGraph
from netext.geometry.point import Point
from netext.layout_engines.static import StaticLayout


@pytest.fixture
def console():
    return Console()


def test_render_binomial_tree(console):
    """Test rendering a binomial tree. Simple smoke test that no exceptions are raised."""
    graph = binomial_tree(4)
    terminal_graph = ConsoleGraph(graph)

    with console.capture():
        console.print(terminal_graph)


def test_render_graph_with_two_nodes(console):
    """Test rendering a graph with two nodes. Simple smoke test that no exceptions are raised."""
    graph = DiGraph()
    graph.add_node(1, **{"$x": 1, "$y": 1})
    graph.add_node(2, **{"$x": 10, "$y": 1})
    graph.add_edge(1, 2)

    terminal_graph = ConsoleGraph[DiGraph](graph, layout_engine=StaticLayout())

    with console.capture() as capture:
        console.print(terminal_graph)
    original = capture.get()
    point = Point(*terminal_graph.to_graph_coordinates(1, 1))

    print(terminal_graph.node_positions)

    terminal_graph.remove_node(1)
    # TODO This is in the viewport space while the layout engine works in the graph space
    terminal_graph.add_node(1, position=point)
    terminal_graph.add_edge(1, 2)

    with console.capture() as capture:
        console.print(terminal_graph)
    mutated = capture.get()
    print("")
    print(original)
    print(mutated)
    assert original == mutated
