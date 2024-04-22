from netext._core import CoreGraph


def test_initialization():
    g = CoreGraph.from_edges([(1, 2), (2, 3), (3, 4)])
    assert set(g.all_nodes()) == {1, 2, 3, 4}
