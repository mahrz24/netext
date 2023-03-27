import pytest
from rich.console import Console

from netext.edge_rasterizer import (
    EdgeRoutingMode,
    EdgeSegment,
    Point,
    rasterize_edge,
    route_edge,
)
from netext.node_rasterizer import rasterize_node


@pytest.fixture
def console() -> Console:
    return Console()


def test_trivial_edge(console: Console) -> None:
    node_buffer_u = rasterize_node(console, node="A", data=dict())
    node_buffer_v = rasterize_node(console, node="B", data=dict())

    node_buffer_u.center.x = 1
    node_buffer_u.center.y = 1

    node_buffer_v.center.x = 9
    node_buffer_v.center.y = 9

    edge, _, _ = rasterize_edge(
        console,
        node_buffer_u,
        node_buffer_v,
        [node_buffer_u, node_buffer_u],
        [],
        data=dict(),
    )

    assert edge.width == 6
    assert edge.height == 6


def test_route_edge_direct(console: Console) -> None:
    edge_segements = route_edge(
        Point(x=1, y=2), Point(x=5, y=6), routing_mode=EdgeRoutingMode.straight
    )
    assert edge_segements == [EdgeSegment(start=Point(x=1, y=2), end=Point(x=5, y=6))]


def test_route_edge_straight(console: Console) -> None:
    edge_segements = route_edge(
        Point(x=1, y=2), Point(x=5, y=6), routing_mode=EdgeRoutingMode.orthogonal
    )
    assert edge_segements == [
        EdgeSegment(start=Point(x=1, y=2), end=Point(x=1, y=6)),
        EdgeSegment(start=Point(x=1, y=6), end=Point(x=5, y=6)),
    ]
