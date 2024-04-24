import pytest
from netext._core import CoreGraph


@pytest.fixture
def simple_graph():
    return CoreGraph.from_edges([(1, 2), (2, 3), (3, 4)])


def test_initialization(simple_graph: CoreGraph):
    assert set(simple_graph.all_nodes()) == {1, 2, 3, 4}
    assert set(simple_graph.all_edges()) == {(1, 2), (2, 3), (3, 4)}


def test_adding_data(simple_graph: CoreGraph):
    data = {"foo": "bar"}
    simple_graph.update_node_data(1, data)
    assert simple_graph.node_data(1) == data


def test_adding_and_mutating_original_data(simple_graph: CoreGraph):
    data = {"foo": "bar"}
    simple_graph.update_node_data(1, data)
    data["bar"] = "baz"
    assert simple_graph.node_data(1) == data
    assert simple_graph.node_data_or_default(1, None) == data
