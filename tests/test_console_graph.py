import pytest
from networkx import binomial_tree
from networkx import DiGraph
from rich.console import Console

from netext import ConsoleGraph
from netext.console_graph import AutoZoom
from netext.geometry.point import FloatPoint
from netext.geometry.region import Region
from netext.layout_engines.static import StaticLayout


@pytest.fixture
def console():
    return Console()


def test_render_binomial_tree(console):
    """Test rendering a binomial tree. Simple smoke test that no exceptions are raised."""
    graph = binomial_tree(4)
    console_graph = ConsoleGraph(graph)

    with console.capture():
        console.print(console_graph)


@pytest.mark.parametrize("zoom", [AutoZoom.FIT, AutoZoom.FIT_PROPORTIONAL, 2, (2, 3)])
def test_zoom(console, zoom: AutoZoom | float | tuple[float, float]):
    graph = binomial_tree(4)
    expected_console_graph = ConsoleGraph(graph, zoom=zoom)
    console_graph = ConsoleGraph(graph)
    console_graph.zoom = zoom

    with console.capture() as capture:
        console.print(console_graph)
    original = capture.get()

    with console.capture() as capture:
        console.print(expected_console_graph)
    expected = capture.get()

    assert original == expected


def test_get_viewport_when_set_previously():
    # Set up
    graph = binomial_tree(4)
    console_graph = ConsoleGraph(graph)
    console_graph._viewport = Region(x=0, y=0, width=100, height=100)

    # Exercise
    result = console_graph.viewport

    # Verify
    assert result == Region(x=0, y=0, width=100, height=100)


@pytest.mark.parametrize("viewport", [Region(x=0, y=0, width=100, height=100)])
def test_viewport_renders_the_same_when_set_or_initialized(console, viewport: Region):
    graph = binomial_tree(4)
    expected_console_graph = ConsoleGraph(graph, viewport=viewport)
    console_graph = ConsoleGraph(graph)
    console_graph.viewport = viewport

    with console.capture() as capture:
        console.print(console_graph)
    original = capture.get()

    with console.capture() as capture:
        console.print(expected_console_graph)
    expected = capture.get()

    assert original == expected


def test_render_graph_with_mutations_remove_and_add(console):
    graph = DiGraph()
    graph.add_node(1, **{"$x": 1, "$y": 1})
    graph.add_node(2, **{"$x": 10, "$y": 1})
    graph.add_edge(1, 2)

    console_graph = ConsoleGraph[DiGraph](graph, layout_engine=StaticLayout())

    with console.capture() as capture:
        console.print(console_graph)
    original = capture.get()

    console_graph.remove_node(1)

    console_graph.add_node(1, position=FloatPoint(1, 1))
    console_graph.add_edge(1, 2)

    with console.capture() as capture:
        console.print(console_graph)
    mutated = capture.get()

    assert original == mutated


def test_render_graph_with_mutations_update_positions(console):
    graph = DiGraph()
    graph.add_node(1, **{"$x": 1, "$y": 1})
    graph.add_node(2, **{"$x": 10, "$y": 1})
    graph.add_edge(1, 2)

    console_graph = ConsoleGraph[DiGraph](graph, layout_engine=StaticLayout())

    with console.capture() as capture:
        console.print(console_graph)
    original = capture.get()

    console_graph.update_node(1, position=FloatPoint(1, 2))

    with console.capture() as capture:
        console.print(console_graph)
    mutated = capture.get()

    graph = DiGraph()
    graph.add_node(1, **{"$x": 1, "$y": 2})
    graph.add_node(2, **{"$x": 10, "$y": 1})
    graph.add_edge(1, 2)

    expected_console_graph = ConsoleGraph[DiGraph](graph, layout_engine=StaticLayout())

    with console.capture() as capture:
        console.print(expected_console_graph)
    expected = capture.get()

    assert original != mutated
    assert expected == mutated


@pytest.mark.parametrize("zoom", [AutoZoom.FIT, AutoZoom.FIT_PROPORTIONAL])
def test_render_graph_with_mutations_update_positions_and_zoom(console, zoom: AutoZoom):
    graph = DiGraph()
    graph.add_node(1, **{"$x": 1, "$y": 1})
    graph.add_node(2, **{"$x": 10, "$y": 1})
    graph.add_edge(1, 2)

    console_graph = ConsoleGraph[DiGraph](graph, layout_engine=StaticLayout(), zoom=zoom)

    with console.capture() as capture:
        console.print(console_graph)
    original = capture.get()

    console_graph.update_node(1, position=FloatPoint(1, 5))
    console_graph.update_node(1, position=FloatPoint(1, 1))

    with console.capture() as capture:
        console.print(console_graph)
    mutated = capture.get()

    assert original == mutated


def test_render_graph_with_mutations_update_positions_and_data(console):
    graph = DiGraph()
    graph.add_node(
        1,
        **{
            "$x": 1,
            "$y": 1,
            "label": "foo",
            "$content-renderer": lambda _, d, __: d["label"],
        },
    )
    graph.add_node(
        2,
        **{
            "$x": 10,
            "$y": 1,
            "label": "bar",
            "$content-renderer": lambda _, d, __: d["label"],
        },
    )

    graph.add_edge(1, 2)

    console_graph = ConsoleGraph[DiGraph](graph, layout_engine=StaticLayout())

    with console.capture() as capture:
        console.print(console_graph)
    original = capture.get()

    console_graph.update_node(1, position=FloatPoint(1, 2), data={"label": "bar"})

    with console.capture() as capture:
        console.print(console_graph)
    mutated = capture.get()

    graph = DiGraph()
    graph.add_node(
        1,
        **{
            "$x": 1,
            "$y": 2,
            "label": "bar",
            "$content-renderer": lambda _, d, __: d["label"],
        },
    )
    graph.add_node(
        2,
        **{
            "$x": 10,
            "$y": 1,
            "label": "bar",
            "$content-renderer": lambda _, d, __: d["label"],
        },
    )
    graph.add_edge(1, 2)

    expected_console_graph = ConsoleGraph[DiGraph](graph, layout_engine=StaticLayout())

    with console.capture() as capture:
        console.print(expected_console_graph)
    expected = capture.get()

    assert original != mutated
    assert expected == mutated
