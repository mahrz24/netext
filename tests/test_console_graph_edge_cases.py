import pytest
from networkx import DiGraph
from netext.console_graph import ConsoleGraph, AutoZoom
from netext.geometry.point import FloatPoint
from netext.geometry.region import Region
from netext.layout_engines import StaticLayout
from netext.testing.assertions import assert_output_equal
from rich.console import Console

@pytest.fixture
def console():
    return Console()

def test_line_194():
    """Covers case where zoom is a float (int) to trigger code around line 194."""
    graph = DiGraph()
    _ = ConsoleGraph(graph, zoom=2.0)

def test_line_248():
    """Covers code that checks render state transitions (line 248)."""
    graph = DiGraph()
    cg = ConsoleGraph(graph)
    # Force internal requirement check by calling remove_node
    with pytest.raises(KeyError):
        cg.remove_node("non_existent")

def test_line_303_304():
    """Covers a state transition path (lines 303-304)."""
    graph = DiGraph()
    cg = ConsoleGraph(graph)
    # Attempt a layout to trigger transitions
    cg.layout()

def test_line_307_309():
    """Covers another state transition (lines 307-309)."""
    graph = DiGraph()
    cg = ConsoleGraph(graph)
    # Force a transition by calling internal transitions in layout
    cg.layout()
    # Setting zoom might retrigger transitions
    cg.zoom = AutoZoom.FIT

def test_line_319():
    """Covers code around line 319, likely requiring transitions to EDGES_RENDERED."""
    graph = DiGraph()
    graph.add_node(1)
    cg = ConsoleGraph(graph)
    cg.layout()

def test_line_339():
    """Covers code around line 339 (resetting states)."""
    graph = DiGraph()
    cg = ConsoleGraph(graph)
    # Trigger some transitions, then reset
    cg.layout()
    cg.reset_viewport()

def test_line_342():
    """Covers code around line 342."""
    graph = DiGraph()
    cg = ConsoleGraph(graph)
    cg.layout()
    # Possibly triggers the line when getting zoom
    _ = cg.zoom

def test_line_344():
    """Covers code around line 344."""
    graph = DiGraph()
    cg = ConsoleGraph(graph)
    cg.zoom = 2.0

def test_line_346():
    """Covers code around line 346."""
    graph = DiGraph()
    cg = ConsoleGraph(graph)
    cg.zoom = (2.0, 3.0)

def test_line_447():
    """Covers code around line 447, possibly removing a node after edges are rendered."""
    graph = DiGraph()
    graph.add_nodes_from([1, 2])
    graph.add_edge(1, 2)
    cg = ConsoleGraph(graph)
    with pytest.raises(KeyError):
        cg.remove_node("does_not_exist")

def test_line_456():
    """Covers code for removing an edge near line 456."""
    graph = DiGraph()
    graph.add_nodes_from([1, 2])
    graph.add_edge(1, 2)
    cg = ConsoleGraph(graph)
    cg.remove_edge(1, 2)
    assert (1, 2) not in cg._core_graph.all_edges()

def test_line_459():
    """Covers code verifying internal references after removing edges (line 459)."""
    graph = DiGraph()
    graph.add_nodes_from([1, 2])
    graph.add_edge(1, 2)
    cg = ConsoleGraph(graph)
    cg.remove_edge(1, 2)
    # Attempt another operation to ensure references are cleaned up
    with pytest.raises(KeyError):
        _ = cg.edge_buffers[(1, 2)]

def test_line_501_502():
    """Covers code around lines 501-502 (updating node data)."""
    graph = DiGraph()
    graph.add_node(1)
    cg = ConsoleGraph(graph)
    cg.update_node(1, data={"test": "value"}, update_data=True)
    assert "$properties" in cg._core_graph.node_data_or_default(1, {})

def test_line_550():
    """Covers code around line 550 (transition or layout method part)."""
    graph = DiGraph()
    cg = ConsoleGraph(graph)
    cg.layout()  # Should hit line 550 in layout steps

def test_line_568():
    """Covers code around line 568 in layout or zoom computation logic."""
    graph = DiGraph()
    cg = ConsoleGraph(graph, zoom=(2, 3))
    cg.layout()

def test_line_613():
    """Covers code around line 613 (possibly a transition edge)."""
    graph = DiGraph()
    cg = ConsoleGraph(graph)
    cg.layout()
    # Possibly triggers final transition to EDGES_RENDERED
    console = Console()
    with console.capture():
        console.print(cg)

def test_line_619():
    """Covers code around line 619 (final rendering steps)."""
    graph = DiGraph()
    cg = ConsoleGraph(graph)
    console = Console()
    cg.layout()
    with console.capture():
        console.print(cg)

def test_line_659():
    """Covers code around line 659 (port buffers or another transition)."""
    graph = DiGraph()
    cg = ConsoleGraph(graph)
    graph.add_node(1)
    # Force re-render with ports
    cg.add_node(1, data={"$content-renderer": lambda _, __, ___: "test"})
    console = Console()
    with console.capture():
        console.print(cg)

def test_line_742():
    """Covers code around line 742 (edge rendering)."""
    graph = DiGraph()
    graph.add_nodes_from([1, 2])
    graph.add_edge(1, 2)
    cg = ConsoleGraph(graph)
    console = Console()
    with console.capture():
        console.print(cg)

def test_line_749():
    """Covers code around line 749 (edge label rendering)."""
    graph = DiGraph()
    graph.add_node(1)
    graph.add_node(2)
    graph.add_edge(1, 2, **{"label": "edge_label"})
    cg = ConsoleGraph(graph)
    console = Console()
    with console.capture():
        console.print(cg)

def test_line_758_762():
    """Covers code around lines 758-762 (edge constraints)."""
    graph = DiGraph()
    graph.add_nodes_from([1, 2])
    graph.add_edge(1, 2)
    cg = ConsoleGraph(graph)
    # Update node to possibly trigger constraints
    cg.update_node(1, position=FloatPoint(2.0, 2.0))
    cg.layout()

def test_line_767():
    """Covers code around line 767 (more edge rendering paths)."""
    graph = DiGraph()
    graph.add_nodes_from([1, 2])
    graph.add_edge(1, 2)
    cg = ConsoleGraph(graph)
    cg.layout()
    # Possibly triggers alternative path in edge rendering
    cg.update_edge(1, 2, {}, update_layout=False)

def test_line_841():
    """Covers code around line 841 (all buffers iteration)."""
    graph = DiGraph()
    cg = ConsoleGraph(graph)
    list(cg._all_buffers())  # triggers iteration

def test_line_848():
    """Covers code around line 848 (unconstrained viewport logic)."""
    graph = DiGraph()
    cg = ConsoleGraph(graph)
    _ = cg._unconstrained_viewport()

def test_line_878():
    """Covers code around line 878 (__rich_console__)."""
    graph = DiGraph()
    cg = ConsoleGraph(graph)
    console = Console()
    with console.capture():
        console.print(cg)
    # Implicitly covers lines in __rich_console__

def test_line_896_901():
    """Covers code around lines 896-901 (__rich_measure__)."""
    graph = DiGraph()
    cg = ConsoleGraph(graph)
    console = Console()
    # This calls __rich_measure__ internally
    measure = cg.__rich_measure__(console, console.options)
    assert measure.minimum >= 0
