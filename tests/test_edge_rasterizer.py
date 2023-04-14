import pytest
from rich.console import Console

from netext.edge_rasterizer import rasterize_edge
from netext.geometry.point import Point
from netext.edge_routing.edge import EdgeSegment, RoutedEdgeSegments
from netext.edge_routing.modes import EdgeRoutingMode
from netext.edge_routing.route import route_edge
from netext.node_rasterizer import rasterize_node


@pytest.fixture
def console() -> Console:
    return Console()


def test_trivial_edge(console: Console) -> None:
    node_buffer_u = rasterize_node(console, node="A", data=dict())
    node_buffer_v = rasterize_node(console, node="B", data=dict())

    node_buffer_u.center = Point(1, 1)
    node_buffer_v.center = Point(9, 9)

    edge, _, _ = rasterize_edge(
        console,
        node_buffer_u,
        node_buffer_v,
        [node_buffer_u, node_buffer_u],
        [],
        data=dict(),
    )

    assert edge.width == 5
    assert edge.height == 5


def test_route_edge_direct(console: Console) -> None:
    edge_segements = route_edge(
        Point(x=1, y=2), Point(x=5, y=6), routing_mode=EdgeRoutingMode.straight
    )
    assert edge_segements == RoutedEdgeSegments(
        [EdgeSegment(start=Point(x=1, y=2), end=Point(x=5, y=6))], intersections=0
    )


def test_route_edge_straight(console: Console) -> None:
    edge_segements = route_edge(
        Point(x=1, y=2), Point(x=5, y=6), routing_mode=EdgeRoutingMode.orthogonal
    )
    assert edge_segements == RoutedEdgeSegments(
        [
            EdgeSegment(start=Point(x=1, y=2), end=Point(x=1, y=6)),
            EdgeSegment(start=Point(x=1, y=6), end=Point(x=5, y=6)),
        ],
        intersections=0,
    )
