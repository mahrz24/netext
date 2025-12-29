import pytest
from networkx import DiGraph
from netext.console_graph import ConsoleGraph, AutoZoom, RenderState
from netext.geometry.point import FloatPoint
from rich.console import Console


@pytest.fixture
def console():
    return Console()


def test_remove_nonexistent_node_raises_keyerror():
    graph = DiGraph()
    cg = ConsoleGraph(graph)
    with pytest.raises(KeyError):
        cg.remove_node("non_existent")


def test_zoom_fig():
    graph = DiGraph()
    graph.add_node(1)
    graph.add_node(2)
    graph.add_edge(1, 2)
    cg = ConsoleGraph(graph, max_width=100, max_height=100, zoom=AutoZoom.FIT)
    # Attempt a layout to trigger transitions
    cg.add_node(3, position=FloatPoint(0, 0))
    cg.add_edge(1, 3)
    cg.add_edge(2, 3)
    assert cg.zoom == AutoZoom.FIT
    assert cg._zoom_factor != 1.0


def test_zoom_factor_is_recomputed(console):
    graph = DiGraph()
    graph.add_node(1)
    graph.add_node(2)
    graph.add_edge(1, 2)
    cg = ConsoleGraph(graph, max_width=100, max_height=100, zoom=AutoZoom.FIT)

    with console.capture():
        console.print(cg)

    old_zoom_factor = cg._zoom_factor
    # Attempt a layout to trigger transitions
    for i in range(5):
        cg.add_node(i, position=FloatPoint(i, i))
        cg.add_edge(1, i)
        cg.add_edge(2, i)
    assert cg.zoom == AutoZoom.FIT
    assert cg._zoom_factor != old_zoom_factor


def test_add_node_after_render_resets_layout_state(console):
    graph = DiGraph()
    graph.add_node(1)
    cg = ConsoleGraph(graph)

    with console.capture():
        console.print(cg)

    cg.add_node(2)
    assert cg._render_state == RenderState.NODE_BUFFERS_RENDERED_FOR_LAYOUT


def test_remove_nonexistent_node_after_render_raises_keyerror(console):
    graph = DiGraph()
    graph.add_nodes_from([1, 2])
    graph.add_edge(1, 2)
    cg = ConsoleGraph(graph)
    with console.capture():
        console.print(cg)
    with pytest.raises(KeyError):
        cg.remove_node("does_not_exist")


def test_remove_edge_removes_from_core_graph():
    graph = DiGraph()
    graph.add_nodes_from([1, 2])
    graph.add_edge(1, 2)
    cg = ConsoleGraph(graph)
    cg.remove_edge(1, 2)
    assert (1, 2) not in cg._core_graph.all_edges()


def test_remove_edge_clears_rendered_edge_buffers():
    graph = DiGraph()
    graph.add_nodes_from([1, 2])
    graph.add_edge(1, 2)
    cg = ConsoleGraph(graph)
    cg.remove_edge(1, 2)
    # Attempt another operation to ensure references are cleaned up
    with pytest.raises(KeyError):
        _ = cg.edge_buffers[(1, 2)]


def test_update_node_data_sets_properties():
    graph = DiGraph()
    graph.add_node(1)
    cg = ConsoleGraph(graph)
    cg.update_node(1, data={"test": "value"}, update_data=True)
    assert "$properties" in cg._core_graph.node_data_or_default(1, {})
