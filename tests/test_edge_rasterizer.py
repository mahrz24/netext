import pytest
from rich.console import Console

from netext.edge_rasterizer import rasterize_edge
from netext.geometry.point import Point
from netext.node_rasterizer import rasterize_node
from netext.properties.edge import EdgeProperties

import netext._core as core


@pytest.fixture
def console() -> Console:
    return Console()


def test_trivial_edge(console: Console) -> None:
    node_buffer_u = rasterize_node(console, node="A", data=dict())
    node_buffer_v = rasterize_node(console, node="B", data=dict())

    node_buffer_u.center = Point(1, 1)
    node_buffer_v.center = Point(9, 9)

    edge_router = core.EdgeRouter()

    result = rasterize_edge(
        console,
        edge_router,
        node_buffer_u,
        node_buffer_v,
        properties=EdgeProperties(),
    )
    assert result is not None
    edge, _ = result

    assert edge.width == 6
    assert edge.height == 7
