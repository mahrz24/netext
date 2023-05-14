from pathlib import Path

EXAMPLES_DIR = Path("../../examples")


def test_minimal_example(snap_compare):
    assert snap_compare(EXAMPLES_DIR / "minimal.py")


def test_labels_example(snap_compare):
    assert snap_compare(EXAMPLES_DIR / "labels.py")


def test_rich_nodes_example(snap_compare):
    assert snap_compare(EXAMPLES_DIR / "rich_nodes.py")


def test_routing_example(snap_compare):
    assert snap_compare(EXAMPLES_DIR / "routing.py")


def test_hypercube_example(snap_compare):
    assert snap_compare(EXAMPLES_DIR / "hypercube.py")


def test_mst_example(snap_compare):
    assert snap_compare(EXAMPLES_DIR / "mst.py")
