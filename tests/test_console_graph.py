import pytest
from networkx import binomial_tree
from networkx import DiGraph
from rich.console import Console

from netext import ConsoleGraph
from netext.console_graph import AutoZoom
from netext.geometry.point import FloatPoint
from netext.layout_engines.static import StaticLayout


@pytest.fixture
def console():
    return Console()


def test_render_binomial_tree(console):
    """Test rendering a binomial tree. Simple smoke test that no exceptions are raised.
    """
    graph = binomial_tree(4)
    terminal_graph = ConsoleGraph(graph)

    with console.capture():
        console.print(terminal_graph)


def test_render_graph_with_mutations_remove_and_add(console):
    graph = DiGraph()
    graph.add_node(1, **{"$x": 1, "$y": 1})
    graph.add_node(2, **{"$x": 10, "$y": 1})
    graph.add_edge(1, 2)

    terminal_graph = ConsoleGraph[DiGraph](graph, layout_engine=StaticLayout())

    with console.capture() as capture:
        console.print(terminal_graph)
    original = capture.get()

    terminal_graph.remove_node(1)

    terminal_graph.add_node(1, position=FloatPoint(1, 1))
    terminal_graph.add_edge(1, 2)

    with console.capture() as capture:
        console.print(terminal_graph)
    mutated = capture.get()

    assert original == mutated


def test_render_graph_with_mutations_update_positions(console):
    graph = DiGraph()
    graph.add_node(1, **{"$x": 1, "$y": 1})
    graph.add_node(2, **{"$x": 10, "$y": 1})
    graph.add_edge(1, 2)

    terminal_graph = ConsoleGraph[DiGraph](graph, layout_engine=StaticLayout())

    with console.capture() as capture:
        console.print(terminal_graph)
    original = capture.get()

    terminal_graph.update_node(1, position=FloatPoint(1, 2))

    with console.capture() as capture:
        console.print(terminal_graph)
    mutated = capture.get()

    graph = DiGraph()
    graph.add_node(1, **{"$x": 1, "$y": 2})
    graph.add_node(2, **{"$x": 10, "$y": 1})
    graph.add_edge(1, 2)

    expected_terminal_graph = ConsoleGraph[DiGraph](graph, layout_engine=StaticLayout())

    with console.capture() as capture:
        console.print(expected_terminal_graph)
    expected = capture.get()

    assert original != mutated
    assert expected == mutated


def test_render_graph_with_mutations_update_positions_and_zoom_fit(console):
    graph = DiGraph()
    graph.add_node(1, **{"$x": 1, "$y": 1})
    graph.add_node(2, **{"$x": 10, "$y": 1})
    graph.add_edge(1, 2)

    terminal_graph = ConsoleGraph[DiGraph](
        graph, layout_engine=StaticLayout(), zoom=AutoZoom.FIT
    )

    with console.capture() as capture:
        console.print(terminal_graph)
    original = capture.get()

    terminal_graph.update_node(1, position=FloatPoint(1, 5))
    terminal_graph.update_node(1, position=FloatPoint(1, 1))

    with console.capture() as capture:
        console.print(terminal_graph)
    mutated = capture.get()

    assert original == mutated
